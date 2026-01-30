#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_vulnerabilities_universal.py

✅ Script MUY completo e independiente (SOLO librería estándar).
✅ Diseñado para gestionar MULTIPLES proyectos (1 o N raíces).
✅ No usa PDFs ni depende de Kiuwan/CI: todas las validaciones están dentro del script.
✅ Reporta 4 niveles: MUY_ALTA / ALTA / MEDIO / BAJO
✅ Muestra por hallazgo: ruta, línea, regla/CWE, detalle + snippet (contexto configurable).
✅ Genera ranking de archivos con ALTA/MUY_ALTA (ruta y reconteo).

Limitación honesta
------------------
Esto NO reemplaza un SAST comercial (Kiuwan/Sonar/etc.) porque esos usan parsers completos,
taint tracking y modelos configurables por lenguaje. Este script está pensado para:
- evitar dependencias
- ejecutar igual en cualquier equipo
- entregar hallazgos consistentes y útiles para revisión/corrección
- servir como “pre-scan” local / gate básico

Uso
---
# 1 proyecto (por defecto: carpeta actual)
py validate_vulnerabilities_universal.py

# varios proyectos
py validate_vulnerabilities_universal.py C:\\repos\\proj1 C:\\repos\\proj2

# escanear solo carpetas específicas dentro de cada proyecto
py validate_vulnerabilities_universal.py --paths blueprints services utils templates config

# controlar extensiones
py validate_vulnerabilities_universal.py --include-ext .py,.js,.ts,.html,.jinja

# contexto de líneas (0,1,2)
py validate_vulnerabilities_universal.py --context 2

# salida
py validate_vulnerabilities_universal.py --out-dir security_reports --format txt
py validate_vulnerabilities_universal.py --out-dir security_reports --format json

# ajustar severidad por regla/CWE sin editar código
# JSON ejemplo: {"CWE-532":"MEDIO","CWE-79":"MUY_ALTA"}
py validate_vulnerabilities_universal.py --severity-map severity_map.json

Salida
------
Crea por proyecto:
- report_<projectname>.txt  (o .json) dentro de --out-dir
y además imprime un resumen corto en consola.

Reglas (incluidas por defecto)
------------------------------
Python:
- CWE-89   SQL Injection (heurística sobre cursor.execute)
- CWE-78   OS Command Injection (subprocess/os.system + shell=True/untrusted)
- CWE-94   Code Injection (eval/exec con datos no confiables)
- CWE-502  Unsafe deserialization (pickle.loads, yaml.load sin safe_load)
- CWE-22   Path Traversal (open/send_file/send_from_directory con request/input)
- CWE-601  Open Redirect (redirect con request.*)
- CWE-117  Log Injection (logger.* con request/session/g)
- CWE-532  Sensitive info in logs (password/token/etc en logs)
- CWE-209  Detailed errors exposed (traceback/format_exc/str(e) en responses)
- CWE-698  Execution After Redirect (redirect sin return / código después)
- CWE-489  Debug mode enabled (app.run(debug=True), FLASK_DEBUG=True)

