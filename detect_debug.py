

#!/usr/bin/env python3
# detect_debug.py
"""
Escanea un repo y detecta "rastros de debug" comunes (Python/JS/TS, etc.):
- pdb.set_trace(), import pdb, breakpoint()
- DEBUG = True (Django/Flask config típico)
- logging.debug(...) / logger.debug(...)
- console.log/debug/trace(...) y `debugger;` en JS/TS
- (opcional) print(...) si activas --include-print

Uso:
  python detect_debug.py
  python detect_debug.py /ruta/al/proyecto
  python detect_debug.py --include-print
  python detect_debug.py --json hallazgos.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Dict, Optional, Tuple


DEFAULT_IGNORES = {
    ".git", ".hg", ".svn",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".venv", "venv", "env",
    "node_modules",
    "dist", "build", "out", "target",
    ".idea", ".vscode",
    ".next", ".nuxt",
    ".terraform",
}

DEFAULT_EXTENSIONS = {
    # Code
    ".py", ".pyi",
    ".js", ".jsx", ".ts", ".tsx",
    ".java", ".kt",
    ".go",
    ".rb",
    ".php",
    ".cs",
    ".c", ".h", ".cpp", ".hpp",
    ".rs",
    ".swift",
    # Config / scripts
    ".sh", ".bash", ".zsh",
    ".yaml", ".yml",
    ".ini", ".cfg", ".conf",
    ".env",
    ".toml",
}

# Archivos comunes a escanear aunque no tengan extensión típica
ALWAYS_SCAN_FILENAMES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Makefile",
}

@dataclass
class Match:
    label: str
    line_no: int
    line: str
    pattern: str


def is_probably_text_file(path: Path, max_bytes: int = 8192) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(max_bytes)
        if b"\x00" in chunk:
            return False
        # si se puede decodificar "razonablemente", lo tratamos como texto
        chunk.decode("utf-8", errors="replace")
        return True
    except Exception:
        return False


def should_scan_file(path: Path, extensions: set, scan_all: bool) -> bool:
    if path.name in ALWAYS_SCAN_FILENAMES:
        return True
    if scan_all:
        return True
    if path.suffix.lower() in extensions:
        return True
    return False


def iter_files(root: Path, ignores: set, extensions: set, scan_all: bool) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        # Filtra directorios ignorados in-place (os.walk respeta este cambio)
        dirnames[:] = [d for d in dirnames if d not in ignores and not d.startswith(".git")]
        for fn in filenames:
            p = Path(dirpath) / fn
            if should_scan_file(p, extensions, scan_all) and is_probably_text_file(p):
                yield p


def compile_patterns(include_print: bool) -> List[Tuple[str, re.Pattern]]:
    patterns: List[Tuple[str, str]] = [
        # Python debugging
        ("PY_PDB_SET_TRACE", r"\bpdb\.set_trace\(\)"),
        ("PY_IMPORT_PDB", r"^\s*import\s+pdb\b"),
        ("PY_BREAKPOINT", r"\bbreakpoint\s*\("),
        ("PY_IPDB", r"\bipdb\.set_trace\(\)|\bimport\s+ipdb\b"),
        ("PY_DEBUG_TRUE", r"^\s*DEBUG\s*=\s*True\b"),
        ("PY_LOGGING_DEBUG", r"\blogging\.debug\s*\("),
        ("PY_LOGGER_DEBUG", r"\blogger\.debug\s*\("),

        # JS/TS debugging
        ("JS_CONSOLE", r"\bconsole\.(log|debug|trace|warn)\s*\("),
        ("JS_DEBUGGER", r"^\s*debugger\s*;"),

        # Otros patrones útiles (comentarios explícitos)
        ("COMMENT_DEBUG_MARK", r"(#|//)\s*debug\b|/\*\s*debug\b"),
    ]

    if include_print:
        # OJO: print puede ser válido; por eso va opcional
        patterns.append(("PY_PRINT", r"\bprint\s*\("))

    compiled: List[Tuple[str, re.Pattern]] = []
    for label, pat in patterns:
        compiled.append((label, re.compile(pat, re.IGNORECASE)))
    return compiled


def scan_file(path: Path, compiled_patterns: List[Tuple[str, re.Pattern]], max_matches_per_file: int) -> List[Match]:
    matches: List[Match] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return matches

    lines = text.splitlines()
    for i, line in enumerate(lines, start=1):
        # rápido: evita regex si no contiene palabras típicas
        lowered = line.lower()
        if not any(k in lowered for k in ("debug", "pdb", "breakpoint", "console", "logger", "logging", "ipdb", "debugger", "print")):
            continue

        for label, rx in compiled_patterns:
            if rx.search(line):
                snippet = line.strip()
                matches.append(Match(label=label, line_no=i, line=snippet, pattern=rx.pattern))
                if len(matches) >= max_matches_per_file:
                    return matches
    return matches


def main() -> int:
    ap = argparse.ArgumentParser(description="Detecta archivos con rastros de debug.")
    ap.add_argument("root", nargs="?", default=".", help="Ruta raíz del proyecto (default: .)")
    ap.add_argument("--include-print", action="store_true", help="Incluye detección de print(...) (más falsos positivos).")
    ap.add_argument("--scan-all", action="store_true", help="Escanea todos los archivos de texto, no solo extensiones conocidas.")
    ap.add_argument("--ext", action="append", default=[], help="Extensión extra a incluir (ej: --ext .vue). Repetible.")
    ap.add_argument("--ignore", action="append", default=[], help="Carpeta extra a ignorar (ej: --ignore .cache). Repetible.")
    ap.add_argument("--max-per-file", type=int, default=200, help="Máximo de coincidencias por archivo (default: 200).")
    ap.add_argument("--max-total", type=int, default=5000, help="Máximo total de coincidencias (default: 5000).")
    ap.add_argument("--json", dest="json_path", default=None, help="Si se indica, guarda salida en JSON.")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Ruta no existe: {root}", file=sys.stderr)
        return 2

    ignores = set(DEFAULT_IGNORES) | set(args.ignore)
    extensions = set(DEFAULT_EXTENSIONS)
    for e in args.ext:
        if not e.startswith("."):
            e = "." + e
        extensions.add(e.lower())

    compiled = compile_patterns(include_print=args.include_print)

    scanned_files = 0
    total_matches = 0
    results: Dict[str, List[Dict]] = {}

    for f in iter_files(root, ignores=ignores, extensions=extensions, scan_all=args.scan_all):
        scanned_files += 1
        ms = scan_file(f, compiled, max_matches_per_file=args.max_per_file)
        if ms:
            rel = str(f.relative_to(root))
            results[rel] = [
                {"label": m.label, "line": m.line_no, "text": m.line}
                for m in ms
            ]
            total_matches += len(ms)
            if total_matches >= args.max_total:
                break

    # salida humana
    files_with_hits = len(results)
    print(f"\n[detect_debug] Root: {root}")
    print(f"[detect_debug] Archivos escaneados: {scanned_files}")
    print(f"[detect_debug] Archivos con hallazgos: {files_with_hits}")
    print(f"[detect_debug] Total hallazgos: {sum(len(v) for v in results.values())}\n")

    for relpath in sorted(results.keys()):
        print(f"== {relpath} ==")
        for item in results[relpath]:
            label = item["label"]
            line_no = item["line"]
            text = item["text"]
            print(f"  L{line_no:>5}  {label:<18}  {text}")
        print()

    if args.json_path:
        out = {
            "root": str(root),
            "scanned_files": scanned_files,
            "files_with_hits": files_with_hits,
            "total_hits": sum(len(v) for v in results.values()),
            "results": results,
        }
        Path(args.json_path).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[detect_debug] JSON guardado en: {args.json_path}")

    # return code útil: 0 si limpio, 1 si encontró cosas
    return 1 if files_with_hits > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
