#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Proxy Checker v1.0
- Verifica proxies vivas
- Testea conectividad con login.live.com
- Alta velocidad con 150 threads
"""

import os
import sys
import re
import requests
import threading
import colorama
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import time

# Cambiar al directorio del script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

colorama.init()

# === CONFIGURACIÓN ===
DEFAULT_THREADS = 150
TIMEOUT_BASIC = 5      # Timeout para test básico
TIMEOUT_LIVE = 8       # Timeout para login.live.com

# === CONTADORES THREAD-SAFE ===
lock = threading.Lock()
stats = {
    'total': 0,
    'alive': 0,
    'live_ok': 0,
    'dead': 0,
    'checked': 0
}

# === LISTAS DE RESULTADOS ===
alive_proxies = []
live_proxies = []

def banner():
    print(f"""{colorama.Fore.LIGHTCYAN_EX}
╔══════════════════════════════════════════════════════╗
║          Proxy Checker v1.0 - High Speed             ║
║   Test: Alive + login.live.com compatibility         ║
╚══════════════════════════════════════════════════════╝
{colorama.Fore.RESET}""")

def fetch_proxies_from_api():
    """Obtener proxies de ProxyScrape API."""
    proxies = []
    try:
        print(f"{colorama.Fore.LIGHTYELLOW_EX}[*] Obteniendo proxies de ProxyScrape API...{colorama.Fore.RESET}")
        url = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            for line in resp.text.strip().split('\n'):
                line = line.strip()
                if line and ':' in line:
                    proxies.append(line)
        print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Obtenidos {len(proxies)} proxies de API{colorama.Fore.RESET}")
    except Exception as e:
        print(f"{colorama.Fore.LIGHTRED_EX}[-] Error API: {e}{colorama.Fore.RESET}")
    return proxies

def fetch_proxies_from_web():
    """Obtener proxies de free-proxy-list.net."""
    proxies = []
    try:
        print(f"{colorama.Fore.LIGHTYELLOW_EX}[*] Obteniendo proxies de free-proxy-list.net...{colorama.Fore.RESET}")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get('https://free-proxy-list.net/', headers=headers, timeout=15)
        if resp.status_code == 200:
            pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})</td><td>(\d+)'
            matches = re.findall(pattern, resp.text)
            for ip, port in matches:
                proxies.append(f"{ip}:{port}")
        print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Obtenidos {len(proxies)} proxies de la web{colorama.Fore.RESET}")
    except Exception as e:
        print(f"{colorama.Fore.LIGHTRED_EX}[-] Error web: {e}{colorama.Fore.RESET}")
    return proxies

def fetch_proxies_from_sslproxies():
    """Obtener proxies de sslproxies.org."""
    proxies = []
    try:
        print(f"{colorama.Fore.LIGHTYELLOW_EX}[*] Obteniendo proxies de sslproxies.org...{colorama.Fore.RESET}")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get('https://www.sslproxies.org/', headers=headers, timeout=15)
        if resp.status_code == 200:
            pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})</td><td>(\d+)'
            matches = re.findall(pattern, resp.text)
            for ip, port in matches:
                proxies.append(f"{ip}:{port}")
        print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Obtenidos {len(proxies)} proxies SSL{colorama.Fore.RESET}")
    except Exception as e:
        print(f"{colorama.Fore.LIGHTRED_EX}[-] Error SSL: {e}{colorama.Fore.RESET}")
    return proxies

def load_proxies_from_file(filepath):
    """Cargar proxies desde archivo."""
    proxies = []
    try:
        full_path = os.path.join(SCRIPT_DIR, filepath)
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line and ':' in line:
                    # Limpiar formato ip:port
                    match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)', line)
                    if match:
                        proxies.append(f"{match.group(1)}:{match.group(2)}")
        print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Cargados {len(proxies)} proxies de {filepath}{colorama.Fore.RESET}")
    except FileNotFoundError:
        print(f"{colorama.Fore.LIGHTRED_EX}[-] Archivo no encontrado: {filepath}{colorama.Fore.RESET}")
    except Exception as e:
        print(f"{colorama.Fore.LIGHTRED_EX}[-] Error: {e}{colorama.Fore.RESET}")
    return proxies

def check_proxy_alive(proxy):
    """Test básico - verificar si el proxy responde."""
    try:
        proxies = {
            'http': f'http://{proxy}',
            'https': f'http://{proxy}'
        }
        # Test con httpbin o google
        resp = requests.get(
            'http://httpbin.org/ip',
            proxies=proxies,
            timeout=TIMEOUT_BASIC
        )
        return resp.status_code == 200
    except:
        return False

def check_proxy_live(proxy):
    """Test avanzado - verificar si funciona con login.live.com."""
    try:
        proxies = {
            'http': f'http://{proxy}',
            'https': f'http://{proxy}'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        resp = requests.get(
            'https://login.live.com/login.srf',
            headers=headers,
            proxies=proxies,
            timeout=TIMEOUT_LIVE,
            allow_redirects=True
        )
        # Debe contener el formulario de login
        return resp.status_code == 200 and ('PPFT' in resp.text or 'login' in resp.text.lower())
    except:
        return False

def check_proxy(proxy, test_live=True):
    """Verificar un proxy completo."""
    global stats, alive_proxies, live_proxies
    
    with lock:
        stats['checked'] += 1
        current = stats['checked']
    
    # Test 1: Proxy viva
    is_alive = check_proxy_alive(proxy)
    
    if not is_alive:
        with lock:
            stats['dead'] += 1
        print(f"{colorama.Fore.LIGHTBLACK_EX}[{current:04d}] ❌ DEAD: {proxy}{colorama.Fore.RESET}")
        return
    
    with lock:
        stats['alive'] += 1
        alive_proxies.append(proxy)
    
    if not test_live:
        print(f"{colorama.Fore.LIGHTGREEN_EX}[{current:04d}] ✅ ALIVE: {proxy}{colorama.Fore.RESET}")
        return
    
    # Test 2: Compatible con login.live.com
    is_live_ok = check_proxy_live(proxy)
    
    if is_live_ok:
        with lock:
            stats['live_ok'] += 1
            live_proxies.append(proxy)
        print(f"{colorama.Fore.LIGHTGREEN_EX}[{current:04d}] ✅ LIVE OK: {proxy}{colorama.Fore.RESET}")
    else:
        print(f"{colorama.Fore.LIGHTYELLOW_EX}[{current:04d}] ⚠️ ALIVE (no live): {proxy}{colorama.Fore.RESET}")

def save_results():
    """Guardar resultados en archivos."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    # Guardar proxies vivas
    if alive_proxies:
        filename = f"proxies_alive_{timestamp}.txt"
        with open(os.path.join(SCRIPT_DIR, filename), 'w') as f:
            for p in alive_proxies:
                f.write(f"{p}\n")
        print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Guardadas {len(alive_proxies)} proxies vivas en {filename}{colorama.Fore.RESET}")
    
    # Guardar proxies compatibles con login.live.com
    if live_proxies:
        filename = f"proxies_live_{timestamp}.txt"
        with open(os.path.join(SCRIPT_DIR, filename), 'w') as f:
            for p in live_proxies:
                f.write(f"{p}\n")
        print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Guardadas {len(live_proxies)} proxies LIVE en {filename}{colorama.Fore.RESET}")
        
        # También guardar como proxies.txt para uso directo
        with open(os.path.join(SCRIPT_DIR, "proxies.txt"), 'w') as f:
            for p in live_proxies:
                f.write(f"{p}\n")
        print(f"{colorama.Fore.LIGHTCYAN_EX}[+] Copiadas a proxies.txt para uso directo{colorama.Fore.RESET}")

