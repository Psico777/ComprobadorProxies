#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║              Proxy Checker v2.0 — Async Engine               ║
║  • 12+ fuentes  • SOCKS4/5 + HTTP/S  • Scoring inteligente  ║
║  • 500+ conexiones async  • Geoloc  • Proxy Pool rotativo   ║
╚══════════════════════════════════════════════════════════════╝

Autor: Psico777
Licencia: MIT
"""

import os
import sys
import re
import json
import csv
import time
import asyncio
import random
import signal
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

# Carpeta de resultados
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


class Config:
    """Configuración central ajustable."""
    # ── Rendimiento ──
    MAX_CONCURRENT    = 500        # Conexiones async simultáneas
    TIMEOUT_ALIVE     = 6          # Timeout test de vida (seg)
    TIMEOUT_QUALITY   = 10         # Timeout test de calidad (seg)
    TIMEOUT_FETCH     = 20         # Timeout para descargar listas

    # ── Scoring ──
    LATENCY_EXCELLENT = 1.0        # < 1s   → excelente
    LATENCY_GOOD      = 2.5        # < 2.5s → buena
    LATENCY_FAIR      = 5.0        # < 5s   → aceptable

    # ── Test targets ──
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

    # ── User Agents rotación ──
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
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
    TRANSPARENT = "transparent"   # Tu IP real se filtra
    ANONYMOUS   = "anonymous"     # Oculta IP pero se sabe que es proxy
    ELITE       = "elite"         # Indistinguible de conexión directa
    UNKNOWN     = "unknown"


class QualityTier(Enum):
    PREMIUM  = "⭐ PREMIUM"     # Score ≥ 80
    HIGH     = "🟢 HIGH"        # Score ≥ 60
    MEDIUM   = "🟡 MEDIUM"      # Score ≥ 40
    LOW      = "🔴 LOW"         # Score < 40


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
    """Contadores thread-safe con asyncio.Lock."""
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

    async def inc(self, field: str, protocol: str = "", country: str = ""):
        async with self.lock:
            setattr(self, field, getattr(self, field) + 1)
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
#                   FUENTES DE PROXIES (12+)
# ══════════════════════════════════════════════════════════════

class ProxyFetcher:
    """Descarga proxies de 12+ fuentes en paralelo."""

    # ── Fuentes: (nombre, url, protocolo_default) ──
    SOURCES = {
        # === APIs directas ===
        "ProxyScrape HTTP": (
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
            ProxyProtocol.HTTP
        ),
        "ProxyScrape SOCKS4": (
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=10000&country=all",
            ProxyProtocol.SOCKS4
        ),
        "ProxyScrape SOCKS5": (
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000&country=all",
            ProxyProtocol.SOCKS5
        ),
        "Geonode Free": (
            "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc",
            ProxyProtocol.HTTP  # JSON, parsed separately
        ),

        # === GitHub Repos (raw txt) ===
        "TheSpeedX HTTP": (
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            ProxyProtocol.HTTP
        ),
        "TheSpeedX SOCKS4": (
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
            ProxyProtocol.SOCKS4
        ),
        "TheSpeedX SOCKS5": (
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
            ProxyProtocol.SOCKS5
        ),
        "monosans HTTP": (
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
            ProxyProtocol.HTTP
        ),
        "monosans SOCKS4": (
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
            ProxyProtocol.SOCKS4
        ),
        "monosans SOCKS5": (
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
            ProxyProtocol.SOCKS5
        ),
        "clarketm HTTP": (
            "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
            ProxyProtocol.HTTP
        ),
        "jetkai HTTP": (
            "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
            ProxyProtocol.HTTP
        ),
        "jetkai HTTPS": (
            "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt",
            ProxyProtocol.HTTPS
        ),
        "jetkai SOCKS4": (
            "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks4.txt",
            ProxyProtocol.SOCKS4
        ),
        "jetkai SOCKS5": (
            "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
            ProxyProtocol.SOCKS5
        ),
        "hookzof SOCKS5": (
            "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
            ProxyProtocol.SOCKS5
        ),
    }

    @staticmethod
    def _parse_ip_port(text: str) -> List[str]:
        """Extrae ip:port de texto crudo."""
        pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{2,5})'
        return [f"{m[0]}:{m[1]}" for m in re.findall(pattern, text)]

    @staticmethod
    async def _fetch_one(session: aiohttp.ClientSession, name: str, url: str,
                         protocol: ProxyProtocol) -> List[Tuple[str, ProxyProtocol]]:
        """Descarga una fuente y retorna lista de (ip:port, protocolo)."""
        results = []
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=Config.TIMEOUT_FETCH)) as resp:
                if resp.status != 200:
                    return results
                text = await resp.text()

                # Caso especial: Geonode devuelve JSON
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
                    # Texto plano ip:port
                    for addr in ProxyFetcher._parse_ip_port(text):
                        results.append((addr, protocol))

            count = len(results)
            color = Fore.LIGHTGREEN_EX if count > 0 else Fore.LIGHTRED_EX
            print(f"  {color}[{'✓' if count else '✗'}] {name}: {count} proxies{Fore.RESET}")

        except Exception as e:
            print(f"  {Fore.LIGHTRED_EX}[✗] {name}: {e}{Fore.RESET}")
        return results

    @classmethod
    async def fetch_all(cls, protocols_filter: Optional[Set[ProxyProtocol]] = None,
                        sources_filter: Optional[List[str]] = None) -> Dict[str, ProxyProtocol]:
        """
        Descarga todas las fuentes en paralelo.
        Retorna dict {ip:port: protocol} sin duplicados.
        """
        print(f"\n{Fore.LIGHTCYAN_EX}{'═'*60}")
        print(f"  📡  DESCARGANDO PROXIES DE {len(cls.SOURCES)} FUENTES")
        print(f"{'═'*60}{Fore.RESET}\n")

        proxies: Dict[str, ProxyProtocol] = {}

        async with aiohttp.ClientSession(
            headers={"User-Agent": random.choice(Config.USER_AGENTS)}
        ) as session:
            tasks = []
            for name, (url, proto) in cls.SOURCES.items():
                # Filtro por protocolo
                if protocols_filter and proto not in protocols_filter:
                    continue
                # Filtro por nombre de fuente
                if sources_filter and not any(s.lower() in name.lower() for s in sources_filter):
                    continue
                tasks.append(cls._fetch_one(session, name, url, proto))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    continue
                for addr, proto in result:
                    if addr not in proxies:
                        proxies[addr] = proto

        print(f"\n{Fore.LIGHTCYAN_EX}  📊  Total proxies únicas: {len(proxies)}{Fore.RESET}")

        # Desglose por protocolo
        by_proto = defaultdict(int)
        for proto in proxies.values():
            by_proto[proto.value] += 1
        for proto, count in sorted(by_proto.items()):
            print(f"      {proto.upper():8s} → {count}")

        return proxies

    @staticmethod
    def load_from_file(filepath: str) -> Dict[str, ProxyProtocol]:
        """Carga proxies desde archivo local."""
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
                        # Detectar protocolo por keyword en la línea
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

    async def _detect_my_ip(self):
        """Detecta tu IP real para verificar anonimato."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.ipify.org?format=json", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    self.my_ip = data.get("ip", "")
                    print(f"{Fore.LIGHTYELLOW_EX}  🌐 Tu IP real: {self.my_ip}{Fore.RESET}")
        except Exception:
            print(f"{Fore.LIGHTYELLOW_EX}  ⚠ No se pudo detectar tu IP real{Fore.RESET}")

    def _get_connector(self, protocol: ProxyProtocol, address: str) -> Optional[ProxyConnector]:
        """Crea conector según el tipo de proxy."""
        ip, port = address.split(":")
        try:
            if protocol == ProxyProtocol.SOCKS5:
                return ProxyConnector(
                    proxy_type=ProxyType.SOCKS5,
                    host=ip, port=int(port), rdns=True
                )
            elif protocol == ProxyProtocol.SOCKS4:
                return ProxyConnector(
                    proxy_type=ProxyType.SOCKS4,
                    host=ip, port=int(port), rdns=True
                )
            else:
                # HTTP/HTTPS → usa proxy estándar de aiohttp
                return None
        except Exception:
            return None

    async def _test_alive(self, session_or_connector, address: str,
                          protocol: ProxyProtocol) -> Tuple[bool, float, dict]:
        """
        Test de vida: intenta conectar y mide latencia.
        Retorna (alive, latency_ms, response_data).
        """
        test_url = random.choice(Config.ALIVE_TEST_URLS)
        headers = {"User-Agent": random.choice(Config.USER_AGENTS)}
        timeout = aiohttp.ClientTimeout(total=Config.TIMEOUT_ALIVE)
        start = time.monotonic()
        resp_data = {}

        try:
            if protocol in (ProxyProtocol.SOCKS4, ProxyProtocol.SOCKS5):
                connector = self._get_connector(protocol, address)
                if not connector:
                    return False, 0, {}
                async with aiohttp.ClientSession(connector=connector) as socks_session:
                    async with socks_session.get(test_url, headers=headers, timeout=timeout) as resp:
                        latency = (time.monotonic() - start) * 1000
                        if resp.status == 200:
                            text = await resp.text()
                            try:
                                resp_data = json.loads(text)
                            except (json.JSONDecodeError, Exception):
                                resp_data = {"raw": text[:200]}
                            return True, latency, resp_data
            else:
                proxy_url = f"http://{address}"
                async with session_or_connector.get(
                    test_url, headers=headers, timeout=timeout, proxy=proxy_url
                ) as resp:
                    latency = (time.monotonic() - start) * 1000
                    if resp.status == 200:
                        text = await resp.text()
                        try:
                            resp_data = json.loads(text)
                        except (json.JSONDecodeError, Exception):
                            resp_data = {"raw": text[:200]}
                        return True, latency, resp_data
        except Exception:
            pass
        return False, 0, {}

    def _detect_anonymity(self, resp_data: dict) -> AnonLevel:
        """Detecta nivel de anonimato basado en la respuesta."""
        if not self.my_ip or not resp_data:
            return AnonLevel.UNKNOWN

        text = json.dumps(resp_data).lower()

        # Si tu IP real aparece en la respuesta → transparente
        if self.my_ip in text:
            return AnonLevel.TRANSPARENT

        # Buscar headers que delatan proxy
        proxy_headers = ['x-forwarded-for', 'via', 'x-real-ip', 'forwarded']
        origin = resp_data.get('origin', '')

        # Si origin contiene tu IP → transparente
        if self.my_ip in origin:
            return AnonLevel.TRANSPARENT

        # Si hay headers de proxy en la respuesta → anonymous
        headers_data = resp_data.get('headers', {})
        if isinstance(headers_data, dict):
            for h in proxy_headers:
                if h in [k.lower() for k in headers_data.keys()]:
                    if self.my_ip in str(headers_data.get(h, '')):
                        return AnonLevel.TRANSPARENT
                    return AnonLevel.ANONYMOUS

        # Sin filtración → elite
        return AnonLevel.ELITE

    async def _test_quality_target(self, session_or_connector, address: str,
                                   protocol: ProxyProtocol,
                                   target_name: str, target_url: str) -> bool:
        """Testea si el proxy funciona contra un target específico."""
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
                async with aiohttp.ClientSession(connector=connector) as socks_session:
                    async with socks_session.get(target_url, headers=headers,
                                                  timeout=timeout, allow_redirects=True) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            if target_name == "login.live.com":
                                return 'PPFT' in text or 'login' in text.lower()
                            return len(text) > 100
            else:
                proxy_url = f"http://{address}"
                async with session_or_connector.get(
                    target_url, headers=headers, timeout=timeout,
                    proxy=proxy_url, allow_redirects=True
                ) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        if target_name == "login.live.com":
                            return 'PPFT' in text or 'login' in text.lower()
                        return len(text) > 100
        except Exception:
            pass
        return False

    async def _get_geolocation(self, ip: str) -> Tuple[str, str, str]:
        """Obtiene país y organización del IP (batch-friendly)."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://ip-api.com/json/{ip}?fields=countryCode,country,org"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return (
                            data.get("countryCode", "??"),
                            data.get("country", "Unknown"),
                            data.get("org", "")
                        )
        except Exception:
            pass
        return "??", "Unknown", ""

    def _calculate_score(self, result: ProxyResult) -> int:
        """
        Calcula score 0-100 basado en múltiples factores.
        """
        score = 0

        # ── Latencia (max 35pts) ──
        lat_s = result.latency_ms / 1000.0
        if lat_s <= Config.LATENCY_EXCELLENT:
            score += 35
        elif lat_s <= Config.LATENCY_GOOD:
            score += 25
        elif lat_s <= Config.LATENCY_FAIR:
            score += 15
        else:
            score += 5

        # ── Anonimato (max 30pts) ──
        anon_scores = {
            AnonLevel.ELITE: 30,
            AnonLevel.ANONYMOUS: 20,
            AnonLevel.TRANSPARENT: 5,
            AnonLevel.UNKNOWN: 10,
        }
        score += anon_scores.get(result.anon_level, 0)

        # ── Protocolo (max 10pts) ──
        proto_scores = {
            ProxyProtocol.SOCKS5: 10,
            ProxyProtocol.SOCKS4: 7,
            ProxyProtocol.HTTPS: 8,
            ProxyProtocol.HTTP: 5,
        }
        score += proto_scores.get(result.protocol, 0)

        # ── Targets OK (max 25pts) ──
        if result.targets_ok:
            target_pts = min(25, len(result.targets_ok) * 8)
            score += target_pts

        return min(100, score)

    def _classify_quality(self, score: int) -> QualityTier:
        if score >= 80:
            return QualityTier.PREMIUM
        elif score >= 60:
            return QualityTier.HIGH
        elif score >= 40:
            return QualityTier.MEDIUM
        else:
            return QualityTier.LOW

    async def _check_one(self, session: aiohttp.ClientSession,
                         address: str, protocol: ProxyProtocol) -> Optional[ProxyResult]:
        """Verificación completa de un proxy."""
        async with self._semaphore:
            ip, port_str = address.split(":")
            result = ProxyResult(
                ip=ip, port=int(port_str), protocol=protocol,
                last_checked=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            # 1️⃣ Test de vida + latencia
            alive, latency, resp_data = await self._test_alive(session, address, protocol)

            await self.stats.inc('checked')
            current = self.stats.checked

            if not alive:
                result.alive = False
                await self.stats.inc('dead')
                # Solo imprimir cada 50 muertos para no saturar
                if self.stats.dead % 50 == 0:
                    print(f"  {Fore.LIGHTBLACK_EX}[{current:05d}] ... {self.stats.dead} muertos ...{Fore.RESET}")
                return None

            result.alive = True
            result.latency_ms = round(latency, 1)
            await self.stats.inc('alive', protocol.value)

            # 2️⃣ Detección de anonimato
            result.anon_level = self._detect_anonymity(resp_data)

            # 3️⃣ Geolocalización (solo para vivas)
            result.country, result.country_name, result.org = await self._get_geolocation(ip)
            if result.country != "??":
                await self.stats.inc('alive', country=result.country)

            # 4️⃣ Test de targets de calidad
            for target_name in self.test_targets:
                if target_name in Config.QUALITY_TEST_URLS:
                    target_url = Config.QUALITY_TEST_URLS[target_name]
                    ok = await self._test_quality_target(session, address, protocol, target_name, target_url)
                    if ok:
                        result.targets_ok.append(target_name)

            # 5️⃣ Scoring y clasificación
            result.score = self._calculate_score(result)
            result.quality = self._classify_quality(result.score)

            # Actualizar stats de calidad
            tier_map = {
                QualityTier.PREMIUM: 'premium',
                QualityTier.HIGH: 'high',
                QualityTier.MEDIUM: 'medium',
                QualityTier.LOW: 'low',
            }
            await self.stats.inc(tier_map[result.quality])

            # Imprimir resultado
            anon_icon = {"elite": "🛡️", "anonymous": "🔒", "transparent": "👁️", "unknown": "❓"}
            proto_color = {
                "http": Fore.LIGHTWHITE_EX, "https": Fore.LIGHTCYAN_EX,
                "socks4": Fore.LIGHTMAGENTA_EX, "socks5": Fore.LIGHTYELLOW_EX,
            }
            quality_color = {
                QualityTier.PREMIUM: Fore.LIGHTGREEN_EX,
                QualityTier.HIGH: Fore.GREEN,
                QualityTier.MEDIUM: Fore.LIGHTYELLOW_EX,
                QualityTier.LOW: Fore.LIGHTRED_EX,
            }

            pc = proto_color.get(protocol.value, Fore.WHITE)
            qc = quality_color.get(result.quality, Fore.WHITE)
            ai = anon_icon.get(result.anon_level.value, "❓")
            targets = ",".join(result.targets_ok) if result.targets_ok else "—"

            print(
                f"  {qc}[{current:05d}] "
                f"{result.quality.value} "
                f"{pc}{protocol.value.upper():6s}{Fore.RESET} "
                f"{address:21s} "
                f"{ai} {result.anon_level.value:12s} "
                f"🌍 {result.country:2s} "
                f"⏱ {result.latency_ms:7.0f}ms "
                f"📊 {result.score:3d}/100 "
                f"🎯 {targets}"
                f"{Fore.RESET}"
            )

            async with self._results_lock:
                self.results.append(result)

            return result

    async def check_all(self, proxies: Dict[str, ProxyProtocol]):
        """Verifica todas las proxies con alta concurrencia."""
        self._semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT)
        self.stats.total = len(proxies)
        self.stats.start_time = time.time()

        print(f"\n{Fore.LIGHTCYAN_EX}{'═'*60}")
        print(f"  ⚡  VERIFICACIÓN ASYNC — {Config.MAX_CONCURRENT} conexiones simultáneas")
        print(f"{'═'*60}{Fore.RESET}")

        # Detectar IP real
        await self._detect_my_ip()

        targets_str = ", ".join(self.test_targets)
        print(f"  📋 Total: {len(proxies)} | Targets: {targets_str}")
        print(f"  ⏳ Iniciando...\n")

        # Crear sesión base para HTTP/HTTPS
        tcp_conn = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300, ssl=False)
        async with aiohttp.ClientSession(connector=tcp_conn) as session:
            tasks = [
                self._check_one(session, addr, proto)
                for addr, proto in proxies.items()
            ]
            await asyncio.gather(*tasks, return_exceptions=True)


# ══════════════════════════════════════════════════════════════
#              PROXY POOL — ROTACIÓN INTELIGENTE
# ══════════════════════════════════════════════════════════════

class ProxyPool:
    """
    Pool rotativo de proxies verificadas.
    Uso futuro: integración con scrapers.
    """

    def __init__(self, proxies: List[ProxyResult]):
        # Ordenar por score descendente
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
        """Obtener siguiente proxy con filtros opcionales."""
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
        """Obtener proxy aleatoria de alta calidad."""
        good = [p for p in self._all if p.score >= min_score]
        return random.choice(good) if good else None

    def get_best(self, n: int = 10) -> List[ProxyResult]:
        """Top N mejores proxies."""
        return self._all[:n]

    @property
    def summary(self) -> dict:
        return {
            "total": len(self._all),
            "by_protocol": {k: len(v) for k, v in self._by_protocol.items()},
            "by_quality": {k: len(v) for k, v in self._by_quality.items()},
            "top_countries": dict(sorted(
                {k: len(v) for k, v in self._by_country.items()}.items(),
                key=lambda x: x[1], reverse=True
            )[:10]),
            "avg_score": round(sum(p.score for p in self._all) / max(len(self._all), 1), 1),
            "avg_latency": round(sum(p.latency_ms for p in self._all) / max(len(self._all), 1), 1),
        }


# ══════════════════════════════════════════════════════════════
#                 EXPORTADOR DE RESULTADOS
# ══════════════════════════════════════════════════════════════

class ProxyExporter:
    """Exporta resultados en múltiples formatos, modular por tipo."""

    @staticmethod
    def _save_txt(proxies: List[ProxyResult], filepath: str, header: str = ""):
        with open(filepath, 'w', encoding='utf-8') as f:
            if header:
                f.write(f"# {header}\n")
                f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Total: {len(proxies)}\n\n")
            for p in proxies:
                f.write(f"{p.address}\n")
        return filepath

    @staticmethod
    def _save_detailed_txt(proxies: List[ProxyResult], filepath: str, header: str = ""):
        with open(filepath, 'w', encoding='utf-8') as f:
            if header:
                f.write(f"# {header}\n")
                f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for p in proxies:
                targets = ",".join(p.targets_ok) if p.targets_ok else "none"
                f.write(
                    f"{p.protocol.value:6s} | {p.address:21s} | "
                    f"Score:{p.score:3d} | {p.anon_level.value:12s} | "
                    f"{p.country:2s} | {p.latency_ms:.0f}ms | "
                    f"Targets: {targets}\n"
                )
        return filepath

    @staticmethod
    def _save_json(proxies: List[ProxyResult], filepath: str):
        data = {
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": len(proxies),
            "proxies": [p.to_dict() for p in proxies]
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return filepath

    @staticmethod
    def _save_csv(proxies: List[ProxyResult], filepath: str):
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                "ip", "port", "protocol", "score", "quality", "latency_ms",
                "anon_level", "country", "org", "targets_ok", "last_checked"
            ])
            for p in proxies:
                writer.writerow([
                    p.ip, p.port, p.protocol.value, p.score, p.quality.value,
                    p.latency_ms, p.anon_level.value, p.country, p.org,
                    "|".join(p.targets_ok), p.last_checked
                ])
        return filepath

    @classmethod
    def export_all(cls, results: List[ProxyResult]):
        """Exporta todos los resultados organizados por tipo y calidad."""
        if not results:
            print(f"{Fore.LIGHTRED_EX}  [!] No hay proxies para exportar{Fore.RESET}")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = os.path.join(RESULTS_DIR, timestamp)
        os.makedirs(session_dir, exist_ok=True)

        saved_files = []

        # ── 1. Todas las vivas (TXT simple) ──
        f = cls._save_txt(results, os.path.join(session_dir, "all_alive.txt"), "All Alive Proxies")
        saved_files.append(("all_alive.txt", len(results)))

        # ── 2. Por protocolo ──
        by_proto = defaultdict(list)
        for p in results:
            by_proto[p.protocol.value].append(p)

        for proto, plist in by_proto.items():
            fname = f"{proto}_proxies.txt"
            cls._save_txt(plist, os.path.join(session_dir, fname), f"{proto.upper()} Proxies")
            saved_files.append((fname, len(plist)))

        # ── 3. Por calidad ──
        for tier in QualityTier:
            tier_proxies = [p for p in results if p.quality == tier]
            if tier_proxies:
                tier_name = tier.name.lower()
                fname = f"quality_{tier_name}.txt"
                cls._save_txt(tier_proxies, os.path.join(session_dir, fname), f"{tier.value} Proxies")
                saved_files.append((fname, len(tier_proxies)))

        # ── 4. Proxies.txt → Mejores para uso directo ──
        best = sorted(results, key=lambda p: p.score, reverse=True)
        cls._save_txt(best, os.path.join(session_dir, "proxies.txt"), "Best Proxies (sorted by score)")
        saved_files.append(("proxies.txt (best)", len(best)))

        # También copiar al directorio principal
        cls._save_txt(best, os.path.join(SCRIPT_DIR, "proxies.txt"), "Best Proxies")

        # ── 5. Detallado ──
        cls._save_detailed_txt(results, os.path.join(session_dir, "detailed_report.txt"), "Detailed Proxy Report")
        saved_files.append(("detailed_report.txt", len(results)))

        # ── 6. JSON completo ──
        cls._save_json(results, os.path.join(session_dir, "proxies_full.json"))
        saved_files.append(("proxies_full.json", len(results)))

        # ── 7. CSV ──
        cls._save_csv(results, os.path.join(session_dir, "proxies.csv"))
        saved_files.append(("proxies.csv", len(results)))

        # Imprimir resumen
        print(f"\n{Fore.LIGHTCYAN_EX}{'═'*60}")
        print(f"  💾  ARCHIVOS GUARDADOS en results/{timestamp}/")
        print(f"{'═'*60}{Fore.RESET}")
        for fname, count in saved_files:
            print(f"  {Fore.LIGHTGREEN_EX}📄 {fname:30s} → {count} proxies{Fore.RESET}")
        print(f"  {Fore.LIGHTCYAN_EX}📄 proxies.txt (copia en raíz)  → {len(best)} proxies{Fore.RESET}")


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
 {Fore.LIGHTYELLOW_EX}Checker v2.0 — Async Engine{Fore.RESET}
 {Fore.LIGHTWHITE_EX}SOCKS4/5 + HTTP/S │ 12+ Sources │ Smart Scoring{Fore.RESET}
 {Fore.LIGHTBLACK_EX}─────────────────────────────────────────────{Fore.RESET}
""")


