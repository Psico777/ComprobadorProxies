# 🔍 Proxy Checker v2.1 — Async Engine

Herramienta de alta velocidad para obtener, verificar y clasificar proxies de **20+ fuentes gratuitas** automáticamente. Separa los resultados por tipo (HTTP, HTTPS, SOCKS4, SOCKS5) y por calidad (Premium, High, Medium, Low).

## ⚡ ¿Qué hace?

1. **Descarga** proxies de 20+ fuentes (APIs + repositorios GitHub) en paralelo
2. **Verifica** cuáles están vivas con 500+ conexiones simultáneas (async)
3. **Mide** la latencia de cada proxy en milisegundos
4. **Detecta** el nivel de anonimato (Elite 🛡️ / Anonymous 🔒 / Transparent 👁️)
5. **Geolocaliza** cada proxy por país
6. **Prueba** compatibilidad con sitios protegidos (login.live.com, Google, Cloudflare)
7. **Puntúa** cada proxy de 0 a 100 con scoring inteligente
8. **Exporta** resultados organizados por tipo y calidad en múltiples formatos

## 📦 Instalación

```bash
# Clonar el repositorio
git clone git@github.com:Psico777/ComprobadorProxies.git
cd ComprobadorProxies

# Instalar dependencias
pip install aiohttp aiohttp-socks colorama
```

### Requisitos
- Python 3.9+
- Conexión a internet

## 🚀 Uso

```bash
python proxy_checker_v2.py
```

Se mostrará un menú interactivo con las siguientes opciones:

### Menú 1 — Fuente de Proxies

| Opción | Descripción |
|--------|-------------|
| 1) 📂 Archivo local | Carga proxies desde un archivo `.txt` de tu PC |
| 2) 🌐 Todas las fuentes | APIs + GitHub repos, obtiene ~15,000+ proxies **(recomendado)** |
| 3) 🔌 Solo HTTP/HTTPS | Solo proxies web estándar, sin SOCKS |
| 4) 🧦 Solo SOCKS4/5 | Proxies SOCKS, generalmente más anónimas y estables |
| 5) ⚡ Solo APIs directas | ProxyScrape + Geonode + OpenProxy (~3,000 proxies rápidas) |
| 6) 📦 Solo GitHub repos | Listas masivas de repositorios públicos (~12,000+) |

### Menú 2 — Tests de Calidad

| Opción | Descripción |
|--------|-------------|
| 1) 🔐 login.live.com | Verifica si la proxy puede acceder al login de Microsoft |
| 2) 🌍 Google + Cloudflare | Test contra sitios con protección anti-bot |
| 3) 🎯 Todos los targets | Live.com + Google + Cloudflare (test más completo) |
| 4) ⚡ Solo vida (rápido) | Solo verifica si la proxy responde, sin tests extra |

### Menú 3 — Velocidad/Concurrencia

| Opción | Conexiones simultáneas | Para quién |
|--------|----------------------|------------|
| 1) 🐢 200 | Conservador | Conexiones lentas o PCs con poca RAM |
| 2) ⚡ 500 | Recomendado | Balance entre velocidad y estabilidad |
| 3) 🚀 800 | Agresivo | Buena conexión a internet |
| 4) 💀 1200 | Extremo | Máxima velocidad, puede saturar la red |

## 📊 Sistema de Scoring (0-100)

Cada proxy recibe un puntaje basado en:

| Factor | Puntos máx | Detalle |
|--------|-----------|---------|
| Latencia | 35 pts | <1s = 35, <2.5s = 25, <5s = 15, >5s = 5 |
| Anonimato | 30 pts | Elite = 30, Anonymous = 20, Transparent = 5 |
| Protocolo | 10 pts | SOCKS5 = 10, HTTPS = 8, SOCKS4 = 7, HTTP = 5 |
| Targets OK | 25 pts | 8 pts por cada target que funciona |

### Clasificación

