# 🗺️ Guía Práctica: Dónde y Cómo Usar Cada Tipo de Proxy

Esta guía te explica **para qué sirve cada tipo de proxy**, qué hacer con cada nivel de calidad, y casos de uso reales.

---

## 📚 Conceptos Básicos

### ¿Qué es una proxy?
Una proxy es un servidor intermediario entre tu computadora e internet. Cuando usas una proxy, los sitios web ven la IP de la proxy, **no la tuya**.

### ¿Por qué usar proxies?
- **Privacidad**: Ocultar tu IP real
- **Acceso geográfico**: Acceder a contenido bloqueado por país
- **Web scraping**: Recopilar datos sin ser bloqueado
- **Testing**: Probar sitios desde diferentes ubicaciones
- **Automatización**: Ejecutar múltiples tareas sin restricciones de IP

---

## 🔌 Tipos de Proxy por Protocolo

### HTTP — Puerto estándar web

| Aspecto | Detalle |
|---------|---------|
| **Qué hace** | Reenvía tráfico HTTP (sin cifrar) |
| **Seguridad** | ❌ Baja — el tráfico se puede interceptar |
| **Velocidad** | ⚡ Rápida — menos overhead |
| **Compatibilidad** | ✅ Universal — funciona en cualquier navegador/herramienta |

**Dónde usar HTTP:**
- ✅ Web scraping de sitios públicos (noticias, precios, productos)
- ✅ Verificación de disponibilidad de páginas
- ✅ Bots de monitoreo de precios
- ✅ Crawling de motores de búsqueda
- ⚠️ NO usar para login, pagos, o datos sensibles

**Ejemplo práctico:**
```python
import requests

proxy = {"http": "http://IP:PORT"}
response = requests.get("http://example.com/products", proxies=proxy)
```

---

### HTTPS — HTTP con cifrado SSL/TLS

| Aspecto | Detalle |
|---------|---------|
| **Qué hace** | Reenvía tráfico HTTPS (cifrado end-to-end) |
| **Seguridad** | ✅ Alta — cifrado SSL/TLS |
| **Velocidad** | ⚡ Buena — ligeramente más lenta que HTTP |
| **Compatibilidad** | ✅ Alta — la mayoría de herramientas lo soportan |

**Dónde usar HTTPS:**
- ✅ Scraping de sitios con SSL (HTTPS)
- ✅ Acceso a APIs que requieren HTTPS
- ✅ Navegación web general
- ✅ Verificación de certificados SSL
- ✅ Testing de sitios e-commerce

**Ejemplo práctico:**
```python
import requests

proxy = {"https": "http://IP:PORT"}
response = requests.get("https://api.example.com/data", proxies=proxy)
```

---

### SOCKS4 — Socket Secure v4

| Aspecto | Detalle |
|---------|---------|
| **Qué hace** | Reenvía cualquier tipo de tráfico TCP (no solo HTTP) |
| **Seguridad** | 🔒 Media — no cifra, pero no revela headers |
| **Velocidad** | ⚡⚡ Muy rápida — protocolo minimalista |
| **Compatibilidad** | Requiere soporte SOCKS (no todos los programas) |

**Dónde usar SOCKS4:**
- ✅ Torrents y P2P
- ✅ Conexiones TCP genéricas (FTP, SSH tunneling)
- ✅ Gaming (reducir latencia mediante ruta diferente)
- ✅ Bots de automatización masiva (velocidad)
- ✅ Scraping que requiere conexiones raw TCP

**Ejemplo práctico:**
```python
import requests

proxy = {"http": "socks4://IP:PORT", "https": "socks4://IP:PORT"}
response = requests.get("https://example.com", proxies=proxy)
```

**Con aiohttp-socks (async):**
```python
from aiohttp_socks import ProxyConnector, ProxyType
import aiohttp

connector = ProxyConnector(proxy_type=ProxyType.SOCKS4, host="IP", port=PORT)
async with aiohttp.ClientSession(connector=connector) as session:
    async with session.get("https://example.com") as resp:
        print(await resp.text())
```

---

### SOCKS5 — Socket Secure v5 (el más versátil)

| Aspecto | Detalle |
|---------|---------|
| **Qué hace** | Reenvía TCP + UDP, soporta autenticación y DNS remoto |
| **Seguridad** | 🔒🔒 Alta — DNS remoto evita leaks, autenticación |
| **Velocidad** | ⚡⚡ Muy rápida |
| **Compatibilidad** | La más amplia entre los SOCKS |

