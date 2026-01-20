# -*- coding: utf-8 -*-
import re
from pathlib import Path

TARGET = Path("config/permissions.py")

INV_MODULE = "inventario_corporativo"
INV_ACTIONS_LIST = "['view_oficinas_servicio', 'request_return', 'request_transfer']"

def ensure_module_in_modules(role_block: str) -> str:
    # Encuentra modules: [ ... ]
    m = re.search(r"('modules'\s*:\s*\[)(.*?)(\])", role_block, flags=re.DOTALL)
    if not m:
        return role_block

    prefix, body, suffix = m.group(1), m.group(2), m.group(3)
    if INV_MODULE in body:
        return role_block

    body_strip = body.strip()
    if body_strip and not body_strip.endswith(","):
        body_strip += ","
    body_strip += f" '{INV_MODULE}'"

    return role_block[:m.start()] + prefix + body_strip + suffix + role_block[m.end():]

def ensure_actions_inventario(role_block: str) -> str:
    # Busca actions: { ... }
    m = re.search(r"('actions'\s*:\s*\{)(.*?)(\})", role_block, flags=re.DOTALL)
    if not m:
        return role_block

    prefix, body, suffix = m.group(1), m.group(2), m.group(3)

    if re.search(r"'inventario_corporativo'\s*:", body):
        # Ya existe; no lo sobreescribimos para no romper nada
        return role_block

    # Insertar antes del cierre del dict actions
    body_strip = body.rstrip()
    insert = f"\n         '{INV_MODULE}': {INV_ACTIONS_LIST},"
    # Ojo: mantener indentación similar
    if body_strip.strip().endswith(","):
        new_body = body_strip + insert
    else:
        new_body = body_strip + "," + insert

    return role_block[:m.start()] + prefix + new_body + suffix + role_block[m.end():]

def patch_file(text: str) -> str:
    # Parchea solo roles que empiecen por 'oficina_'
    role_pattern = r"('oficina_[^']+'\s*:\s*\{.*?\n\s*\},)"
    def repl(match):
        block = match.group(1)
        block2 = ensure_module_in_modules(block)
        block3 = ensure_actions_inventario(block2)
        return block3
    return re.sub(role_pattern, repl, text, flags=re.DOTALL)

def main():
    if not TARGET.exists():
        raise SystemExit(f"No encontré {TARGET}. Ejecuta el script en la raíz del repo.")

    original = TARGET.read_text(encoding="utf-8", errors="ignore")
    patched = patch_file(original)

    if patched == original:
        print("[SKIP] No hubo cambios (quizá ya estaba aplicado).")
        return

    bak = TARGET.with_suffix(".py.bak")
    if not bak.exists():
        bak.write_text(original, encoding="utf-8")
        print(f"[OK] Backup creado: {bak}")

    TARGET.write_text(patched, encoding="utf-8")
    print(f"[OK] Parche aplicado: {TARGET}")

if __name__ == "__main__":
    main()
