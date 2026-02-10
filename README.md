# 🔍 Proxy Checker v2.3 — Async Engine

Herramienta de alta velocidad para obtener, verificar y clasificar proxies de **30+ fuentes gratuitas** automáticamente. Verifica cada proxy con **doble comprobación**, separa los resultados por tipo × calidad (ej: `socks5_premium.txt`), y guarda automáticamente al presionar Ctrl+C.

## ⚡ ¿Qué hace?

1. **Descarga** proxies de 30+ fuentes (APIs + repositorios GitHub) en paralelo
2. **Filtra duplicados** automáticamente (IP:PORT único, validación de octetos)
3. **Doble verificación** — cada proxy se testea contra 2 URLs diferentes para eliminar falsos positivos
4. **Mide** la latencia promedio de ambos tests en milisegundos
5. **Detecta** el nivel de anonimato (Elite 🛡️ / Anonymous 🔒 / Transparent 👁️)
6. **Geolocaliza** cada proxy por país
7. **Prueba** compatibilidad con sitios protegidos (Google, Cloudflare, httpbin, azenv)
8. **Puntúa** cada proxy de 0 a 100 con scoring inteligente
9. **Exporta** resultados organizados por **protocolo × calidad** en múltiples formatos
10. **Ctrl+C seguro** — guarda todo lo encontrado hasta ese momento

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
| 2) 🌐 Todas las fuentes | APIs + GitHub repos, obtiene ~20,000+ proxies **(recomendado)** |
| 3) 🔌 Solo HTTP/HTTPS | Solo proxies web estándar, sin SOCKS |
| 4) 🧦 Solo SOCKS4/5 | Proxies SOCKS, generalmente más anónimas |
| 5) ⚡ Solo APIs directas | ProxyScrape + OpenProxy (~8,000 rápidas) |
| 6) 📦 Solo GitHub repos | Listas masivas de repositorios públicos (~15,000+) |

### Menú 2 — Tests de Calidad

| Opción | Descripción |
|--------|-------------|
| 1) 🎯 Custom URL | Testea contra cualquier URL que tú elijas |
| 2) 🌍 Google + Cloudflare | Test contra sitios con protección anti-bot |
| 3) 🔬 HQ Riguroso | 5 targets: Google + CF + httpbin headers/ip + azenv **(más completo)** |
| 4) ⚡ Solo vida (rápido) | Solo verifica si la proxy responde (doble check), sin targets |

### Menú 3 — Velocidad/Concurrencia

| Opción | Conexiones | Para quién |
|--------|-----------|------------|
| 1) 🐢 200 | Conservador | Conexiones lentas o PCs con poca RAM |
| 2) ⚡ 500 | Recomendado | Balance entre velocidad y estabilidad |
| 3) 🚀 800 | Agresivo | Buena conexión a internet |
| 4) 💀 1200 | Extremo | Máxima velocidad |

### Menú 4 — Control de Tiempo

Antes de iniciar, el checker **estima cuánto tiempo tomará** y te da opciones:

| Opción | Descripción |
|--------|-------------|
| 1) ✅ Testear TODAS | Verifica todas las proxies |
| 2) ⏱ Limitar por tiempo | Dices "5 minutos" y testea lo que quepa |
| 3) 🔢 Limitar por cantidad | Eliges cuántas proxies testear |

## 🔒 Doble Verificación

A diferencia de otros checkers, v2.3 **verifica cada proxy dos veces**:

1. **Test 1**: Conecta a una URL aleatoria (httpbin.org/ip, ip-api.com, ipify.org)
2. **Test 2**: Conecta a una URL **diferente** para confirmar

Ambos tests deben:
- Devolver HTTP 200
- Contener un JSON válido con una IP real (no texto random)
- La IP devuelta debe ser diferente a tu IP real

Esto **elimina falsos positivos** donde una proxy responde una vez pero no funciona de verdad.

## 📊 Sistema de Scoring (0-100)

| Factor | Puntos máx | Detalle |
|--------|-----------|---------|
| Latencia | 35 pts | <1s = 35, <2.5s = 25, <5s = 15, >5s = 5 |
| Anonimato | 30 pts | Elite = 30, Anonymous = 20, Transparent = 5 |
| Protocolo | 10 pts | SOCKS5 = 10, HTTPS = 8, SOCKS4 = 7, HTTP = 5 |
| Targets OK | 25 pts | Proporcional a % de targets superados |

### Clasificación

- ⭐ **PREMIUM** (≥80 pts) — Proxy de alta calidad, rápida y anónima
- 🟢 **HIGH** (≥60 pts) — Buena calidad, funcional para la mayoría de usos
- 🟡 **MEDIUM** (≥40 pts) — Calidad aceptable, usar con precaución
- 🔴 **LOW** (<40 pts) — Baja calidad, solo para uso básico

## 💾 Archivos de Salida