def setup_proxies():
    """Configurar origen de proxies."""
    print(f"\n{colorama.Fore.LIGHTYELLOW_EX}=== Origen de Proxies ==={colorama.Fore.RESET}")
    print("1) Cargar desde archivo local")
    print("2) ProxyScrape API (~900+) [RECOMENDADO]")
    print("3) free-proxy-list.net (~300)")
    print("4) sslproxies.org (~100)")
    print("5) Todas las fuentes web (API + web + SSL)")
    
    choice = input(f"\n{colorama.Fore.LIGHTYELLOW_EX}Selecciona (1-5) [default: 2]: {colorama.Fore.RESET}").strip() or "2"
    
    proxies = []
    
    if choice == "1":
        filepath = input(f"{colorama.Fore.LIGHTYELLOW_EX}Archivo [proxies_raw.txt]: {colorama.Fore.RESET}").strip() or "proxies_raw.txt"
        proxies = load_proxies_from_file(filepath)
    
    elif choice == "2":
        proxies = fetch_proxies_from_api()
    
    elif choice == "3":
        proxies = fetch_proxies_from_web()
    
    elif choice == "4":
        proxies = fetch_proxies_from_sslproxies()
    
    elif choice == "5":
        proxies = fetch_proxies_from_api()
        proxies.extend(fetch_proxies_from_web())
        proxies.extend(fetch_proxies_from_sslproxies())
    
    # Eliminar duplicados
    proxies = list(dict.fromkeys(proxies))
    print(f"{colorama.Fore.LIGHTCYAN_EX}[+] Total proxies únicas: {len(proxies)}{colorama.Fore.RESET}")
    
    return proxies