def menu_source() -> Dict[str, ProxyProtocol]:
    """Menú de selección de fuente."""
    print(f"{Fore.LIGHTYELLOW_EX}  ╔═══ FUENTE DE PROXIES ═══╗{Fore.RESET}")
    print(f"  ║ 1) 📂 Archivo local       ║")
    print(f"  ║ 2) 🌐 Todas las fuentes   ║")
    print(f"  ║ 3) 🔌 Solo HTTP/HTTPS     ║")
    print(f"  ║ 4) 🧦 Solo SOCKS4/5       ║")
    print(f"  ║ 5) ⚡ Solo APIs (rápido)  ║")
    print(f"  ║ 6) 📦 Solo GitHub repos   ║")
    print(f"  {Fore.LIGHTYELLOW_EX}╚══════════════════════════╝{Fore.RESET}")

    choice = input(f"\n  {Fore.LIGHTYELLOW_EX}Selecciona [1-6, default=2]: {Fore.RESET}").strip() or "2"

    if choice == "1":
        filepath = input(f"  {Fore.LIGHTYELLOW_EX}Archivo [proxies_raw.txt]: {Fore.RESET}").strip() or "proxies_raw.txt"
        return ProxyFetcher.load_from_file(filepath)
    elif choice == "3":
        return asyncio.run(_fetch_filtered({ProxyProtocol.HTTP, ProxyProtocol.HTTPS}))
    elif choice == "4":
        return asyncio.run(_fetch_filtered({ProxyProtocol.SOCKS4, ProxyProtocol.SOCKS5}))
    elif choice == "5":
        return asyncio.run(_fetch_filtered(sources=["ProxyScrape", "Geonode"]))
    elif choice == "6":
        return asyncio.run(_fetch_filtered(sources=["TheSpeedX", "monosans", "clarketm", "jetkai", "hookzof"]))
    else:
        return asyncio.run(_fetch_filtered())


