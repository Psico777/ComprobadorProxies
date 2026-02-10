import requests
import re

print("=== Test Proxy Extraction ===")

# Test 1: free-proxy-list.net
print("\n[1] Testing free-proxy-list.net...")
try:
    r = requests.get(
        'https://free-proxy-list.net/',
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'},
        timeout=15
    )
    print(f"Status: {r.status_code}")
    print(f"Content length: {len(r.text)}")
    
    # Pattern 1
    pattern1 = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})</td><td>(\d+)'
    matches1 = re.findall(pattern1, r.text)
    print(f"Pattern 1 found: {len(matches1)} proxies")
    if matches1:
        print(f"Sample: {matches1[:3]}")
    
    # Save HTML for debug
    with open('proxy_debug.html', 'w', encoding='utf-8') as f:
        f.write(r.text)
    print("HTML saved to proxy_debug.html")
    
except Exception as e:
    print(f"Error: {e}")

# Test 2: sslproxies.org
print("\n[2] Testing sslproxies.org...")
try:
    r2 = requests.get(
        'https://www.sslproxies.org/',
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'},
        timeout=15
    )
    print(f"Status: {r2.status_code}")
    matches2 = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})</td><td>(\d+)', r2.text)
    print(f"Found: {len(matches2)} proxies")
    if matches2:
        print(f"Sample: {matches2[:3]}")
except Exception as e:
    print(f"Error: {e}")

# Test 3: proxyscrape API
print("\n[3] Testing proxyscrape.com API...")
try:
    r3 = requests.get(
        'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all',
        headers={'User-Agent': 'Mozilla/5.0'},
        timeout=15
    )
    print(f"Status: {r3.status_code}")
    proxies = [p.strip() for p in r3.text.split('\n') if p.strip() and ':' in p]
    print(f"Found: {len(proxies)} proxies")
    if proxies:
        print(f"Sample: {proxies[:3]}")
except Exception as e:
    print(f"Error: {e}")
