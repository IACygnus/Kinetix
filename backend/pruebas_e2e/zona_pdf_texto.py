"""Reporte 146 — el TEXTO de los PDF de la suite de zona horaria. FUERA del contenedor.

    docker cp jmeter_backend:/tmp/146_zz.pdf .  &&  docker cp jmeter_backend:/tmp/146_zz_int.pdf .
    python zona_pdf_texto.py 146_zz.pdf 146_zz_int.pdf [146_sodexo.pdf]

Necesita `pdftotext` (Git for Windows lo trae) o PyMuPDF. Cuenta lo que se ve en
el documento: la cabecera en hora de Colombia y ninguna hora UTC de la prueba.
"""
import re
import shutil
import subprocess
import sys

ESPERADO = {"146_zz": ("17:16:37", "17:18:36", r"(?<![\d:])22:1[68]:\d\d"),
            "146_zz_int": ("17:16:37", "17:18:36", r"(?<![\d:])22:1[68]:\d\d"),
            "146_sodexo": ("17:16:37", "18:03:51", r"(?<![\d:])(22:16:37|23:03:51)")}


def texto(pdf):
    if shutil.which("pdftotext"):
        return subprocess.run(["pdftotext", "-enc", "UTF-8", "-layout", pdf, "-"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace").stdout
    import pymupdf
    return "".join(p.get_text() for p in pymupdf.open(pdf))


fallos = 0
for pdf in sys.argv[1:]:
    clave = next(k for k in ESPERADO if pdf.replace("\\", "/").split("/")[-1].startswith(k + "."))
    ini, fin, utc = ESPERADO[clave]
    t = texto(pdf)
    bien = ini in t and fin in t and not re.search(utc, t)
    fallos += not bien
    print(("  ok    " if bien else "  FALLA ") + f"{pdf}: {ini} y {fin} presentes, ninguna hora UTC")
print("\nTODO PASA" if not fallos else f"\n{fallos} FALLA(N)")
sys.exit(1 if fallos else 0)