- ⭐ **PREMIUM** (≥80 pts) — Proxy de alta calidad, rápida y anónima
- 🟢 **HIGH** (≥60 pts) — Buena calidad, funcional para la mayoría de usos
- 🟡 **MEDIUM** (≥40 pts) — Calidad aceptable, usar con precaución
- 🔴 **LOW** (<40 pts) — Baja calidad, solo para uso básico

## 💾 Archivos de Salida

Todos los resultados se guardan en `results/YYYYMMDD_HHMMSS/`:

```
results/20260210_153000/
├── all_alive.txt          # Todas las proxies vivas
├── http.txt               # Solo proxies HTTP (ordenadas por score)
├── https.txt              # Solo proxies HTTPS
├── socks4.txt             # Solo proxies SOCKS4
├── socks5.txt             # Solo proxies SOCKS5
├── quality_premium.txt    # Solo las ⭐ PREMIUM
├── quality_high.txt       # Solo las 🟢 HIGH
├── quality_medium.txt     # Solo las 🟡 MEDIUM
├── quality_low.txt        # Solo las 🔴 LOW
├── hq_elite.txt           # Score≥60 + Anonimato Elite (las mejores)
├── detailed_report.txt    # Reporte con todos los datos por proxy
├── proxies_full.json      # JSON completo con toda la metadata
└── proxies.csv            # CSV para análisis en Excel/Google Sheets
```

Además, se copia `proxies.txt` en la raíz del proyecto con todas las proxies ordenadas por score para uso directo.

## 📡 Fuentes de Proxies (20+)

### APIs Directas (rápidas, ~3,000)
- ProxyScrape (HTTP, SOCKS4, SOCKS5)
- Geonode Free (HTTP, SOCKS)
- OpenProxyList (HTTP, SOCKS4, SOCKS5)

### GitHub Repos (masivas, ~12,000+)
- TheSpeedX/PROXY-List
- monosans/proxy-list
- clarketm/proxy-list
- jetkai/proxy-list
- hookzof/socks5_list
- roosterkid/openproxylist
- ErcinDedeworken/topfreeproxies
- MuRongPIG/Proxy-Master
- prxchk/proxy-list

## 🔄 ProxyPool — Uso Programático

El checker incluye un `ProxyPool` para integrar con scrapers:

```python
from proxy_checker_v2 import ProxyPool, ProxyResult

# Después de verificar
pool = ProxyPool(results)

# Obtener la mejor proxy
best = pool.get_best(1)[0]

# Proxy aleatoria de alta calidad
proxy = pool.get_random(min_score=60)

# Rotación secuencial
proxy = pool.get_next(protocol="socks5", min_score=50)

# Filtrar por país
proxy = pool.get_next(country="US", min_score=40)
```

## 🆚 v1.0 vs v2.1

| Característica | v1.0 | v2.1 |
|---------------|------|------|
| Motor | requests + threads | aiohttp async |
| Conexiones simultáneas | 150 | 500-1200 |
| Fuentes de proxies | 3 | 20+ |
| Proxies obtenidas | ~1,300 | ~15,000+ |
| Protocolos | Solo HTTP | HTTP/HTTPS/SOCKS4/SOCKS5 |
| Scoring | No | 0-100 multi-factor |
| Anonimato | No detecta | Elite/Anonymous/Transparent |
| Geolocalización | No | Sí (país + org) |
| Separación por tipo | No | http.txt, socks5.txt, etc. |
| Separación por calidad | No | premium.txt, high.txt, etc. |
| Export JSON/CSV | No | Sí |
| ProxyPool | No | Sí (rotación inteligente) |

## ⚠️ Notas Importantes

- Las proxies gratuitas tienen **vida corta** — se recomienda ejecutar el checker antes de cada sesión de trabajo
- El rate limit de geolocalización (ip-api.com) es de ~45 req/min, el checker lo respeta automáticamente
- Para **máxima calidad**, usa la opción 2 (todas las fuentes) + opción 3 (todos los targets)
- Los archivos `hq_elite.txt` contienen las proxies de **mayor calidad absoluta**

## 📜 Licencia

MIT — Libre para uso personal y comercial.

## 👤 Autor

**Psico777** — [GitHub](https://github.com/Psico777)
