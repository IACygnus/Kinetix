#!/usr/bin/env python3
"""Guardián de tokens del rediseño de Kinetix.

Falla (código 1) si en los archivos ya migrados aparece un estilo que no sale
de los tokens (frontend/src/styles/tokens.css):

  hex        un color hexadecimal literal: #4f46e5
  rgb        un color funcional literal: rgb(79 70 229), rgba(0,0,0,.5), hsl(...)
  arbitrario un valor arbitrario de Tailwind: bg-[#…], text-[11px], max-w-[50vh],
             una variante arbitraria ([&_x]:…) o una propiedad arbitraria ([a:b])
  paleta     una clase de la paleta por defecto de Tailwind (bg-indigo-600,
             text-gray-500, bg-white, text-black) o de la paleta vieja (sqa-*)

Se permiten `rgb(var(--x) …)` y `rgb(${…})`: leen un token.

Uso:
    python tools/check_tokens.py            # revisa el alcance de la etapa
    python tools/check_tokens.py --lista    # solo enseña qué archivos revisa

AMPLIAR EN CADA ETAPA: añadir a ALCANCE las carpetas o archivos que la etapa
migra. Lo que no está en ALCANCE no se revisa: las pantallas aún no migradas
conservan sus clases a propósito (plan del rediseño, regla 4).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SRC = RAIZ / "frontend" / "src"

# ---------------------------------------------------------------------------
# Alcance. Una línea por pieza migrada; la etapa que la migró, al lado.
# ---------------------------------------------------------------------------
ALCANCE: list[Path] = [
    # Etapa 0 — sistema de diseño, armazón e inicio de sesión
    SRC / "components" / "ui",
    SRC / "components" / "layout",
    SRC / "components" / "auth" / "Login.tsx",
    SRC / "context" / "PreferenciasContext.tsx",
    SRC / "styles",
    SRC / "index.css",
    SRC / "main.tsx",
    # Etapa 1 — …
]

# Dentro del alcance pero fuera de la regla.
EXENTOS: set[Path] = {
    # La definición de los tokens: el único sitio donde puede haber un color.
    SRC / "styles" / "tokens.css",
}

EXTENSIONES = {".ts", ".tsx", ".css"}

# ---------------------------------------------------------------------------
# Reglas
# ---------------------------------------------------------------------------
HEX = re.compile(r"(?<![\w&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b")
COLOR_FUNCIONAL = re.compile(r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\(\s*(?!var\(|\$\{)[-\d.]")

COLORES_TAILWIND = (
    "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|"
    "cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose"
)
UTILIDADES_COLOR = (
    "bg|text|border(?:-[trblxyse])?|ring|ring-offset|from|via|to|fill|stroke|outline|"
    "divide|placeholder|accent|caret|shadow|decoration"
)
PALETA = re.compile(
    rf"(?<![\w-])(?:[\w-]+:)*(?:{UTILIDADES_COLOR})-"
    rf"(?:(?:{COLORES_TAILWIND})-\d{{2,3}}|white|black|sqa-[\w-]+)(?:/\d+)?(?![\w-])"
)

# Valores, variantes y propiedades arbitrarias de Tailwind. Solo se buscan
# DENTRO de cadenas, para no confundir `lista[0]` con una clase.
ARBITRARIO = re.compile(
    r"(?<![\w$])(?:[\w-]+:)*[a-z][\w-]*-\[[^\]\s]+\]"   # bg-[#fff], max-w-[50vh]
    r"|\[[^\]\s]*&[^\]\s]*\]:"                          # [&_x]:… o [[data-x]_&]:…
    r"|(?<![\w$\]])\[[a-z-]+:[^\]\s]+\]"                 # [overflow-wrap:anywhere]
)
CADENA = re.compile(r"""'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*"|`(?:[^`\\]|\\.)*`""", re.S)


def archivos() -> list[Path]:
    salida: list[Path] = []
    for p in ALCANCE:
        if p.is_dir():
            salida += [f for f in sorted(p.rglob("*")) if f.suffix in EXTENSIONES]
        elif p.is_file():
            salida.append(p)
        else:
            print(f"AVISO: {p.relative_to(RAIZ)} no existe", file=sys.stderr)
    return [f for f in salida if f not in EXENTOS and ".bak" not in f.name]


def linea_col(texto: str, pos: int) -> tuple[int, int]:
    linea = texto.count("\n", 0, pos) + 1
    return linea, pos - (texto.rfind("\n", 0, pos) + 1) + 1


def revisar(f: Path) -> list[tuple[int, int, str, str]]:
    texto = f.read_text(encoding="utf-8")
    hallados: list[tuple[int, int, str, str]] = []

    def anotar(regla: str, m: re.Match, base: int = 0) -> None:
        ln, col = linea_col(texto, base + m.start())
        hallados.append((ln, col, regla, m.group(0)))

    for m in HEX.finditer(texto):
        anotar("hex", m)
    for m in COLOR_FUNCIONAL.finditer(texto):
        anotar("rgb", m)
    if f.suffix in {".ts", ".tsx"}:
        for c in CADENA.finditer(texto):
            for m in ARBITRARIO.finditer(c.group(0)):
                anotar("arbitrario", m, c.start())
            for m in PALETA.finditer(c.group(0)):
                anotar("paleta", m, c.start())
    return sorted(set(hallados))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    lista = archivos()
    if "--lista" in sys.argv:
        for f in lista:
            print(f.relative_to(RAIZ).as_posix())
        print(f"{len(lista)} archivos")
        return 0

    total = 0
    for f in lista:
        for ln, col, regla, valor in revisar(f):
            total += 1
            print(f"{f.relative_to(RAIZ).as_posix()}:{ln}:{col}  [{regla}]  {valor}")
    print(f"\n{len(lista)} archivos revisados · {total} valores prohibidos")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