**Dónde usar SOCKS5:**
- ✅ **Todo lo que SOCKS4 hace, pero mejor**
- ✅ VoIP y streaming (soporta UDP)
- ✅ Resolución DNS remota (oculta qué sitios visitas)
- ✅ Navegación anónima de alto nivel
- ✅ Bypass de firewalls corporativos
- ✅ Tor-like setups
- ✅ Scraping con máxima privacidad

**Ejemplo práctico:**
```python
import requests

proxy = {"http": "socks5://IP:PORT", "https": "socks5://IP:PORT"}
response = requests.get("https://example.com", proxies=proxy)
```

---

## ⭐ Qué Hacer Según la Calidad (Score)

### ⭐ PREMIUM (Score ≥ 80)

Estas proxies son **las mejores que encontraste**. Rápidas, anónimas, pasan múltiples targets.

| Uso recomendado | Por qué |
|----------------|---------|
| 🔐 Acceso a sitios protegidos | Pasan Cloudflare, Google, etc. |
| 🤖 Bots de compra/reserva | Necesitan velocidad + anonimato |
| 📊 Scraping de APIs premium | No te bloquean fácilmente |
| 🔍 OSINT / investigación | Ocultan tu identidad completamente |
| 🎮 Gaming competitivo | Latencia mínima |

**Archivos a usar:** `socks5_premium.txt`, `http_premium.txt`, `hq_elite.txt`

---

### 🟢 HIGH (Score 60-79)

Buena calidad. Funcionales para la mayoría de tareas.

| Uso recomendado | Por qué |
|----------------|---------|
| 🕷️ Web scraping general | Suficiente velocidad y anonimato |
| 📧 Verificación de emails | Acceso a servidores SMTP/IMAP |
| 🌍 Geo-testing | Testear contenido por país |
| 📱 Testing de apps | Simular usuarios de diferentes regiones |
| 🔄 Rotación de IPs | Pool grande de proxies funcionales |

**Archivos a usar:** `socks4_high.txt`, `http_high.txt`, `quality_high.txt`

---

### 🟡 MEDIUM (Score 40-59)

Calidad aceptable. Usar para tareas que toleran fallos.

| Uso recomendado | Por qué |
|----------------|---------|
| 📋 Scraping masivo (bulk) | No importa si algunas fallan |
| 🔍 Verificación de URLs | Solo necesitan responder |
| 📊 Monitoreo básico | Chequeo periódico de sitios |
| 🧪 Testing/desarrollo | Para probar tu código |

**Archivos a usar:** `http_medium.txt`, `socks4_medium.txt`

---

### 🔴 LOW (Score < 40)

Calidad baja. Solo para uso básico donde no importa el anonimato.

| Uso recomendado | Por qué |
|----------------|---------|
| ✅ Verificar si un sitio está online | Solo necesita conexión |
| 📊 Estadísticas de proxy | Para investigación |
| 🧪 Testing de conectividad | Solo ping básico |

**Archivos a usar:** `quality_low.txt`

---

## 🛡️ Niveles de Anonimato

### Elite 🛡️
- Tu IP real **NO aparece** en ningún header
- El sitio destino **NO sabe** que estás usando proxy
- **Ideal para:** Todo lo que requiera privacidad máxima

### Anonymous 🔒
- Tu IP real **NO aparece**, pero hay headers de proxy (X-Forwarded-For, Via)
- El sitio sabe que **usas proxy**, pero no sabe quién eres
- **Ideal para:** Scraping general, acceso geográfico

### Transparent 👁️
- Tu IP real **SÍ aparece** en los headers
- **NO proporciona anonimato** — solo cambia la ruta
- **Ideal para:** Nada que requiera privacidad. Solo para caching o balanceo.

---

## 🗂️ Guía de Archivos de Salida

Después de ejecutar el checker, encontrarás estos archivos en `results/YYYYMMDD_HHMMSS/`:

### Archivos por Protocolo (solo `ip:port`)
| Archivo | Contenido |
|---------|-----------|
| `http.txt` | Todas las HTTP vivas, ordenadas por score |
| `https.txt` | Todas las HTTPS vivas |
| `socks4.txt` | Todas las SOCKS4 vivas |
| `socks5.txt` | Todas las SOCKS5 vivas |

