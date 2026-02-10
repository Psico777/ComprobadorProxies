import requests
import re

r = requests.get(
    'https://login.live.com/login.srf', 
    params={'wa':'wsignin1.0','wreply':'https://account.microsoft.com/'}, 
    headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
)

print('URL:', r.url)
print('Status:', r.status_code)

# Guardar HTML para debug
with open('debug_response.html', 'w', encoding='utf-8') as f:
    f.write(r.text)
print('HTML guardado en debug_response.html')

# Buscar todas las ocurrencias de sFT y PPFT
if 'sFT' in r.text:
    idx = r.text.find('sFT')
    print(f'sFT encontrado en posicion {idx}')
    print(f'Contexto: {r.text[idx:idx+200]}')

if 'PPFT' in r.text:
    idx = r.text.find('PPFT')
    print(f'PPFT encontrado en posicion {idx}')
    print(f'Contexto: {r.text[idx:idx+200]}')