Web/JS/Templates:
- CWE-79   XSS (|safe en Jinja; sinks DOM: innerHTML/outerHTML/document.write/etc.)
- CWE-1022 Reverse tabnabbing (target=_blank sin rel=noopener/noreferrer)
- CWE-20   Form validation disabled (novalidate)
- CWE-311  Insecure transport (http:// literal)
- CWE-798  Hardcoded secrets/keys (regex de tokens, private keys, AWS keys, etc.)
- CWE-200  Hardcoded IP / information exposure
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import symtable
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


SEV_MUY_ALTA = "MUY_ALTA"
SEV_ALTA = "ALTA"
SEV_MEDIO = "MEDIO"
SEV_BAJO = "BAJO"
SEVERITY_ORDER = [SEV_MUY_ALTA, SEV_ALTA, SEV_MEDIO, SEV_BAJO]


def _sev_rank(s: str) -> int:
    try:
        return SEVERITY_ORDER.index(s)
    except ValueError:
        return len(SEVERITY_ORDER)


DEFAULT_SEVERITY_BY_RULE: Dict[str, str] = {
    "CWE-89": SEV_MUY_ALTA,
    "CWE-78": SEV_MUY_ALTA,
    "CWE-94": SEV_MUY_ALTA,
    "CWE-798": SEV_MUY_ALTA,
    "CWE-79": SEV_ALTA,

    "CWE-502": SEV_ALTA,
    "CWE-22": SEV_ALTA,
    "CWE-601": SEV_ALTA,
    "CWE-117": SEV_ALTA,
    "CWE-918": SEV_ALTA,

    "CWE-311": SEV_MEDIO,
    "CWE-209": SEV_MEDIO,
    "CWE-698": SEV_MEDIO,
    "CWE-489": SEV_MEDIO,

    "CWE-532": SEV_BAJO,
    "CWE-1022": SEV_BAJO,
    "CWE-20": SEV_BAJO,
    "CWE-200": SEV_BAJO,

    "PARSER": SEV_BAJO,
}

RULE_TITLE: Dict[str, str] = {
    "CWE-89": "SQL Injection",
    "CWE-78": "OS Command Injection",
    "CWE-94": "Code Injection (eval/exec)",
    "CWE-502": "Unsafe deserialization",
    "CWE-22": "Path Traversal",
    "CWE-601": "Open Redirect",
    "CWE-117": "Log Injection / Log forging",
    "CWE-532": "Sensitive information through logs",
    "CWE-209": "Detailed error messages exposed",
    "CWE-698": "Execution After Redirect (EAR)",
    "CWE-489": "Debug mode enabled",
    "CWE-918": "SSRF (heurístico)",
    "CWE-79": "XSS / DOM-based XSS",
    "CWE-1022": "Reverse tabnabbing",
    "CWE-20": "Form validation disabled (novalidate)",
    "CWE-311": "Insecure transport (HTTP literal / TLS missing)",
    "CWE-798": "Hardcoded secrets / credentials",
    "CWE-200": "Hardcoded IP / information exposure",
    "PARSER": "Parser error (no se pudo parsear)",
}

DEFAULT_INCLUDE_EXT = [".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".htm", ".jinja", ".j2", ".yml", ".yaml", ".env", ".ini", ".cfg", ".conf", ".txt"]

EXCLUDE_DIRS = {
    ".git", ".hg", ".svn",
    "__pycache__", ".pytest_cache", ".mypy_cache",
    ".venv", "venv", "env",
    "node_modules", "dist", "build", "target", "out",
    ".idea", ".vscode",
}

MAX_FILE_SIZE_BYTES = 2_000_000


@dataclass(frozen=True)
class Finding:
    severity: str
    rule_id: str
    rule_title: str
    path: str
    line: int
    detail: str
    snippet: str = ""


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def normalize_path(p: str) -> str:
    return p.replace("\\", "/")


def is_binary_file(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(4096)
        return b"\0" in chunk
    except Exception:
        return True


def read_text(path: Path) -> Optional[str]:
    try:
        if path.stat().st_size > MAX_FILE_SIZE_BYTES:
            return None
    except Exception:
        return None

    if is_binary_file(path):
        return None

    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        try:
            return path.read_text(encoding="latin-1", errors="replace")
        except Exception:
            return None


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def get_line(text: str, lineno: int) -> str:
    lines = text.splitlines()
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1]
    return ""


def snippet_with_context(text: str, lineno: int, context: int) -> str:
    if context <= 0:
        ln = get_line(text, lineno)
        return (ln[:240] + "…") if len(ln) > 240 else ln

    lines = text.splitlines()
    if not lines:
        return ""

    start = max(0, lineno - 1 - context)
    end = min(len(lines), lineno + context)
    block: List[str] = []
    for i in range(start, end):
        prefix = ">" if (i + 1) == lineno else " "
        ln = lines[i]
        if len(ln) > 240:
            ln = ln[:240] + "…"
        block.append(f"{prefix}{i+1:04d}: {ln}")
    return "\n".join(block)


def safe_ast_parse(text: str, filename: str) -> Optional[ast.AST]:
    try:
        return ast.parse(text, filename=filename)
    except SyntaxError:
        return None


def load_severity_map(path: Optional[str]) -> Dict[str, str]:
    if not path:
        return {}
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        out: Dict[str, str] = {}
        for k, v in data.items():
            if not isinstance(k, str) or not isinstance(v, str):
                continue
            kk = k.strip().upper()
            vv = v.strip().upper()
            if vv in SEVERITY_ORDER:
                out[kk] = vv
        return out
    except Exception:
        return {}


def iter_files(root: Path, include_ext: Set[str], only_paths: Optional[List[str]]) -> Iterable[Path]:
    bases = [root] if not only_paths else [root / p for p in only_paths]

    for base in bases:
        if not base.exists():
            continue
        if base.is_file():
            if base.suffix.lower() in include_ext:
                yield base
            continue

        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if any(part in EXCLUDE_DIRS for part in p.parts):
                continue
            if p.suffix.lower() not in include_ext:
                continue
            yield p


def add_finding(out: List[Finding], severity_by_rule: Dict[str, str], rule_id: str,
                rel_path: str, line: int, detail: str, snippet: str) -> None:
    rid = rule_id.upper()
    sev = severity_by_rule.get(rid, SEV_MEDIO)
    out.append(Finding(
        severity=sev,
        rule_id=rid,
        rule_title=RULE_TITLE.get(rid, rid),
        path=rel_path,
        line=line,
        detail=detail,
        snippet=snippet,
    ))


# -----------------------------
# Regex rules (templates/web/general)
# -----------------------------
NOVALIDATE_RE = re.compile(r"\bnovalidate\b", re.IGNORECASE)
TARGET_BLANK_RE = re.compile(r'target\s*=\s*["\']_blank["\']', re.IGNORECASE)
REL_ATTR_RE = re.compile(r"\brel\s*=\s*['\"][^'\"]*['\"]", re.IGNORECASE)
HTTP_URL_RE = re.compile(r"['\"]http://[^'\"]+['\"]", re.IGNORECASE)

IPV4_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
ALLOWED_IPS = {"0.0.0.0", "127.0.0.1", "255.255.255.255"}

PEM_PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----")
AWS_ACCESS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
AWS_SECRET_KEY_RE = re.compile(r"(?i)\baws_secret_access_key\b\s*[:=]\s*['\"][^'\"]+['\"]")
GENERIC_SECRET_ASSIGN_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|auth[_-]?token)\b\s*[:=]\s*['\"][^'\"]{6,}['\"]"
)
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")

DOM_SINKS = [
    re.compile(r"\binnerHTML\s*=\s*[^;]+", re.IGNORECASE),
    re.compile(r"\bouterHTML\s*=\s*[^;]+", re.IGNORECASE),
    re.compile(r"\binsertAdjacentHTML\s*\(", re.IGNORECASE),
    re.compile(r"\bdocument\.write\s*\(", re.IGNORECASE),
]
JINJA_SAFE_RE = re.compile(r"\|\s*safe\b", re.IGNORECASE)


def scan_web_general(root: Path, path: Path, text: str, severity_by_rule: Dict[str, str], context: int) -> List[Finding]:
    rel = normalize_path(str(path.relative_to(root)))
    out: List[Finding] = []
    ext = path.suffix.lower()

    if ext in {".html", ".htm", ".jinja", ".j2"}:
        for m in NOVALIDATE_RE.finditer(text):
            ln = line_for_offset(text, m.start())
            add_finding(out, severity_by_rule, "CWE-20", rel, ln,
                        "Atributo 'novalidate' encontrado (deshabilita validación del navegador).",
                        snippet_with_context(text, ln, context))

        for m in TARGET_BLANK_RE.finditer(text):
            ln = line_for_offset(text, m.start())
            lines = text.splitlines()
            i = ln - 1
            block = lines[i] if 0 <= i < len(lines) else ""
            if ">" not in block:
                for j in range(i + 1, min(i + 6, len(lines))):
                    block += "\n" + lines[j]
                    if ">" in lines[j]:
                        break
            relm = REL_ATTR_RE.search(block)
            rel_ok = False
            if relm:
                rv = relm.group(0).lower()
                rel_ok = ("noopener" in rv and "noreferrer" in rv)
            if not rel_ok:
                add_finding(out, severity_by_rule, "CWE-1022", rel, ln,
                            'target="_blank" sin rel="noopener noreferrer".',
                            snippet_with_context(text, ln, context))

        for m in JINJA_SAFE_RE.finditer(text):
            ln = line_for_offset(text, m.start())
            add_finding(out, severity_by_rule, "CWE-79", rel, ln,
                        "Uso de '|safe' en template (posible XSS si el contenido no está sanitizado).",
                        snippet_with_context(text, ln, context))

    if ext in {".js", ".jsx", ".ts", ".tsx"}:
        for sink in DOM_SINKS:
            for m in sink.finditer(text):
                ln = line_for_offset(text, m.start())
                add_finding(out, severity_by_rule, "CWE-79", rel, ln,
                            f"Uso de sink DOM potencialmente peligroso ({sink.pattern}).",
                            snippet_with_context(text, ln, context))

    for m in HTTP_URL_RE.finditer(text):
        ln = line_for_offset(text, m.start())
        add_finding(out, severity_by_rule, "CWE-311", rel, ln,
                    "URL HTTP (sin TLS) hardcodeada. Preferir https:// o configuración por entorno.",
                    snippet_with_context(text, ln, context))

    for m in IPV4_RE.finditer(text):
        ip = m.group(0)
        if ip in ALLOWED_IPS:
            continue
        ln = line_for_offset(text, m.start())
        line = get_line(text, ln)
        if line.lstrip().startswith("#") or "<!--" in line:
            continue
        add_finding(out, severity_by_rule, "CWE-200", rel, ln,
                    f"IP hardcodeada detectada: {ip}",
                    snippet_with_context(text, ln, context))

    # secrets
    for m in PEM_PRIVATE_KEY_RE.finditer(text):
        ln = line_for_offset(text, m.start())
        add_finding(out, severity_by_rule, "CWE-798", rel, ln,
                    "Se detectó un bloque PRIVATE KEY (posible secreto hardcodeado).",
                    snippet_with_context(text, ln, context))
    for m in AWS_ACCESS_KEY_RE.finditer(text):
        ln = line_for_offset(text, m.start())
        add_finding(out, severity_by_rule, "CWE-798", rel, ln,
                    "AWS Access Key ID detectada (posible secreto hardcodeado).",
                    snippet_with_context(text, ln, context))
    for m in AWS_SECRET_KEY_RE.finditer(text):
        ln = line_for_offset(text, m.start())
        add_finding(out, severity_by_rule, "CWE-798", rel, ln,
                    "aws_secret_access_key detectada (posible secreto hardcodeado).",
                    snippet_with_context(text, ln, context))
    for m in GENERIC_SECRET_ASSIGN_RE.finditer(text):
        ln = line_for_offset(text, m.start())
        add_finding(out, severity_by_rule, "CWE-798", rel, ln,
                    "Asignación de password/secret/token/apiKey detectada (posible secreto hardcodeado).",
                    snippet_with_context(text, ln, context))
    for m in JWT_RE.finditer(text):
        ln = line_for_offset(text, m.start())
        add_finding(out, severity_by_rule, "CWE-798", rel, ln,
                    "JWT detectado (posible token hardcodeado).",
                    snippet_with_context(text, ln, context))

    return out


# -----------------------------
# Python AST rules
# -----------------------------
LOGGER_METHODS = {"debug", "info", "warning", "error", "critical", "exception"}
SENSITIVE_KEYWORDS = {"password", "passwd", "contraseña", "contrasena", "token", "secret", "apikey", "api_key", "authorization", "cookie", "session", "jwt"}
SANITIZER_HINT_RE = re.compile(r"\bsanitiz(e|ar)|escape|mask|redact\b", re.IGNORECASE)
UNTRUSTED_SOURCES_RE = re.compile(
    r"\b(request\.(args|form|json|values|data|headers|cookies)|"
    r"flask\.request\.(args|form|json|values|data|headers|cookies)|"
    r"g\.|session\b|input\s*\(|sys\.argv\b)\b",
    re.IGNORECASE,
)
OPEN_REDIRECT_RE = re.compile(r"\bredirect\s*\(\s*(request\.(args|form|values)\.get|request\.(args|form|values)\[)", re.IGNORECASE)
SSRF_RE = re.compile(r"\b(requests\.(get|post|put|delete|head)|urllib\.request\.urlopen)\s*\(", re.IGNORECASE)

CWE209_TEXT_PATTERNS = [
    re.compile(r"\btraceback\b", re.IGNORECASE),
    re.compile(r"\bformat_exc\b", re.IGNORECASE),
    re.compile(r"\bstr\s*\(\s*e\s*\)", re.IGNORECASE),
    re.compile(r"\brepr\s*\(\s*e\s*\)", re.IGNORECASE),
    re.compile(r"type\s*\(\s*e\s*\)\s*\.\s*__name__", re.IGNORECASE),
]


def _call_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def _contains_untrusted_src(text: str, node: ast.AST) -> bool:
    seg = ast.get_source_segment(text, node) or ""
    return bool(UNTRUSTED_SOURCES_RE.search(seg))


def _contains_string_formatting(node: ast.AST) -> bool:
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        return True
    return False


def scan_python(root: Path, path: Path, text: str, severity_by_rule: Dict[str, str], context: int) -> List[Finding]:
    rel = normalize_path(str(path.relative_to(root)))
    out: List[Finding] = []

    tree = safe_ast_parse(text, filename=str(path))
    if tree is None:
        add_finding(out, severity_by_rule, "PARSER", rel, 1, "No se pudo parsear el archivo Python (SyntaxError).", "")
        return out

    # debug=True / FLASK_DEBUG=True
    for m in re.finditer(r"\bapp\.run\s*\((.*?)\)", text, flags=re.IGNORECASE | re.DOTALL):
        args = m.group(1) or ""
        if re.search(r"\bdebug\s*=\s*True\b", args) is not None:
            ln = line_for_offset(text, m.start())
            add_finding(out, severity_by_rule, "CWE-489", rel, ln,
                        "app.run(debug=True) detectado. Evitar debug en producción.",
                        snippet_with_context(text, ln, context))
    for m in re.finditer(r"\bFLASK_DEBUG\s*=\s*True\b", text):
        ln = line_for_offset(text, m.start())
        add_finding(out, severity_by_rule, "CWE-489", rel, ln,
                    "FLASK_DEBUG=True detectado. Evitar debug en producción.",
                    snippet_with_context(text, ln, context))

    # open redirect (regex)
    for m in OPEN_REDIRECT_RE.finditer(text):
        ln = line_for_offset(text, m.start())
        add_finding(out, severity_by_rule, "CWE-601", rel, ln,
                    "redirect(...) usa destino derivado de request.* (posible Open Redirect). Validar/whitelist.",
                    snippet_with_context(text, ln, context))

    # SSRF (heurístico)
    for m in SSRF_RE.finditer(text):
        ln = line_for_offset(text, m.start())
        line = get_line(text, ln)
        if UNTRUSTED_SOURCES_RE.search(line):
            add_finding(out, severity_by_rule, "CWE-918", rel, ln,
                        "Llamada HTTP (requests/urlopen) con posible URL controlada por usuario (SSRF). Validar/whitelist host.",
                        snippet_with_context(text, ln, context))

    # detailed errors (texto)
    for pat in CWE209_TEXT_PATTERNS:
        for m in pat.finditer(text):
            ln = line_for_offset(text, m.start())
            line = get_line(text, ln)
            if SANITIZER_HINT_RE.search(line):
                continue
            if re.search(r"\b(return|jsonify|abort|make_response)\b", line):
                add_finding(out, severity_by_rule, "CWE-209", rel, ln,
                            "Posible detalle técnico expuesto al usuario (traceback/str(e)/repr(e)).",
                            snippet_with_context(text, ln, context))

    # AST
    for node in ast.walk(tree):
        # code injection
        if isinstance(node, ast.Call) and _call_name(node) in {"eval", "exec", "compile"}:
            ln = getattr(node, "lineno", 1)
            if node.args and _contains_untrusted_src(text, node.args[0]):
                add_finding(out, severity_by_rule, "CWE-94", rel, ln,
                            f"Uso de {_call_name(node)}() con entrada no confiable (request/input/argv).",
                            snippet_with_context(text, ln, context))

        # unsafe deserialization
        if isinstance(node, ast.Call):
            ln = getattr(node, "lineno", 1)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "loads":
                base = node.func.value
                if isinstance(base, ast.Name) and base.id == "pickle":
                    add_finding(out, severity_by_rule, "CWE-502", rel, ln,
                                "pickle.loads(...) detectado. Evitar deserialización insegura.",
                                snippet_with_context(text, ln, context))
            if isinstance(node.func, ast.Attribute) and node.func.attr == "load":
                base = node.func.value
                if isinstance(base, ast.Name) and base.id == "yaml":
                    src = ast.get_source_segment(text, node) or ""
                    if "SafeLoader" not in src and "safe_load" not in src:
                        add_finding(out, severity_by_rule, "CWE-502", rel, ln,
                                    "yaml.load(...) sin SafeLoader detectado. Preferir yaml.safe_load.",
                                    snippet_with_context(text, ln, context))

        # logs: sensitive & untrusted
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in LOGGER_METHODS:
            ln = getattr(node, "lineno", 1)
            if not node.args:
                continue
            src_line = get_line(text, ln)

            if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                msg = node.args[0].value.lower()
                if any(k in msg for k in SENSITIVE_KEYWORDS):
                    add_finding(out, severity_by_rule, "CWE-532", rel, ln,
                                "Mensaje de log contiene keywords sensibles (password/token/etc.).",
                                snippet_with_context(text, ln, context))

            for a in node.args[1:]:
                seg = (ast.get_source_segment(text, a) or "").lower()
                if any(k in seg for k in SENSITIVE_KEYWORDS):
                    add_finding(out, severity_by_rule, "CWE-532", rel, ln,
                                "Posible dato sensible enviado al log (password/token/etc.).",
                                snippet_with_context(text, ln, context))
                    break

            if (UNTRUSTED_SOURCES_RE.search(src_line) or any(_contains_untrusted_src(text, a) for a in node.args)) and not SANITIZER_HINT_RE.search(src_line):
                add_finding(out, severity_by_rule, "CWE-117", rel, ln,
                            "logger.* usa datos no confiables (request/session/input/argv) sin sanitización.",
                            snippet_with_context(text, ln, context))

        # path traversal
        if isinstance(node, ast.Call) and _call_name(node) in {"open", "send_file", "send_from_directory"}:
            ln = getattr(node, "lineno", 1)
            if node.args and _contains_untrusted_src(text, node.args[0]):
                add_finding(out, severity_by_rule, "CWE-22", rel, ln,
                            f"{_call_name(node)}() con ruta derivada de entrada no confiable (posible path traversal).",
                            snippet_with_context(text, ln, context))

        # command injection
        if isinstance(node, ast.Call):
            ln = getattr(node, "lineno", 1)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "system":
                base = node.func.value
                if isinstance(base, ast.Name) and base.id == "os" and node.args:
                    if _contains_untrusted_src(text, node.args[0]) or _contains_string_formatting(node.args[0]):
                        add_finding(out, severity_by_rule, "CWE-78", rel, ln,
                                    "os.system(...) con posible comando construido dinámicamente/untrusted.",
                                    snippet_with_context(text, ln, context))

            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                fn = node.func.attr
                if fn in {"run", "call", "check_call", "check_output", "Popen"}:
                    src = ast.get_source_segment(text, node) or ""
                    if re.search(r"\bshell\s*=\s*True\b", src):
                        add_finding(out, severity_by_rule, "CWE-78", rel, ln,
                                    "subprocess.* con shell=True (alto riesgo). Evitar shell=True o usar lista + validación.",
                                    snippet_with_context(text, ln, context))
                    elif node.args:
                        arg0 = node.args[0]
                        if not (isinstance(arg0, ast.Constant) and isinstance(arg0.value, str)):
                            if _contains_untrusted_src(text, arg0) or _contains_string_formatting(arg0):
                                add_finding(out, severity_by_rule, "CWE-78", rel, ln,
                                            "subprocess.* con comando construido dinámicamente/untrusted. Validar entrada y usar lista.",
                                            snippet_with_context(text, ln, context))

        # SQL injection heurístico
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"execute", "executemany"}:
            ln = getattr(node, "lineno", 1)
            if not node.args:
                continue
            if len(node.args) >= 2:
                continue
            query = node.args[0]
            if isinstance(query, ast.Constant) and isinstance(query.value, str):
                continue
            if _contains_string_formatting(query) or _contains_untrusted_src(text, query):
                add_finding(out, severity_by_rule, "CWE-89", rel, ln,
                            "cursor.execute(...) con query construida dinámicamente (posible SQLi). Usar parámetros.",
                            snippet_with_context(text, ln, context))

    # EAR heuristic (text)
    for m in re.finditer(r"\bredirect\s*\(", text):
        ln = line_for_offset(text, m.start())
        line = get_line(text, ln)
        if "return redirect" not in line:
            add_finding(out, severity_by_rule, "CWE-698", rel, ln,
                        "redirect(...) sin 'return redirect(...)' (posible EAR según SAST).",
                        snippet_with_context(text, ln, context))

    # unused vars (symtable)
    try:
        st = symtable.symtable(text, str(path), "exec")
    except SyntaxError:
        st = None

    if st is not None:
        assigns: Dict[str, List[int]] = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        assigns.setdefault(t.id, []).append(getattr(n, "lineno", 1))
            elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                assigns.setdefault(n.target.id, []).append(getattr(n, "lineno", 1))
            elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
                assigns.setdefault(n.target.id, []).append(getattr(n.target, "lineno", 1))

        def scan(tab: symtable.SymbolTable) -> None:
            for sym in tab.get_symbols():
                name = sym.get_name()
                if name.startswith("_"):
                    continue
                if sym.is_imported() or sym.is_parameter():
                    continue
                if sym.is_assigned() and (not sym.is_referenced()):
                    line = assigns.get(name, [1])[0]
                    add_finding(out, severity_by_rule, "CWE-563", rel, line,
                                f"Variable asignada pero no usada: '{name}'.",
                                snippet_with_context(text, line, context))
            for child in tab.get_children():
                scan(child)

        scan(st)

    return out


