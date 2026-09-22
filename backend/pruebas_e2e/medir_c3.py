"""Mide C3: separa LINEAS MOVIDAS de CAMBIOS REALES en un archivo protegido.

C3 (corregida) se aplica solo a los cambios reales. Una linea eliminada del archivo
protegido que aparece literalmente en el archivo destino es un MOVIMIENTO, no un
cambio, siempre que la equivalencia este demostrada.

Uso:
    python3 medir_c3.py <diff.txt> <archivo_destino> [archivo_destino...]

`diff.txt` es la salida de `git diff <base> <head> -- <archivo_protegido>`.
"""
import re
import sys


def main():
    diff_path = sys.argv[1]
    destinos = []
    for p in sys.argv[2:]:
        try:
            destinos.append(open(p, encoding="utf-8").read())
        except Exception as e:
            print(f"aviso: no se pudo leer {p}: {e}")
    texto_destino = "\n".join(destinos)

    quitadas, anadidas = [], []
    for linea in open(diff_path, encoding="utf-8", errors="replace"):
        if linea.startswith("---") or linea.startswith("+++"):
            continue
        if linea.startswith("-"):
            quitadas.append(linea[1:].rstrip("\n").rstrip("\r"))
        elif linea.startswith("+"):
            anadidas.append(linea[1:].rstrip("\n").rstrip("\r"))

    def esta_en_destino(l):
        t = l.strip()
        if not t:
            return True          # lineas en blanco: no son un cambio real
        return t in texto_destino

    mov_q = [l for l in quitadas if esta_en_destino(l)]
    real_q = [l for l in quitadas if not esta_en_destino(l)]
    # Una linea anadida que solo reordena o invoca lo movido tambien cuenta aparte
    real_a = [l for l in anadidas if l.strip()]

    print("%-22s %s" % ("ELIMINADAS", len(quitadas)))
    print("%-22s %s" % ("  movidas al destino", len(mov_q)))
    print("%-22s %s" % ("  CAMBIOS REALES", len(real_q)))
    print("%-22s %s" % ("ANADIDAS (reales)", len(real_a)))
    print("%-22s %s" % ("TOTAL CAMBIOS REALES", len(real_q) + len(real_a)))
    if real_q:
        print("\n--- eliminadas que NO estan en el destino ---")
        for l in real_q[:40]:
            print("   -", l.strip()[:90])
    if real_a:
        print("\n--- anadidas ---")
        for l in real_a[:40]:
            print("   +", l.strip()[:90])


if __name__ == "__main__":
    main()