async def _fetch_filtered(protocols: Optional[Set[ProxyProtocol]] = None,
                          sources: Optional[List[str]] = None) -> Dict[str, ProxyProtocol]:
    return await ProxyFetcher.fetch_all(protocols_filter=protocols, sources_filter=sources)


def menu_targets() -> List[str]:
    """Menú de targets para test de calidad."""
    print(f"\n{Fore.LIGHTYELLOW_EX}  ╔═══ TESTS DE CALIDAD ═══╗{Fore.RESET}")
    print(f"  ║ 1) 🔐 login.live.com     ║")
    print(f"  ║ 2) 🌍 Google + Cloudflare║")
    print(f"  ║ 3) 🎯 Todos los targets   ║")
    print(f"  ║ 4) ⚡ Solo vida (rápido)  ║")
    print(f"  {Fore.LIGHTYELLOW_EX}╚══════════════════════════╝{Fore.RESET}")

    choice = input(f"\n  {Fore.LIGHTYELLOW_EX}Selecciona [1-4, default=3]: {Fore.RESET}").strip() or "3"

    if choice == "1":
        return ["login.live.com"]
    elif choice == "2":
        return ["google.com", "cloudflare"]
    elif choice == "3":
        return list(Config.QUALITY_TEST_URLS.keys())
    else:
        return []