def group_findings(findings: List[Finding]) -> Dict[str, Dict[str, List[Finding]]]:
    out: Dict[str, Dict[str, List[Finding]]] = {s: {} for s in SEVERITY_ORDER}
    for f in findings:
        out.setdefault(f.severity, {})
        out[f.severity].setdefault(f.path, []).append(f)
    for sev in out:
        for p in out[sev]:
            out[sev][p].sort(key=lambda x: (x.line, x.rule_id, x.detail))
    return out


def ranking_high(findings: List[Finding]) -> List[Tuple[str, int, int, int]]:
    per: Dict[str, Dict[str, int]] = {}
    for f in findings:
        if f.severity not in {SEV_MUY_ALTA, SEV_ALTA}:
            continue
        per.setdefault(f.path, {SEV_MUY_ALTA: 0, SEV_ALTA: 0})
        per[f.path][f.severity] += 1
    rank: List[Tuple[str, int, int, int]] = []
    for path, d in per.items():
        muy = d.get(SEV_MUY_ALTA, 0)
        alta = d.get(SEV_ALTA, 0)
        total = muy + alta
        if total:
            rank.append((path, muy, alta, total))
    rank.sort(key=lambda x: (-x[3], -x[1], -x[2], x[0]))
    return rank


def render_txt(project_root: Path, findings: List[Finding], scanned_files: int) -> str:
    grouped = group_findings(findings)
    counts = {sev: sum(len(v) for v in grouped.get(sev, {}).values()) for sev in SEVERITY_ORDER}

    lines: List[str] = []
    lines.append("UNIVERSAL VULNERABILITIES REPORT")
    lines.append("=" * 98)
    lines.append(f"Project: {project_root}")
    lines.append(f"Generated: {datetime.utcnow().isoformat()}Z")
    lines.append(f"Files scanned: {scanned_files}")
    lines.append("")
    lines.append("Resumen por clasificación:")
    for sev in SEVERITY_ORDER:
        lines.append(f"  - {sev:8s}: {counts.get(sev, 0)}")
    lines.append("")

    lines.append("Ranking de archivos con vulnerabilidades ALTA/MUY_ALTA (ruta y reconteo):")
    lines.append("-" * 98)
    r = ranking_high(findings)
    if not r:
        lines.append("  (sin hallazgos ALTA/MUY_ALTA)")
    else:
        for path, muy, alta, total in r:
            lines.append(f"  - {path}: MUY_ALTA={muy}, ALTA={alta}, TOTAL={total}")
    lines.append("")

    lines.append("Detalle (agrupado por severidad y archivo):")
    lines.append("=" * 98)

    for sev in SEVERITY_ORDER:
        if counts.get(sev, 0) == 0:
            continue
        lines.append(f"\n[{sev}]")
        lines.append("-" * 98)
        for path, items in sorted(grouped[sev].items(), key=lambda x: x[0]):
            lines.append(f"  {path}  ({len(items)})")
            for f in items:
                lines.append(f"    - L{f.line}: [{f.rule_id}] {f.rule_title} :: {f.detail}")
                if f.snippet:
                    for ln in f.snippet.splitlines():
                        lines.append("      " + ln)

    if not findings:
        lines.append("\nOK: No se encontraron hallazgos con las reglas incluidas.")
    lines.append("")
    return "\n".join(lines)


