#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║             Proxy Checker v2.1 — Async Engine                ║
║  • 20+ fuentes  • SOCKS4/5 + HTTP/S  • Scoring inteligente  ║
║  • 500+ conexiones async  • Geoloc  • Proxy Pool rotativo   ║
╚══════════════════════════════════════════════════════════════╝

Autor: Psico777
Licencia: MIT
Repo:   https://github.com/Psico777/ComprobadorProxies
"""

import os
import sys
import re
import json
import csv
import time
import asyncio
import random
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Set, Tuple
from enum import Enum

# ── Dependencias externas ──
try:
    import aiohttp
    from aiohttp_socks import ProxyConnector, ProxyType
    import colorama
    from colorama import Fore, Style
except ImportError as e:
    print(f"[!] Dependencia faltante: {e}")
    print("[*] Instala con: pip install aiohttp aiohttp-socks colorama")
    sys.exit(1)

colorama.init()

# ══════════════════════════════════════════════════════════════
#                       CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def safe_input(prompt: str, default: str = "") -> str:
    """Input seguro que no crashea en terminales no interactivas (ej. VS Code Run)."""
    try:
        value = input(prompt).strip()
        return value if value else default
    except (EOFError, KeyboardInterrupt):
        print(f"\n  {Fore.LIGHTYELLOW_EX}(usando valor por defecto: {default}){Fore.RESET}")
        return default


class Config:
    """Configuración central ajustable."""
    MAX_CONCURRENT    = 500
    TIMEOUT_ALIVE     = 6
    TIMEOUT_QUALITY   = 10
    TIMEOUT_FETCH     = 20
    GEO_RATE_LIMIT    = 40        # ip-api.com = 45/min, usamos 40

    LATENCY_EXCELLENT = 1.0
    LATENCY_GOOD      = 2.5
    LATENCY_FAIR      = 5.0

    ALIVE_TEST_URLS = [
        "http://httpbin.org/ip",
        "http://ip-api.com/json",
        "https://api.ipify.org?format=json",
    ]
    QUALITY_TEST_URLS = {
        "login.live.com": "https://login.live.com/login.srf",
        "google.com":     "https://www.google.com/",
        "cloudflare":     "https://1.1.1.1/cdn-cgi/trace",
    }

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 OPR/105.0.0.0",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
    ]


# ══════════════════════════════════════════════════════════════
#                       MODELOS DE DATOS
# ══════════════════════════════════════════════════════════════

class ProxyProtocol(Enum):
    HTTP   = "http"
    HTTPS  = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class AnonLevel(Enum):
    TRANSPARENT = "transparent"
    ANONYMOUS   = "anonymous"
    ELITE       = "elite"
    UNKNOWN     = "unknown"


class QualityTier(Enum):
    PREMIUM  = "⭐ PREMIUM"
    HIGH     = "🟢 HIGH"
    MEDIUM   = "🟡 MEDIUM"
    LOW      = "🔴 LOW"


@dataclass
class ProxyResult:
    """Resultado completo de un proxy verificado."""
    ip: str
    port: int
    protocol: ProxyProtocol = ProxyProtocol.HTTP
    alive: bool = False
    latency_ms: float = 0.0
    anon_level: AnonLevel = AnonLevel.UNKNOWN
    country: str = "??"
    country_name: str = "Unknown"
    org: str = ""
    score: int = 0
    quality: QualityTier = QualityTier.LOW
    targets_ok: List[str] = field(default_factory=list)
    last_checked: str = ""
    error: str = ""

    @property
    def address(self) -> str:
        return f"{self.ip}:{self.port}"

    @property
    def url(self) -> str:
        return f"{self.protocol.value}://{self.ip}:{self.port}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d['protocol'] = self.protocol.value
        d['anon_level'] = self.anon_level.value
        d['quality'] = self.quality.value
        return d


# ══════════════════════════════════════════════════════════════
#                   ESTADÍSTICAS EN TIEMPO REAL
# ══════════════════════════════════════════════════════════════

class Stats:
    """Contadores async-safe."""
    def __init__(self):
        self.lock = asyncio.Lock()
        self.total = 0
        self.checked = 0
        self.alive = 0
        self.dead = 0
        self.premium = 0
        self.high = 0
        self.medium = 0
        self.low = 0
        self.by_protocol = defaultdict(int)
        self.by_country = defaultdict(int)
        self.start_time = 0.0

    async def inc(self, field_name: str, protocol: str = "", country: str = ""):
        async with self.lock:
            setattr(self, field_name, getattr(self, field_name) + 1)
            if protocol:
                self.by_protocol[protocol] += 1
            if country:
                self.by_country[country] += 1

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time if self.start_time else 0

    @property
    def speed(self) -> float:
        e = self.elapsed
        return self.checked / e if e > 0 else 0


# ══════════════════════════════════════════════════════════════
#                  FUENTES DE PROXIES (20+)
# ══════════════════════════════════════════════════════════════

class ProxyFetcher:
    """Descarga proxies de 20+ fuentes en paralelo."""

    # (url, protocolo, tipo_fuente)  —  tipo: "api" o "github"
    SOURCES = {
        # ═══ APIs DIRECTAS ═══
        "ProxyScrape HTTP": (
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
            ProxyProtocol.HTTP, "api"
        ),
        "ProxyScrape SOCKS4": (
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=10000&country=all",
            ProxyProtocol.SOCKS4, "api"
        ),
        "ProxyScrape SOCKS5": (
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000&country=all",
            ProxyProtocol.SOCKS5, "api"
        ),
        "Geonode Free P1": (
            "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc",
            ProxyProtocol.HTTP, "api"
        ),
        "Geonode Free P2": (
            "https://proxylist.geonode.com/api/proxy-list?limit=500&page=2&sort_by=lastChecked&sort_type=desc",
            ProxyProtocol.HTTP, "api"
        ),
        "OpenProxyList HTTP": (
            "https://api.openproxylist.xyz/http.txt",
            ProxyProtocol.HTTP, "api"
        ),
        "OpenProxyList SOCKS4": (
            "https://api.openproxylist.xyz/socks4.txt",
            ProxyProtocol.SOCKS4, "api"
        ),
        "OpenProxyList SOCKS5": (
            "https://api.openproxylist.xyz/socks5.txt",
            ProxyProtocol.SOCKS5, "api"
        ),

        # ═══ GITHUB REPOS ═══
        "TheSpeedX HTTP": (
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            ProxyProtocol.HTTP, "github"
        ),
        "TheSpeedX SOCKS4": (
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
            ProxyProtocol.SOCKS4, "github"
        ),
        "TheSpeedX SOCKS5": (
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
            ProxyProtocol.SOCKS5, "github"
        ),
        "monosans HTTP": (
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
            ProxyProtocol.HTTP, "github"
        ),
        "monosans SOCKS4": (
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
            ProxyProtocol.SOCKS4, "github"
        ),
        "monosans SOCKS5": (
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
            ProxyProtocol.SOCKS5, "github"
        ),
        "clarketm HTTP": (
            "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
            ProxyProtocol.HTTP, "github"
        ),
        "jetkai HTTP": (
            "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
            ProxyProtocol.HTTP, "github"
        ),
        "jetkai HTTPS": (
            "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt",
            ProxyProtocol.HTTPS, "github"
        ),
        "jetkai SOCKS4": (
            "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks4.txt",
            ProxyProtocol.SOCKS4, "github"
        ),
        "jetkai SOCKS5": (
            "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
            ProxyProtocol.SOCKS5, "github"
        ),
        "hookzof SOCKS5": (
            "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
            ProxyProtocol.SOCKS5, "github"
        ),
        "roosterkid HTTPS": (
            "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
            ProxyProtocol.HTTPS, "github"
        ),
        "ErcinDedeworken S5": (
            "https://raw.githubusercontent.com/ErcinDedeworken/topfreeproxies/master/socks5.txt",
            ProxyProtocol.SOCKS5, "github"
        ),
        "MuRongPIG HTTP": (
            "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt",
            ProxyProtocol.HTTP, "github"
        ),
        "MuRongPIG SOCKS4": (
            "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks4.txt",
            ProxyProtocol.SOCKS4, "github"
        ),
        "MuRongPIG SOCKS5": (
            "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks5.txt",
            ProxyProtocol.SOCKS5, "github"
        ),
        "prxchk HTTP": (
            "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
            ProxyProtocol.HTTP, "github"
        ),
        "prxchk SOCKS5": (
            "https://raw.githubusercontent.com/prxchk/proxy-list/main/socks5.txt",
            ProxyProtocol.SOCKS5, "github"
        ),
    }

    @staticmethod
    def _parse_ip_port(text: str) -> List[str]:
        pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{2,5})'
        return [f"{m[0]}:{m[1]}" for m in re.findall(pattern, text)]

    @staticmethod
    async def _fetch_one(session: aiohttp.ClientSession, name: str, url: str,
                         protocol: ProxyProtocol) -> List[Tuple[str, ProxyProtocol]]:
        results = []
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=Config.TIMEOUT_FETCH)) as resp:
                if resp.status != 200:
                    print(f"  {Fore.LIGHTRED_EX}[✗] {name:30s} → HTTP {resp.status}{Fore.RESET}")
                    return results
                text = await resp.text()

                if "geonode" in name.lower():
                    try:
                        data = json.loads(text)
                        for p in data.get("data", []):
                            ip = p.get("ip", "")
                            port = p.get("port", "")
                            protos = p.get("protocols", ["http"])
                            if ip and port:
                                proto = ProxyProtocol.SOCKS5 if "socks5" in protos \
                                    else ProxyProtocol.SOCKS4 if "socks4" in protos \
                                    else ProxyProtocol.HTTPS if "https" in protos \
                                    else ProxyProtocol.HTTP
                                results.append((f"{ip}:{port}", proto))
                    except json.JSONDecodeError:
                        pass
                else:
                    for addr in ProxyFetcher._parse_ip_port(text):
                        results.append((addr, protocol))

            count = len(results)
            color = Fore.LIGHTGREEN_EX if count > 0 else Fore.LIGHTRED_EX
            print(f"  {color}[{'✓' if count else '✗'}] {name:30s} → {count:5d} proxies{Fore.RESET}")

        except asyncio.TimeoutError:
            print(f"  {Fore.LIGHTRED_EX}[✗] {name:30s} → timeout{Fore.RESET}")
        except Exception as e:
            print(f"  {Fore.LIGHTRED_EX}[✗] {name:30s} → {str(e)[:50]}{Fore.RESET}")
        return results

    @classmethod
    async def fetch_all(cls, protocols_filter: Optional[Set[ProxyProtocol]] = None,
                        source_type_filter: Optional[str] = None) -> Dict[str, ProxyProtocol]:
        active = {
            name: (url, proto, stype) for name, (url, proto, stype) in cls.SOURCES.items()
            if (not protocols_filter or proto in protocols_filter)
            and (not source_type_filter or stype == source_type_filter)
        }

        print(f"\n{Fore.LIGHTCYAN_EX}{'═'*60}")
        print(f"  📡  DESCARGANDO PROXIES DE {len(active)} FUENTES")
        print(f"{'═'*60}{Fore.RESET}\n")

        proxies: Dict[str, ProxyProtocol] = {}

        async with aiohttp.ClientSession(
            headers={"User-Agent": random.choice(Config.USER_AGENTS)}
        ) as session:
            tasks = [cls._fetch_one(session, n, u, p) for n, (u, p, _) in active.items()]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    continue
                for addr, proto in result:
                    if addr not in proxies:
                        proxies[addr] = proto

        print(f"\n{Fore.LIGHTCYAN_EX}  📊  Total proxies únicas: {len(proxies)}{Fore.RESET}")
        by_proto = defaultdict(int)
        for proto in proxies.values():
            by_proto[proto.value] += 1
        for proto, count in sorted(by_proto.items()):
            print(f"      {proto.upper():8s} → {count}")

        return proxies

    @staticmethod
    def load_from_file(filepath: str) -> Dict[str, ProxyProtocol]:
        proxies = {}
        try:
            full_path = os.path.join(SCRIPT_DIR, filepath) if not os.path.isabs(filepath) else filepath
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)', line)
                    if match:
                        addr = f"{match.group(1)}:{match.group(2)}"
                        lower = line.lower()
                        if "socks5" in lower:
                            proto = ProxyProtocol.SOCKS5
                        elif "socks4" in lower:
                            proto = ProxyProtocol.SOCKS4
                        elif "https" in lower:
                            proto = ProxyProtocol.HTTPS
                        else:
                            proto = ProxyProtocol.HTTP
                        proxies[addr] = proto
            print(f"{Fore.LIGHTGREEN_EX}  [+] Archivo: {len(proxies)} proxies de {filepath}{Fore.RESET}")
        except FileNotFoundError:
            print(f"{Fore.LIGHTRED_EX}  [-] Archivo no encontrado: {filepath}{Fore.RESET}")
        except Exception as e:
            print(f"{Fore.LIGHTRED_EX}  [-] Error: {e}{Fore.RESET}")
        return proxies


# ══════════════════════════════════════════════════════════════
#              MOTOR DE VERIFICACIÓN ASYNC
# ══════════════════════════════════════════════════════════════

class ProxyChecker:
    """Motor async de alta velocidad para verificar proxies."""

    def __init__(self, stats: Stats, test_targets: Optional[List[str]] = None):
        self.stats = stats
        self.test_targets = test_targets or ["login.live.com"]
        self.my_ip: Optional[str] = None
        self.results: List[ProxyResult] = []
        self._results_lock = asyncio.Lock()
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._geo_semaphore: Optional[asyncio.Semaphore] = None

    async def _detect_my_ip(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.ipify.org?format=json",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    data = await resp.json()
                    self.my_ip = data.get("ip", "")
                    print(f"{Fore.LIGHTYELLOW_EX}  🌐 Tu IP real: {self.my_ip}{Fore.RESET}")
        except Exception:
            print(f"{Fore.LIGHTYELLOW_EX}  ⚠ No se pudo detectar tu IP real{Fore.RESET}")

    def _get_connector(self, protocol: ProxyProtocol, address: str) -> Optional[ProxyConnector]:
        ip, port = address.split(":")
        try:
            if protocol == ProxyProtocol.SOCKS5:
                return ProxyConnector(proxy_type=ProxyType.SOCKS5, host=ip, port=int(port), rdns=True)
            elif protocol == ProxyProtocol.SOCKS4:
                return ProxyConnector(proxy_type=ProxyType.SOCKS4, host=ip, port=int(port), rdns=True)
            return None
        except Exception:
            return None

    async def _test_alive(self, session: aiohttp.ClientSession, address: str,
                          protocol: ProxyProtocol) -> Tuple[bool, float, dict]:
        test_url = random.choice(Config.ALIVE_TEST_URLS)
        headers = {"User-Agent": random.choice(Config.USER_AGENTS)}
        timeout = aiohttp.ClientTimeout(total=Config.TIMEOUT_ALIVE)
        start = time.monotonic()

        try:
            if protocol in (ProxyProtocol.SOCKS4, ProxyProtocol.SOCKS5):
                connector = self._get_connector(protocol, address)
                if not connector:
                    return False, 0, {}
                async with aiohttp.ClientSession(connector=connector) as s:
                    async with s.get(test_url, headers=headers, timeout=timeout) as resp:
                        latency = (time.monotonic() - start) * 1000
                        if resp.status == 200:
                            text = await resp.text()
                            try:
                                return True, latency, json.loads(text)
                            except Exception:
                                return True, latency, {"raw": text[:200]}
            else:
                async with session.get(test_url, headers=headers, timeout=timeout,
                                       proxy=f"http://{address}") as resp:
                    latency = (time.monotonic() - start) * 1000
                    if resp.status == 200:
                        text = await resp.text()
                        try:
                            return True, latency, json.loads(text)
                        except Exception:
                            return True, latency, {"raw": text[:200]}
        except Exception:
            pass
        return False, 0, {}

    def _detect_anonymity(self, resp_data: dict) -> AnonLevel:
        if not self.my_ip or not resp_data:
            return AnonLevel.UNKNOWN

        text = json.dumps(resp_data).lower()
        if self.my_ip in text:
            return AnonLevel.TRANSPARENT

        origin = resp_data.get('origin', '')
        if self.my_ip in origin:
            return AnonLevel.TRANSPARENT

        headers_data = resp_data.get('headers', {})
        if isinstance(headers_data, dict):
            for h in ['x-forwarded-for', 'via', 'x-real-ip', 'forwarded']:
                if h in [k.lower() for k in headers_data.keys()]:
                    if self.my_ip in str(headers_data.get(h, '')):
                        return AnonLevel.TRANSPARENT
                    return AnonLevel.ANONYMOUS

        return AnonLevel.ELITE

    async def _test_quality_target(self, session: aiohttp.ClientSession, address: str,
                                   protocol: ProxyProtocol,
                                   target_name: str, target_url: str) -> bool:
        headers = {
            "User-Agent": random.choice(Config.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        timeout = aiohttp.ClientTimeout(total=Config.TIMEOUT_QUALITY)

        try:
            if protocol in (ProxyProtocol.SOCKS4, ProxyProtocol.SOCKS5):
                connector = self._get_connector(protocol, address)
                if not connector:
                    return False
                async with aiohttp.ClientSession(connector=connector) as s:
                    async with s.get(target_url, headers=headers,
                                     timeout=timeout, allow_redirects=True) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            if target_name == "login.live.com":
                                return 'PPFT' in text or 'login' in text.lower()
                            return len(text) > 100
            else:
                async with session.get(target_url, headers=headers, timeout=timeout,
                                       proxy=f"http://{address}", allow_redirects=True) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        if target_name == "login.live.com":
                            return 'PPFT' in text or 'login' in text.lower()
                        return len(text) > 100
        except Exception:
            pass
        return False

    async def _get_geolocation(self, ip: str) -> Tuple[str, str, str]:
        async with self._geo_semaphore:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"http://ip-api.com/json/{ip}?fields=countryCode,country,org",
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return (data.get("countryCode", "??"),
                                    data.get("country", "Unknown"),
                                    data.get("org", ""))
                        elif resp.status == 429:
                            await asyncio.sleep(1)
            except Exception:
                pass
            return "??", "Unknown", ""

    def _calculate_score(self, result: ProxyResult) -> int:
        score = 0
        lat_s = result.latency_ms / 1000.0
        if lat_s <= Config.LATENCY_EXCELLENT:
            score += 35
        elif lat_s <= Config.LATENCY_GOOD:
            score += 25
        elif lat_s <= Config.LATENCY_FAIR:
            score += 15
        else:
            score += 5

        score += {AnonLevel.ELITE: 30, AnonLevel.ANONYMOUS: 20,
                  AnonLevel.TRANSPARENT: 5, AnonLevel.UNKNOWN: 10}.get(result.anon_level, 0)

        score += {ProxyProtocol.SOCKS5: 10, ProxyProtocol.SOCKS4: 7,
                  ProxyProtocol.HTTPS: 8, ProxyProtocol.HTTP: 5}.get(result.protocol, 0)

        if result.targets_ok:
            score += min(25, len(result.targets_ok) * 8)

        return min(100, score)

    def _classify(self, score: int) -> QualityTier:
        if score >= 80: return QualityTier.PREMIUM
        if score >= 60: return QualityTier.HIGH
        if score >= 40: return QualityTier.MEDIUM
        return QualityTier.LOW

    async def _check_one(self, session: aiohttp.ClientSession,
                         address: str, protocol: ProxyProtocol) -> Optional[ProxyResult]:
        async with self._semaphore:
            ip, port_str = address.split(":")
            result = ProxyResult(
                ip=ip, port=int(port_str), protocol=protocol,
                last_checked=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            alive, latency, resp_data = await self._test_alive(session, address, protocol)
            await self.stats.inc('checked')
            current = self.stats.checked

            if current % 250 == 0:
                pct = (current / max(self.stats.total, 1)) * 100
                print(
                    f"  {Fore.LIGHTBLACK_EX}── progreso: {current}/{self.stats.total} "
                    f"({pct:.0f}%) | ✅ {self.stats.alive} vivas | "
                    f"⏱ {self.stats.speed:.0f}/seg ──{Fore.RESET}"
                )

            if not alive:
                await self.stats.inc('dead')
                return None

            result.alive = True
            result.latency_ms = round(latency, 1)
            await self.stats.inc('alive', protocol.value)

            result.anon_level = self._detect_anonymity(resp_data)

            result.country, result.country_name, result.org = await self._get_geolocation(ip)
            if result.country != "??":
                async with self.stats.lock:
                    self.stats.by_country[result.country] += 1

            for target_name in self.test_targets:
                if target_name in Config.QUALITY_TEST_URLS:
                    url = Config.QUALITY_TEST_URLS[target_name]
                    if await self._test_quality_target(session, address, protocol, target_name, url):
                        result.targets_ok.append(target_name)

            result.score = self._calculate_score(result)
            result.quality = self._classify(result.score)

            tier_map = {QualityTier.PREMIUM: 'premium', QualityTier.HIGH: 'high',
                        QualityTier.MEDIUM: 'medium', QualityTier.LOW: 'low'}
            await self.stats.inc(tier_map[result.quality])

            # Print proxy viva
            anon_icon = {"elite": "🛡️", "anonymous": "🔒", "transparent": "👁️", "unknown": "❓"}
            proto_color = {"http": Fore.LIGHTWHITE_EX, "https": Fore.LIGHTCYAN_EX,
                           "socks4": Fore.LIGHTMAGENTA_EX, "socks5": Fore.LIGHTYELLOW_EX}
            qcolor = {QualityTier.PREMIUM: Fore.LIGHTGREEN_EX, QualityTier.HIGH: Fore.GREEN,
                      QualityTier.MEDIUM: Fore.LIGHTYELLOW_EX, QualityTier.LOW: Fore.LIGHTRED_EX}

            targets = ",".join(result.targets_ok) if result.targets_ok else "—"
            print(
                f"  {qcolor.get(result.quality, Fore.WHITE)}[{current:05d}] "
                f"{result.quality.value} "
                f"{proto_color.get(protocol.value, Fore.WHITE)}{protocol.value.upper():6s}{Fore.RESET} "
                f"{address:21s} "
                f"{anon_icon.get(result.anon_level.value, '❓')} {result.anon_level.value:12s} "
                f"🌍 {result.country:2s} "
                f"⏱ {result.latency_ms:7.0f}ms "
                f"📊 {result.score:3d}/100 "
                f"🎯 {targets}{Fore.RESET}"
            )

            async with self._results_lock:
                self.results.append(result)
            return result

    async def check_all(self, proxies: Dict[str, ProxyProtocol]):
        self._semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT)
        self._geo_semaphore = asyncio.Semaphore(Config.GEO_RATE_LIMIT)
        self.stats.total = len(proxies)
        self.stats.start_time = time.time()

        print(f"\n{Fore.LIGHTCYAN_EX}{'═'*60}")
        print(f"  ⚡  VERIFICACIÓN ASYNC — {Config.MAX_CONCURRENT} conexiones")
        print(f"{'═'*60}{Fore.RESET}")

        await self._detect_my_ip()
        targets_str = ", ".join(self.test_targets) if self.test_targets else "solo vida"
        print(f"  📋 Total: {len(proxies)} | Targets: {targets_str}")
        print(f"  ⏳ Iniciando...\n")

        tcp_conn = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300, ssl=False)
        async with aiohttp.ClientSession(connector=tcp_conn) as session:
            tasks = [self._check_one(session, addr, proto) for addr, proto in proxies.items()]
            await asyncio.gather(*tasks, return_exceptions=True)


# ══════════════════════════════════════════════════════════════
#              PROXY POOL — ROTACIÓN INTELIGENTE
# ══════════════════════════════════════════════════════════════

class ProxyPool:
    """Pool rotativo para integrar con scrapers y otras herramientas."""

    def __init__(self, proxies: List[ProxyResult]):
        self._all = sorted(proxies, key=lambda p: p.score, reverse=True)
        self._index = 0
        self._by_protocol: Dict[str, List[ProxyResult]] = defaultdict(list)
        self._by_quality: Dict[str, List[ProxyResult]] = defaultdict(list)
        self._by_country: Dict[str, List[ProxyResult]] = defaultdict(list)
        for p in self._all:
            self._by_protocol[p.protocol.value].append(p)
            self._by_quality[p.quality.value].append(p)
            self._by_country[p.country].append(p)

    def get_next(self, protocol: Optional[str] = None,
                 min_score: int = 0, country: Optional[str] = None) -> Optional[ProxyResult]:
        pool = self._all
        if protocol:
            pool = self._by_protocol.get(protocol, [])
        if country:
            pool = [p for p in pool if p.country == country]
        pool = [p for p in pool if p.score >= min_score]
        if not pool:
            return None
        proxy = pool[self._index % len(pool)]
        self._index += 1
        return proxy

    def get_random(self, min_score: int = 60) -> Optional[ProxyResult]:
        good = [p for p in self._all if p.score >= min_score]
        return random.choice(good) if good else None

    def get_best(self, n: int = 10) -> List[ProxyResult]:
        return self._all[:n]

    @property
    def summary(self) -> dict:
        return {
            "total": len(self._all),
            "by_protocol": {k: len(v) for k, v in self._by_protocol.items()},
            "by_quality": {k: len(v) for k, v in self._by_quality.items()},
            "top_countries": dict(sorted(
                {k: len(v) for k, v in self._by_country.items()}.items(),
                key=lambda x: x[1], reverse=True)[:10]),
            "avg_score": round(sum(p.score for p in self._all) / max(len(self._all), 1), 1),
            "avg_latency": round(sum(p.latency_ms for p in self._all) / max(len(self._all), 1), 1),
        }


# ══════════════════════════════════════════════════════════════
#                 EXPORTADOR DE RESULTADOS
# ══════════════════════════════════════════════════════════════

class ProxyExporter:
    """Exporta separando por protocolo (http.txt, socks5.txt...) y por calidad."""

    @staticmethod
    def _save_txt(proxies: List[ProxyResult], filepath: str, header: str = ""):
        with open(filepath, 'w', encoding='utf-8') as f:
            if header:
                f.write(f"# {header}\n")
                f.write(f"# Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Total: {len(proxies)}\n\n")
            for p in proxies:
                f.write(f"{p.address}\n")

    @staticmethod
    def _save_detailed_txt(proxies: List[ProxyResult], filepath: str, header: str = ""):
        with open(filepath, 'w', encoding='utf-8') as f:
            if header:
                f.write(f"# {header}\n")
                f.write(f"# Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"{'PROTO':6s} | {'DIRECCIÓN':21s} | {'SCORE':5s} | {'ANONIMATO':12s} | "
                    f"{'CC':2s} | {'LATENCIA':8s} | TARGETS\n")
            f.write(f"{'-'*90}\n")
            for p in proxies:
                targets = ",".join(p.targets_ok) if p.targets_ok else "none"
                f.write(f"{p.protocol.value:6s} | {p.address:21s} | "
                        f"{p.score:5d} | {p.anon_level.value:12s} | "
                        f"{p.country:2s} | {p.latency_ms:6.0f}ms | {targets}\n")

    @staticmethod
    def _save_json(proxies: List[ProxyResult], filepath: str):
        data = {"generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total": len(proxies), "proxies": [p.to_dict() for p in proxies]}
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _save_csv(proxies: List[ProxyResult], filepath: str):
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(["ip", "port", "protocol", "score", "quality", "latency_ms",
                         "anon_level", "country", "org", "targets_ok", "last_checked"])
            for p in proxies:
                w.writerow([p.ip, p.port, p.protocol.value, p.score, p.quality.value,
                            p.latency_ms, p.anon_level.value, p.country, p.org,
                            "|".join(p.targets_ok), p.last_checked])

    @classmethod
    def export_all(cls, results: List[ProxyResult]):
        if not results:
            print(f"{Fore.LIGHTRED_EX}  [!] No hay proxies para exportar{Fore.RESET}")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = os.path.join(RESULTS_DIR, timestamp)
        os.makedirs(session_dir, exist_ok=True)
        saved = []

        # 1. Todas las vivas
        cls._save_txt(results, os.path.join(session_dir, "all_alive.txt"),
                      "Todas las proxies vivas")
        saved.append(("all_alive.txt", len(results)))

        # 2. SEPARADAS POR PROTOCOLO → http.txt, https.txt, socks4.txt, socks5.txt
        by_proto = defaultdict(list)
        for p in results:
            by_proto[p.protocol.value].append(p)

        for proto, plist in sorted(by_proto.items()):
            plist_sorted = sorted(plist, key=lambda x: x.score, reverse=True)
            fname = f"{proto}.txt"
            cls._save_txt(plist_sorted, os.path.join(session_dir, fname),
                          f"Proxies {proto.upper()} ordenadas por score")
            saved.append((fname, len(plist_sorted)))

        # 3. Por calidad
        for tier in QualityTier:
            tier_proxies = sorted([p for p in results if p.quality == tier],
                                  key=lambda x: x.score, reverse=True)
            if tier_proxies:
                fname = f"quality_{tier.name.lower()}.txt"
                cls._save_txt(tier_proxies, os.path.join(session_dir, fname),
                              f"Proxies {tier.value}")
                saved.append((fname, len(tier_proxies)))

        # 4. HQ Elite
        hq = sorted([p for p in results if p.score >= 60 and p.anon_level == AnonLevel.ELITE],
                     key=lambda x: x.score, reverse=True)
        if hq:
            cls._save_txt(hq, os.path.join(session_dir, "hq_elite.txt"),
                          "HIGH QUALITY ELITE — Score>=60 + Anonimato Elite")
            saved.append(("hq_elite.txt", len(hq)))

        # 5. proxies.txt — mejores para uso directo
        best = sorted(results, key=lambda p: p.score, reverse=True)
        cls._save_txt(best, os.path.join(session_dir, "proxies.txt"),
                      "Todas ordenadas por score")
        cls._save_txt(best, os.path.join(SCRIPT_DIR, "proxies.txt"), "Best Proxies")
        saved.append(("proxies.txt", len(best)))

        # 6-8. Detallado, JSON, CSV
        cls._save_detailed_txt(sorted(results, key=lambda x: x.score, reverse=True),
                               os.path.join(session_dir, "detailed_report.txt"),
                               "Reporte detallado — Proxy Checker v2.1")
        saved.append(("detailed_report.txt", len(results)))

        cls._save_json(results, os.path.join(session_dir, "proxies_full.json"))
        saved.append(("proxies_full.json", len(results)))

        cls._save_csv(results, os.path.join(session_dir, "proxies.csv"))
        saved.append(("proxies.csv", len(results)))

        # Imprimir
        print(f"\n{Fore.LIGHTCYAN_EX}{'═'*60}")
        print(f"  💾  ARCHIVOS GUARDADOS en results/{timestamp}/")
        print(f"{'═'*60}{Fore.RESET}")
        for fname, count in saved:
            icon = "📋" if fname.endswith(".json") else "📊" if fname.endswith(".csv") \
                else "⭐" if "hq" in fname else "🧦" if "socks" in fname \
                else "🔌" if fname in ("http.txt", "https.txt") else "📄"
            print(f"  {Fore.LIGHTGREEN_EX}{icon} {fname:30s} → {count:5d} proxies{Fore.RESET}")
        print(f"  {Fore.LIGHTCYAN_EX}📄 proxies.txt (copia en raíz)  → {len(best):5d} proxies{Fore.RESET}")


# ══════════════════════════════════════════════════════════════
#                       INTERFAZ CLI
# ══════════════════════════════════════════════════════════════

def banner():
    print(f"""{Fore.LIGHTCYAN_EX}
 ██████╗ ██████╗  ██████╗ ██╗  ██╗██╗   ██╗
 ██╔══██╗██╔══██╗██╔═══██╗╚██╗██╔╝╚██╗ ██╔╝
 ██████╔╝██████╔╝██║   ██║ ╚███╔╝  ╚████╔╝
 ██╔═══╝ ██╔══██╗██║   ██║ ██╔██╗   ╚██╔╝
 ██║     ██║  ██║╚██████╔╝██╔╝ ██╗   ██║
 ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝
 {Fore.LIGHTYELLOW_EX}Checker v2.1 — Async Engine{Fore.RESET}
 {Fore.LIGHTWHITE_EX}SOCKS4/5 + HTTP/S │ 20+ Sources │ Smart Scoring{Fore.RESET}
 {Fore.LIGHTBLACK_EX}─────────────────────────────────────────────{Fore.RESET}