def menu_concurrency() -> int:
    """Configurar nivel de concurrencia."""
    print(f"\n{Fore.LIGHTYELLOW_EX}  ╔═══ CONCURRENCIA ═══╗{Fore.RESET}")
    print(f"  ║ 1) 🐢 200 (conservador)  ║")
    print(f"  ║ 2) ⚡ 500 (recomendado)  ║")
    print(f"  ║ 3) 🚀 800 (agresivo)     ║")
    print(f"  ║ 4) 💀 1200 (extremo)     ║")
    print(f"  {Fore.LIGHTYELLOW_EX}╚═════════════════════╝{Fore.RESET}")

    choice = input(f"\n  {Fore.LIGHTYELLOW_EX}Selecciona [1-4, default=2]: {Fore.RESET}").strip() or "2"

    levels = {"1": 200, "2": 500, "3": 800, "4": 1200}
    return levels.get(choice, 500)


def print_final_report(stats: Stats, results: List[ProxyResult]):
    """Imprime reporte final detallado."""
    print(f"\n{Fore.LIGHTCYAN_EX}{'═'*60}")
    print(f"  📊  REPORTE FINAL")
    print(f"{'═'*60}{Fore.RESET}")

    print(f"  {Fore.LIGHTWHITE_EX}⏱  Tiempo total:     {stats.elapsed:.1f}s{Fore.RESET}")
    print(f"  {Fore.LIGHTWHITE_EX}🚀 Velocidad:        {stats.speed:.1f} proxies/seg{Fore.RESET}")
    print(f"  {Fore.LIGHTWHITE_EX}📋 Total verificadas: {stats.checked}/{stats.total}{Fore.RESET}")
    print()
    print(f"  {Fore.LIGHTGREEN_EX}✅ Vivas:    {stats.alive}{Fore.RESET}")
    print(f"  {Fore.LIGHTRED_EX}❌ Muertas:  {stats.dead}{Fore.RESET}")
    print()
    print(f"  {Fore.LIGHTGREEN_EX}⭐ PREMIUM:  {stats.premium}{Fore.RESET}")
    print(f"  {Fore.GREEN}🟢 HIGH:     {stats.high}{Fore.RESET}")
    print(f"  {Fore.LIGHTYELLOW_EX}🟡 MEDIUM:   {stats.medium}{Fore.RESET}")
    print(f"  {Fore.LIGHTRED_EX}🔴 LOW:      {stats.low}{Fore.RESET}")

    if stats.by_protocol:
        print(f"\n  {Fore.LIGHTCYAN_EX}── Por Protocolo ──{Fore.RESET}")
        for proto, count in sorted(stats.by_protocol.items()):
            print(f"    {proto.upper():8s} → {count}")

    # Top países
    if results:
        countries = defaultdict(int)
        for r in results:
            countries[r.country] += 1
        top = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:5]
        if top:
            print(f"\n  {Fore.LIGHTCYAN_EX}── Top Países ──{Fore.RESET}")
            for c, n in top:
                print(f"    🌍 {c}: {n}")

    if results:
        avg_score = sum(r.score for r in results) / len(results)
        avg_lat = sum(r.latency_ms for r in results) / len(results)
        print(f"\n  {Fore.LIGHTCYAN_EX}── Promedios ──{Fore.RESET}")
        print(f"    📊 Score promedio:   {avg_score:.1f}/100")
        print(f"    ⏱  Latencia promedio: {avg_lat:.0f}ms")

    print(f"\n{Fore.LIGHTCYAN_EX}{'═'*60}{Fore.RESET}")