def render_json(project_root: Path, findings: List[Finding], scanned_files: int) -> str:
    payload = {
        "project_root": str(project_root),
        "generated_utc": datetime.utcnow().isoformat() + "Z",
        "files_scanned": scanned_files,
        "findings": [asdict(f) for f in findings],
        "summary": {
            "MUY_ALTA": sum(1 for f in findings if f.severity == SEV_MUY_ALTA),
            "ALTA": sum(1 for f in findings if f.severity == SEV_ALTA),
            "MEDIO": sum(1 for f in findings if f.severity == SEV_MEDIO),
            "BAJO": sum(1 for f in findings if f.severity == SEV_BAJO),
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def scan_project(project_root: Path, include_ext: Set[str], only_paths: Optional[List[str]],
                 severity_by_rule: Dict[str, str], context: int) -> Tuple[List[Finding], int]:
    findings: List[Finding] = []
    files_scanned = 0

    for fpath in iter_files(project_root, include_ext=include_ext, only_paths=only_paths):
        text = read_text(fpath)
        if text is None:
            continue
        files_scanned += 1

        findings.extend(scan_web_general(project_root, fpath, text, severity_by_rule, context))
        if fpath.suffix.lower() == ".py":
            findings.extend(scan_python(project_root, fpath, text, severity_by_rule, context))

    uniq: Dict[Tuple[str, str, int, str], Finding] = {}
    for f in findings:
        uniq.setdefault((f.rule_id, f.path, f.line, f.detail), f)
    findings = list(uniq.values())
    findings.sort(key=lambda x: (_sev_rank(x.severity), x.path, x.line, x.rule_id, x.detail))
    return findings, files_scanned


def main() -> int:
    parser = argparse.ArgumentParser(description="Escaneo universal de vulnerabilidades (independiente, sin PDFs, multi-proyecto).")
    parser.add_argument("project_roots", nargs="*", default=None,
                        help="Rutas de proyectos a escanear. Si se omite, usa el directorio actual.")
    parser.add_argument("--paths", nargs="*", default=None,
                        help="Limita el escaneo a rutas relativas dentro de cada proyecto (ej: blueprints services).")
    parser.add_argument("--include-ext", default=",".join(DEFAULT_INCLUDE_EXT),
                        help="Extensiones a incluir separadas por coma (ej: .py,.js,.html).")
    parser.add_argument("--context", type=int, default=1, choices=[0, 1, 2],
                        help="Líneas de contexto en el reporte (0/1/2).")
    parser.add_argument("--format", choices=["txt", "json"], default="txt",
                        help="Formato del reporte por proyecto.")
    parser.add_argument("--out-dir", default="security_reports",
                        help="Directorio donde se guardarán los reportes (relativo al lugar de ejecución).")
    parser.add_argument("--severity-map", default=None,
                        help="JSON con override de severidad por regla/CWE (ej: {\"CWE-79\":\"MUY_ALTA\"}).")
    parser.add_argument("--fail-on", choices=["none", "bajo", "medio", "alta", "muy_alta"], default="alta",
                        help="Código de salida !=0 si hay hallazgos en o por encima del umbral.")
    args = parser.parse_args()

    include_ext = {e.strip().lower() for e in args.include_ext.split(",") if e.strip()}
    severity_by_rule = dict(DEFAULT_SEVERITY_BY_RULE)
    severity_by_rule.update(load_severity_map(args.severity_map))

    roots = [Path(p).expanduser().resolve() for p in (args.project_roots or [str(Path.cwd())])]
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    threshold = args.fail_on.lower()
    threshold_rank = {
        "none": 999,
        "bajo": _sev_rank(SEV_BAJO),
        "medio": _sev_rank(SEV_MEDIO),
        "alta": _sev_rank(SEV_ALTA),
        "muy_alta": _sev_rank(SEV_MUY_ALTA),
    }[threshold]

    exit_nonzero = False

    for root in roots:
        if not root.exists() or not root.is_dir():
            eprint(f"[SKIP] No existe o no es directorio: {root}")
            continue

        findings, scanned = scan_project(root, include_ext=include_ext, only_paths=args.paths,
                                         severity_by_rule=severity_by_rule, context=args.context)

        counts = {
            SEV_MUY_ALTA: sum(1 for f in findings if f.severity == SEV_MUY_ALTA),
            SEV_ALTA: sum(1 for f in findings if f.severity == SEV_ALTA),
            SEV_MEDIO: sum(1 for f in findings if f.severity == SEV_MEDIO),
            SEV_BAJO: sum(1 for f in findings if f.severity == SEV_BAJO),
        }
        proj_name = root.name or "project"
        eprint(f"\n[PROJECT] {proj_name}")
        eprint(f"  Files scanned: {scanned}")
        eprint(f"  MUY_ALTA={counts[SEV_MUY_ALTA]}  ALTA={counts[SEV_ALTA]}  MEDIO={counts[SEV_MEDIO]}  BAJO={counts[SEV_BAJO]}")

        suffix = "txt" if args.format == "txt" else "json"
        report_path = out_dir / f"report_{proj_name}.{suffix}"
        if args.format == "txt":
            report_path.write_text(render_txt(root, findings, scanned), encoding="utf-8")
        else:
            report_path.write_text(render_json(root, findings, scanned), encoding="utf-8")
        eprint(f"  Report: {report_path}")

        worst = min([_sev_rank(f.severity) for f in findings], default=999)
        if worst <= threshold_rank:
            exit_nonzero = True

    return 2 if exit_nonzero else 0


if __name__ == "__main__":
    raise SystemExit(main())
