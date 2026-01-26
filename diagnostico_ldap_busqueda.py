import os
import sys
from dotenv import load_dotenv

load_dotenv()

def mask(s: str, keep=2):
    if not s:
        return ""
    s = str(s)
    if len(s) <= keep * 2:
        return "*" * len(s)
    return s[:keep] + "*" * (len(s) - keep * 2) + s[-keep:]

print("=== DIAGNÓSTICO LDAP (BÚSQUEDA AD) ===")
print("LDAP_SERVER:", os.getenv("LDAP_SERVER", ""))
print("LDAP_PORT:", os.getenv("LDAP_PORT", ""))
print("LDAP_USE_SSL:", os.getenv("LDAP_USE_SSL", ""))
print("LDAP_DOMAIN:", os.getenv("LDAP_DOMAIN", ""))
print("LDAP_SEARCH_BASE:", os.getenv("LDAP_SEARCH_BASE", ""))
print("LDAP_SERVICE_USER:", os.getenv("LDAP_SERVICE_USER", ""))
print("LDAP_SERVICE_PASSWORD:", mask(os.getenv("LDAP_SERVICE_PASSWORD", ""), keep=2))
print("-------------------------------------")

try:
    from utils.ldap_auth import ad_auth
except Exception as e:
    print("[ERROR] No pude importar utils.ldap_auth:", type(e).__name__, str(e))
    raise

# 1) Test conexión/bind
try:
    res = ad_auth.test_connection()
    print("[test_connection]:", res)
except Exception as e:
    print("[ERROR test_connection]:", type(e).__name__, str(e))

# 2) Prueba búsqueda
term = sys.argv[1] if len(sys.argv) > 1 else "luis"
print(f"\n--- BÚSQUEDA: {term} ---")
try:
    users = ad_auth.search_user_by_name(term, max_results=10)
    print("Resultados:", len(users))
    for u in users[:10]:
        print("-", u.get("usuario",""), "|", u.get("nombre",""), "|", u.get("email",""))
except Exception as e:
    print("[ERROR search_user_by_name]:", type(e).__name__, str(e))

print("\n=== FIN ===")