### Archivos por Protocolo × Calidad ⭐
| Archivo | Para qué usarlo |
|---------|-----------------|
| `socks5_premium.txt` | Lo mejor — scraping protegido, bots, OSINT |
| `socks5_high.txt` | Rotación de IPs de calidad |
| `socks4_premium.txt` | Torrents y P2P con máxima calidad |
| `socks4_high.txt` | Conexiones TCP rápidas |
| `http_premium.txt` | Scraping de APIs premium |
| `http_high.txt` | Scraping web general de calidad |
| `http_medium.txt` | Scraping masivo bulk |
| `https_premium.txt` | Acceso seguro a sitios SSL |

### Archivos Especiales
| Archivo | Para qué usarlo |
|---------|-----------------|
| `hq_elite.txt` | Las MEJORES — Score ≥60 + Anonimato Elite |
| `all_alive.txt` | Todo lo que funciona |
| `proxies.txt` | Todas ordenadas por score (para rotación) |
| `detailed_report.txt` | Reporte legible con todos los datos |
| `proxies_full.json` | JSON completo para integración con código |
| `proxies.csv` | Para análisis en Excel/Sheets |

---

## 🔧 Integración con Herramientas Populares

### Scrapy (Python)
```python
# settings.py
DOWNLOADER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 1,
}

# Leer proxies del archivo
with open('results/proxies.txt') as f:
    ROTATING_PROXY_LIST = [line.strip() for line in f]
```

### Selenium (Python)
```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument('--proxy-server=socks5://IP:PORT')
driver = webdriver.Chrome(options=options)
```

### curl (Terminal)
```bash
# HTTP proxy
curl -x http://IP:PORT https://example.com

# SOCKS5 proxy
curl --socks5 IP:PORT https://example.com

# SOCKS5 con resolución DNS remota
curl --socks5-hostname IP:PORT https://example.com
```

### Axios (Node.js)
```javascript
const { SocksProxyAgent } = require('socks-proxy-agent');
const axios = require('axios');

const agent = new SocksProxyAgent('socks5://IP:PORT');
const response = await axios.get('https://example.com', { httpsAgent: agent });
```

### Navegador (Firefox/Chrome)
1. Configuración → Red → Proxy manual
2. Tipo: SOCKS5 (o HTTP)
3. IP del proxy, Puerto
4. ✅ "DNS remoto" para SOCKS5

---

## ⚠️ Consideraciones Importantes

### Vida útil
- Las proxies **gratuitas mueren rápido** (minutos a horas)
- Ejecuta el checker **antes de cada sesión** de trabajo
- Las proxies PREMIUM duran más que las LOW

### Legalidad
- ✅ Usar proxies es **legal** en la mayoría de países
- ❌ Lo que hagas a través de la proxy **puede ser ilegal**
- ⚠️ Respeta los Terms of Service de los sitios que visites
- ⚠️ No uses proxies para actividades ilegales

### Rendimiento
- **HTTP** → Más rápido para scraping web simple
- **SOCKS5** → Más versátil y anónimo, ligeramente más lento
- **SOCKS4** → Rápido pero sin DNS remoto

### Seguridad
- Las proxies gratuitas pueden **ver tu tráfico no cifrado**
- Siempre usa **HTTPS** cuando mandes datos sensibles
- **SOCKS5 con DNS remoto** es la opción más segura en gratuitas
- Nunca envíes contraseñas a través de HTTP con proxy

---

## 📊 Tabla Resumen Rápida

| Necesidad | Protocolo | Calidad mínima | Archivo |
|-----------|-----------|----------------|---------|
| Scraping protegido (Cloudflare) | SOCKS5 | PREMIUM | `socks5_premium.txt` |
| Scraping general | HTTP | HIGH | `http_high.txt` |
| Scraping masivo (bulk) | HTTP | MEDIUM | `http_medium.txt` |
| Torrents/P2P | SOCKS4/5 | HIGH | `socks4_high.txt` |
| Navegación anónima | SOCKS5 | PREMIUM | `hq_elite.txt` |
| Testing de APIs | HTTPS | HIGH | `https_high.txt` |
| Verificación de URLs | HTTP | LOW | `all_alive.txt` |
| Bots de compra | SOCKS5 | PREMIUM | `socks5_premium.txt` |
| Geo-testing por país | Cualquiera | HIGH | `quality_high.txt` |
| OSINT/investigación | SOCKS5 | PREMIUM | `hq_elite.txt` |

---

**Autor:** [Psico777](https://github.com/Psico777) | **Herramienta:** [ComprobadorProxies](https://github.com/Psico777/ComprobadorProxies)