# ══════════════════════════════════════════════════════════════
#                         MAIN
# ══════════════════════════════════════════════════════════════

async def async_main():
    banner()

    # 1. Obtener proxies
    proxies = menu_source()
    if not proxies:
        print(f"{Fore.LIGHTRED_EX}  [!] No hay proxies para verificar{Fore.RESET}")
        return

    # 2. Configurar targets
    targets = menu_targets()

    # 3. Configurar concurrencia
    Config.MAX_CONCURRENT = menu_concurrency()

    # 4. Crear motor y verificar
    stats = Stats()
    checker = ProxyChecker(stats, test_targets=targets)

    try:
        await checker.check_all(proxies)
    except KeyboardInterrupt:
        print(f"\n{Fore.LIGHTYELLOW_EX}  [!] Interrumpido por usuario{Fore.RESET}")

    # 5. Resultados
    results = checker.results
    print_final_report(stats, results)

    # 6. Exportar
    if results:
        ProxyExporter.export_all(results)

        # 7. Pool rotativo disponible
        pool = ProxyPool(results)
        summary = pool.summary
        print(f"\n{Fore.LIGHTGREEN_EX}  🔄 ProxyPool listo con {summary['total']} proxies{Fore.RESET}")
        print(f"  {Fore.LIGHTWHITE_EX}   Score promedio: {summary['avg_score']}/100{Fore.RESET}")
        print(f"  {Fore.LIGHTWHITE_EX}   Latencia promedio: {summary['avg_latency']:.0f}ms{Fore.RESET}")

        best = pool.get_best(3)
        if best:
            print(f"\n  {Fore.LIGHTGREEN_EX}🏆 Top 3 Proxies:{Fore.RESET}")
            for i, p in enumerate(best, 1):
                print(f"    {i}. {p.protocol.value.upper():6s} {p.address:21s} "
                      f"Score:{p.score:3d} {p.anon_level.value:12s} {p.country}")

    print(f"\n{Fore.LIGHTGREEN_EX}  [✓] Completado! Archivos en results/{Fore.RESET}\n")


def main():
    """Entry point — compatible Windows/Linux."""
    try:
        # Windows: usar WindowsSelectorEventLoopPolicy para evitar warnings
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print(f"\n{Fore.LIGHTYELLOW_EX}  [!] Saliendo...{Fore.RESET}")


if __name__ == "__main__":
    main()