Todos los resultados se guardan en `results/YYYYMMDD_HHMMSS/`:

```
results/20260210_153000/
├── all_alive.txt              # Todas las proxies vivas
├── http.txt                   # Solo HTTP (ordenadas por score)
├── https.txt                  # Solo HTTPS
├── socks4.txt                 # Solo SOCKS4
├── socks5.txt                 # Solo SOCKS5
├── http_premium.txt           # HTTP + calidad PREMIUM
├── http_high.txt              # HTTP + calidad HIGH
├── http_medium.txt            # HTTP + calidad MEDIUM
├── socks4_premium.txt         # SOCKS4 + PREMIUM
├── socks4_high.txt            # SOCKS4 + HIGH
├── socks5_premium.txt         # SOCKS5 + PREMIUM ★ las mejores
├── socks5_high.txt            # SOCKS5 + HIGH
├── quality_premium.txt        # Todos los protocolos PREMIUM
├── quality_high.txt           # Todos los protocolos HIGH
├── hq_elite.txt               # Score≥60 + Anonimato Elite
├── detailed_report.txt        # Reporte con todos los datos
├── proxies_full.json          # JSON completo
└── proxies.csv                # CSV para Excel/Sheets
```

## 🛑 Ctrl+C Seguro

Si presionas **Ctrl+C** durante la verificación:
- El checker **detiene las tareas pendientes** (no se queda colgado)
- **Guarda todas las proxies encontradas** hasta ese momento
- Exporta los archivos normalmente
- Un segundo Ctrl+C fuerza la salida inmediata

## 📡 Fuentes de Proxies (30+ verificadas)

### APIs Directas
- ProxyScrape (HTTP, SOCKS4)
- OpenProxyList (HTTP, SOCKS4, SOCKS5)
- ProxySpace ALL

### GitHub Repos
- TheSpeedX/PROXY-List (HTTP, SOCKS4, SOCKS5)
- monosans/proxy-list (HTTP, SOCKS4, SOCKS5)
- clarketm/proxy-list (HTTP)
- jetkai/proxy-list (HTTP, HTTPS, SOCKS4, SOCKS5)
- roosterkid/openproxylist (HTTPS)
- prxchk/proxy-list (HTTP, SOCKS5)
- zevtyardt/proxy-list (HTTP, SOCKS4, SOCKS5) ★ nuevo
- rdavydov/proxy-list (HTTP, SOCKS4, SOCKS5) ★ nuevo
- sunny9577/proxy-scraper (HTTP) ★ nuevo
- mmpx12/proxy-list (HTTP, HTTPS, SOCKS4, SOCKS5) ★ nuevo

> Fuentes muertas eliminadas: ErcinDedeworken (404), Geonode (API vacía), ProxyScrape SOCKS5 (0 resultados), hookzof (< 15 proxies), MuRongPIG (100k+ entradas sin verificar)

## 🔄 ProxyPool — Uso Programático

```python
from proxy_checker_v2 import ProxyPool, ProxyResult

pool = ProxyPool(results)

best = pool.get_best(1)[0]                          # La mejor
proxy = pool.get_random(min_score=60)                # Aleatoria de calidad
proxy = pool.get_next(protocol="socks5", min_score=50)  # Rotación
proxy = pool.get_next(country="US", min_score=40)    # Por país
```

## 📖 Documentación Adicional

- **[GUIA_DE_USO.md](GUIA_DE_USO.md)** — Guía práctica completa: dónde usar cada tipo de proxy, casos de uso por protocolo y calidad, integración con herramientas (Scrapy, Selenium, curl, etc.)

## 🆚 Changelog

| Versión | Cambios principales |
|---------|-------------------|
| v1.0 | Motor sync con requests+threads, 3 fuentes |
| v2.0 | Motor async (aiohttp), 16 fuentes, SOCKS, scoring |
| v2.1 | Fix EOFError, 27 fuentes, menu descriptions |
| v2.2 | Custom URL, HQ riguroso (5 targets), estimación de tiempo |
| **v2.3** | **Doble verificación, Ctrl+C seguro, export protocolo×calidad, 30+ fuentes verificadas, eliminadas fuentes muertas, validación IP estricta** |

## ⚠️ Notas Importantes

- Las proxies gratuitas tienen **vida corta** — ejecuta el checker antes de cada sesión
- La **doble verificación** reduce falsos positivos pero toma ~50% más de tiempo
- Para **máxima calidad**, usa opción 3 (HQ Riguroso) + opción 2 (500 conexiones)
- Los archivos `socks5_premium.txt` y `hq_elite.txt` contienen las **mejores proxies**
- Ctrl+C guarda lo encontrado — puedes interrumpir si ya tienes suficientes

## 📜 Licencia

MIT — Libre para uso personal y comercial.

## 👤 Autor

**Psico777** — [GitHub](https://github.com/Psico777)