def main():
    global stats
    
    banner()
    
    # Obtener proxies
    proxies = setup_proxies()
    
    if not proxies:
        print(f"{colorama.Fore.LIGHTRED_EX}[-] No hay proxies para verificar{colorama.Fore.RESET}")
        return
    
    stats['total'] = len(proxies)
    
    # Configurar test
    print(f"\n{colorama.Fore.LIGHTYELLOW_EX}=== Configuración del Test ==={colorama.Fore.RESET}")
    test_live = input(f"¿Verificar compatibilidad con login.live.com? (S/n): ").strip().lower() != 'n'
    
    threads = input(f"Threads [{DEFAULT_THREADS}]: ").strip()
    threads = int(threads) if threads.isdigit() else DEFAULT_THREADS
    
    print(f"\n{colorama.Fore.LIGHTCYAN_EX}[*] Iniciando verificación con {threads} threads...{colorama.Fore.RESET}")
    print(f"{colorama.Fore.LIGHTCYAN_EX}[*] Test login.live.com: {'SI' if test_live else 'NO'}{colorama.Fore.RESET}")
    print(f"{colorama.Fore.LIGHTCYAN_EX}[*] Total a verificar: {len(proxies)}{colorama.Fore.RESET}\n")
    
    start_time = time.time()
    
    try:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {executor.submit(check_proxy, proxy, test_live): proxy for proxy in proxies}
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    pass
                    
    except KeyboardInterrupt:
        print(f"\n{colorama.Fore.LIGHTYELLOW_EX}[!] Interrumpido por usuario{colorama.Fore.RESET}")
    
    elapsed = time.time() - start_time
    
    # Mostrar resultados
    print(f"\n{colorama.Fore.LIGHTCYAN_EX}{'='*60}{colorama.Fore.RESET}")
    print(f"{colorama.Fore.LIGHTGREEN_EX}✅ Vivas: {stats['alive']}{colorama.Fore.RESET}")
    if test_live:
        print(f"{colorama.Fore.LIGHTGREEN_EX}🌐 Login.live.com OK: {stats['live_ok']}{colorama.Fore.RESET}")
    print(f"{colorama.Fore.LIGHTRED_EX}❌ Muertas: {stats['dead']}{colorama.Fore.RESET}")
    print(f"{colorama.Fore.LIGHTWHITE_EX}📊 Total verificadas: {stats['checked']}/{stats['total']}{colorama.Fore.RESET}")
    print(f"{colorama.Fore.LIGHTWHITE_EX}⏱️ Tiempo: {elapsed:.1f}s ({stats['checked']/max(elapsed,1):.1f} proxies/seg){colorama.Fore.RESET}")
    print(f"{colorama.Fore.LIGHTCYAN_EX}{'='*60}{colorama.Fore.RESET}")
    
    # Guardar resultados
    save_results()
    
    print(f"\n{colorama.Fore.LIGHTGREEN_EX}[✓] Completado! Usa proxies.txt con Microsoft_v2.py{colorama.Fore.RESET}")

if __name__ == "__main__":
    main()