""")


async def menu_source() -> Dict[str, ProxyProtocol]:
    """Menú de fuentes (async — evita asyncio.run anidado)."""
    print(f"{Fore.LIGHTYELLOW_EX}  ╔══════════════════════════════════════════════════════════════════════════════╗{Fore.RESET}")
    print(f"  ║  1) 📂 Archivo local        — {Fore.LIGHTBLACK_EX}Carga proxies desde un .txt en tu PC{Fore.RESET}                ║")
    print(f"  ║  2) 🌐 Todas las fuentes    — {Fore.LIGHTBLACK_EX}APIs + GitHub repos (~15,000+ proxies){Fore.RESET}              ║")
    print(f"  ║  3) 🔌 Solo HTTP/HTTPS      — {Fore.LIGHTBLACK_EX}Solo proxies web estándar, sin SOCKS{Fore.RESET}                ║")
    print(f"  ║  4) 🧦 Solo SOCKS4/5        — {Fore.LIGHTBLACK_EX}Proxies SOCKS, más anónimas y estables{Fore.RESET}              ║")
    print(f"  ║  5) ⚡ Solo APIs directas    — {Fore.LIGHTBLACK_EX}ProxyScrape + Geonode + OpenProxy (~3,000){Fore.RESET}          ║")
    print(f"  ║  6) 📦 Solo GitHub repos     — {Fore.LIGHTBLACK_EX}Listas masivas de repositorios públicos (~12,000+){Fore.RESET}  ║")
    print(f"  {Fore.LIGHTYELLOW_EX}╚══════════════════════════════════════════════════════════════════════════════╝{Fore.RESET}")

    choice = safe_input(f"\n  {Fore.LIGHTYELLOW_EX}Selecciona [1-6, default=2]: {Fore.RESET}", "2")

    if choice == "1":
        filepath = safe_input(
            f"  {Fore.LIGHTYELLOW_EX}Ruta del archivo [proxies_raw.txt]: {Fore.RESET}", "proxies_raw.txt")
        return ProxyFetcher.load_from_file(filepath)
    elif choice == "3":
        return await ProxyFetcher.fetch_all(protocols_filter={ProxyProtocol.HTTP, ProxyProtocol.HTTPS})
    elif choice == "4":
        return await ProxyFetcher.fetch_all(protocols_filter={ProxyProtocol.SOCKS4, ProxyProtocol.SOCKS5})
    elif choice == "5":
        return await ProxyFetcher.fetch_all(source_type_filter="api")
    elif choice == "6":
        return await ProxyFetcher.fetch_all(source_type_filter="github")
    else:
        return await ProxyFetcher.fetch_all()


def menu_targets() -> List[str]:
    print(f"\n{Fore.LIGHTYELLOW_EX}  ╔══════════════════════════════════════════════════════════════════════════════╗{Fore.RESET}")
    print(f"  ║  1) 🔐 login.live.com       — {Fore.LIGHTBLACK_EX}Verifica si funciona con login de Microsoft{Fore.RESET}          ║")
    print(f"  ║  2) 🌍 Google + Cloudflare  — {Fore.LIGHTBLACK_EX}Test contra sitios con protección anti-bot{Fore.RESET}           ║")
    print(f"  ║  3) 🎯 Todos los targets    — {Fore.LIGHTBLACK_EX}Live.com + Google + Cloudflare (más completo){Fore.RESET}        ║")
    print(f"  ║  4) ⚡ Solo vida (rápido)   — {Fore.LIGHTBLACK_EX}Solo chequea si la proxy responde, sin targets{Fore.RESET}       ║")
    print(f"  {Fore.LIGHTYELLOW_EX}╚══════════════════════════════════════════════════════════════════════════════╝{Fore.RESET}")

    choice = safe_input(f"\n  {Fore.LIGHTYELLOW_EX}Selecciona [1-4, default=3]: {Fore.RESET}", "3")

    if choice == "1": return ["login.live.com"]
    elif choice == "2": return ["google.com", "cloudflare"]
    elif choice == "3": return list(Config.QUALITY_TEST_URLS.keys())
    else: return []


def menu_concurrency() -> int:
    print(f"\n{Fore.LIGHTYELLOW_EX}  ╔══════════════════════════════════════════════════════════════════════════════╗{Fore.RESET}")
    print(f"  ║  1) 🐢 200  (conservador)   — {Fore.LIGHTBLACK_EX}Conexión lenta o PC con poca RAM{Fore.RESET}                    ║")
    print(f"  ║  2) ⚡ 500  (recomendado)   — {Fore.LIGHTBLACK_EX}Balance ideal entre velocidad y estabilidad{Fore.RESET}          ║")
    print(f"  ║  3) 🚀 800  (agresivo)      — {Fore.LIGHTBLACK_EX}Rápido, requiere buena conexión a internet{Fore.RESET}          ║")
    print(f"  ║  4) 💀 1200 (extremo)       — {Fore.LIGHTBLACK_EX}Máxima velocidad, puede saturar tu red{Fore.RESET}              ║")
    print(f"  {Fore.LIGHTYELLOW_EX}╚══════════════════════════════════════════════════════════════════════════════╝{Fore.RESET}")

    choice = safe_input(f"\n  {Fore.LIGHTYELLOW_EX}Selecciona [1-4, default=2]: {Fore.RESET}", "2")
    return {"1": 200, "2": 500, "3": 800, "4": 1200}.get(choice, 500)


def print_final_report(stats: Stats, results: List[ProxyResult]):
    print(f"\n{Fore.LIGHTCYAN_EX}{'═'*60}")
    print(f"  📊  REPORTE FINAL")
    print(f"{'═'*60}{Fore.RESET}")

    print(f"  {Fore.LIGHTWHITE_EX}⏱  Tiempo total:      {stats.elapsed:.1f}s{Fore.RESET}")
    print(f"  {Fore.LIGHTWHITE_EX}🚀 Velocidad:         {stats.speed:.1f} proxies/seg{Fore.RESET}")
    print(f"  {Fore.LIGHTWHITE_EX}📋 Total verificadas:  {stats.checked}/{stats.total}{Fore.RESET}")
    print()
    print(f"  {Fore.LIGHTGREEN_EX}✅ Vivas:     {stats.alive}{Fore.RESET}")
    print(f"  {Fore.LIGHTRED_EX}❌ Muertas:   {stats.dead}{Fore.RESET}")
    print()
    print(f"  {Fore.LIGHTGREEN_EX}⭐ PREMIUM:   {stats.premium}{Fore.RESET}")
    print(f"  {Fore.GREEN}🟢 HIGH:      {stats.high}{Fore.RESET}")
    print(f"  {Fore.LIGHTYELLOW_EX}🟡 MEDIUM:    {stats.medium}{Fore.RESET}")
    print(f"  {Fore.LIGHTRED_EX}🔴 LOW:       {stats.low}{Fore.RESET}")

    if stats.by_protocol:
        print(f"\n  {Fore.LIGHTCYAN_EX}── Por Protocolo ──{Fore.RESET}")
        for proto, count in sorted(stats.by_protocol.items()):
            print(f"    {proto.upper():8s} → {count}")

    if results:
        countries = defaultdict(int)
        for r in results:
            countries[r.country] += 1
        top = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:8]
        if top:
            print(f"\n  {Fore.LIGHTCYAN_EX}── Top Países ──{Fore.RESET}")
            for c, n in top:
                print(f"    🌍 {c}: {n}")

        avg_score = sum(r.score for r in results) / len(results)
        avg_lat = sum(r.latency_ms for r in results) / len(results)
        best_score = max(r.score for r in results)
        best_lat = min(r.latency_ms for r in results)
        print(f"\n  {Fore.LIGHTCYAN_EX}── Estadísticas ──{Fore.RESET}")
        print(f"    📊 Score promedio:    {avg_score:.1f}/100  (mejor: {best_score})")
        print(f"    ⏱  Latencia promedio: {avg_lat:.0f}ms  (mejor: {best_lat:.0f}ms)")

    print(f"\n{Fore.LIGHTCYAN_EX}{'═'*60}{Fore.RESET}")


# ══════════════════════════════════════════════════════════════
#                         MAIN
# ══════════════════════════════════════════════════════════════

async def async_main():
    banner()

    proxies = await menu_source()
    if not proxies:
        print(f"{Fore.LIGHTRED_EX}  [!] No hay proxies para verificar{Fore.RESET}")
        return

    targets = menu_targets()
    Config.MAX_CONCURRENT = menu_concurrency()

    stats = Stats()
    checker = ProxyChecker(stats, test_targets=targets)

    try:
        await checker.check_all(proxies)
    except KeyboardInterrupt:
        print(f"\n{Fore.LIGHTYELLOW_EX}  [!] Interrumpido por usuario{Fore.RESET}")

    results = checker.results
    print_final_report(stats, results)

    if results:
        ProxyExporter.export_all(results)

        pool = ProxyPool(results)
        summary = pool.summary
        print(f"\n{Fore.LIGHTGREEN_EX}  🔄 ProxyPool listo: {summary['total']} proxies{Fore.RESET}")
        print(f"     Score promedio: {summary['avg_score']}/100 | Latencia: {summary['avg_latency']:.0f}ms")

        best = pool.get_best(5)
        if best:
            print(f"\n  {Fore.LIGHTGREEN_EX}🏆 Top 5 Proxies:{Fore.RESET}")
            for i, p in enumerate(best, 1):
                t = ",".join(p.targets_ok) if p.targets_ok else "—"
                print(f"    {i}. {p.protocol.value.upper():6s} {p.address:21s} "
                      f"Score:{p.score:3d} {p.anon_level.value:12s} "
                      f"{p.country} {p.latency_ms:.0f}ms 🎯{t}")

    print(f"\n{Fore.LIGHTGREEN_EX}  [✓] Completado! Archivos en results/{Fore.RESET}\n")


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print(f"\n{Fore.LIGHTYELLOW_EX}  [!] Saliendo...{Fore.RESET}")


if __name__ == "__main__":
    main()
