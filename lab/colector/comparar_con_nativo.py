"""ETAPA O2a.2 — ¿de verdad sale lo mismo que el complemento nativo?

    docker cp lab/colector/comparar_con_nativo.py lab_colector:/tmp/
    docker exec lab_colector python3 /tmp/comparar_con_nativo.py

O-D13 promete que las metricas sin agente se escriben con **los mismos nombres
de medida y de campo** que los complementos nativos de Telegraf. Una promesa asi
no se declara: se comprueba. Y aqui se puede comprobar de verdad, porque
`/proc` no esta separado por contenedor — el recolector y `lab_servidor`
miran la MISMA maquina anfitriona para CPU, memoria y disco—, asi que los dos
caminos son directamente comparables.

Lo que hace:
  1. Levanta un Telegraf con los complementos NATIVOS (cpu, mem, disk, diskio,
     system, net, processes) y una salida a fichero. Lo deja 25 segundos, para
     que la CPU tenga dos lecturas que restar.
  2. Corre el lector por SSH.
  3. Compara, medida a medida: que campos tienen los dos, cuales solo el
     nativo, cuales solo el nuestro. Y para los numericos que observan lo mismo,
     cuanto se separan.

Lo que NO compara, y se dice: `net` y `processes` SI estan separados por
contenedor, asi que el nativo ve la red y los procesos del recolector y el
nuestro los de `lab_servidor`. Son numeros distintos con razon.
"""
import os
import re
import subprocess
import sys
import time

NATIVO_CONF = "/tmp/nativo.conf"
NATIVO_SALIDA = "/tmp/nativo.out"
SEGUNDOS = int(os.environ.get("KX_SEGUNDOS", "25"))

# Las dos primeras comparten maquina; las dos ultimas no (espacio de nombres).
COMPARTEN_MAQUINA = ["cpu", "mem", "disk", "diskio", "system"]
SEPARADAS = ["net", "processes"]

CONFIGURACION = """
[agent]
  interval = "10s"
  flush_interval = "10s"
  omit_hostname = true
  round_interval = false

[[outputs.file]]
  files = ["%s"]
  data_format = "influx"

[[inputs.cpu]]
  percpu = false
  totalcpu = true
  report_active = false

[[inputs.mem]]

[[inputs.disk]]

[[inputs.diskio]]

[[inputs.system]]

[[inputs.net]]

[[inputs.processes]]
""" % NATIVO_SALIDA


def trocear_linea(linea):
    """«medida,etiqueta=v campo=1i,otro=2 123» -> (medida, {campos})."""
    coincidencia = re.match(r"^([^,\s]+)((?:,[^\s]+)?)\s+(.*?)(?:\s+\d+)?$", linea)
    if not coincidencia:
        return None, {}
    medida = coincidencia.group(1)
    campos = {}
    # Se parte por comas que no esten dentro de comillas.
    for trozo in re.findall(r'(?:[^,"]|"(?:\\.|[^"])*")+', coincidencia.group(3)):
        if "=" not in trozo:
            continue
        clave, valor = trozo.split("=", 1)
        campos[clave.strip()] = valor.strip()
    return medida, campos


def numero(texto):
    try:
        return float(texto.rstrip("i"))
    except ValueError:
        return None


def recoger(lineas):
    """{medida: {campo: valor}} quedandose con la ultima lectura de cada una."""
    salida = {}
    for linea in lineas:
        if not linea.strip() or linea.startswith("#"):
            continue
        medida, campos = trocear_linea(linea.strip())
        if medida:
            salida.setdefault(medida, {}).update(campos)
    return salida


def main():
    with open(NATIVO_CONF, "w") as fichero:
        fichero.write(CONFIGURACION)
    if os.path.exists(NATIVO_SALIDA):
        os.remove(NATIVO_SALIDA)

    print("1. Telegraf con los complementos NATIVOS, %d segundos..." % SEGUNDOS)
    proceso = subprocess.Popen(["telegraf", "--config", NATIVO_CONF],
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    time.sleep(SEGUNDOS)
    proceso.terminate()
    try:
        proceso.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proceso.kill()

    if not os.path.exists(NATIVO_SALIDA):
        sys.exit("el Telegraf nativo no escribio nada:\n"
                 + (proceso.stderr.read().decode()[-600:] if proceso.stderr else ""))
    nativo = recoger(open(NATIVO_SALIDA).read().splitlines())

    print("2. El lector por SSH...")
    # Dos veces: la primera deja el estado de la CPU, la segunda ya resta.
    for _ in range(2):
        hecho = subprocess.run(["python3", "/opt/kinetix/linux_sin_agente.py"],
                               capture_output=True, text=True, timeout=60)
        time.sleep(3)
    if hecho.returncode != 0:
        sys.exit("el lector fallo:\n" + hecho.stderr[-600:])
    nuestro = recoger(hecho.stdout.splitlines())

    print()
    print("=" * 74)
    print("MEDIDAS QUE OBSERVAN LA MISMA MAQUINA (/proc no esta separado)")
    print("=" * 74)
    total_iguales = total_solo_nativo = total_solo_nuestro = 0

    for medida in COMPARTEN_MAQUINA:
        campos_n = set(nativo.get(medida, {}))
        campos_m = set(nuestro.get(medida, {}))
        if not campos_n and not campos_m:
            print("\n%-10s  ninguno de los dos la produjo" % medida)
            continue
        comunes = sorted(campos_n & campos_m)
        solo_n = sorted(campos_n - campos_m)
        solo_m = sorted(campos_m - campos_n)
        total_iguales += len(comunes)
        total_solo_nativo += len(solo_n)
        total_solo_nuestro += len(solo_m)

        print("\n%s" % medida)
        print("  identicos (%d): %s" % (len(comunes), ", ".join(comunes) or "—"))
        if solo_n:
            print("  SOLO el nativo (%d): %s" % (len(solo_n), ", ".join(solo_n)))
        if solo_m:
            print("  solo el nuestro (%d): %s" % (len(solo_m), ", ".join(solo_m)))

        # Y para los que miran lo mismo, cuanto se parecen los numeros.
        if medida in ("cpu", "mem", "system"):
            desvios = []
            for campo in comunes:
                a, b = numero(nativo[medida][campo]), numero(nuestro[medida][campo])
                if a is None or b is None:
                    continue
                if abs(a) < 1e-9 and abs(b) < 1e-9:
                    desvios.append((campo, 0.0))
                else:
                    base = max(abs(a), abs(b))
                    desvios.append((campo, 100.0 * abs(a - b) / base))
            desvios.sort(key=lambda par: -par[1])
            if desvios:
                peores = ", ".join("%s %.1f%%" % (c, d) for c, d in desvios[:4])
                print("  mayor separacion: %s" % peores)

    print()
    print("=" * 74)
    print("MEDIDAS QUE NO SE PUEDEN COMPARAR (cada contenedor tiene la suya)")
    print("=" * 74)
    for medida in SEPARADAS:
        campos_n = set(nativo.get(medida, {}))
        campos_m = set(nuestro.get(medida, {}))
        comunes = sorted(campos_n & campos_m)
        solo_n = sorted(campos_n - campos_m)
        solo_m = sorted(campos_m - campos_n)
        print("\n%s  (nombres de campo, no valores)" % medida)
        print("  identicos (%d): %s" % (len(comunes), ", ".join(comunes) or "—"))
        if solo_n:
            print("  SOLO el nativo (%d): %s" % (len(solo_n), ", ".join(solo_n)))
        if solo_m:
            print("  solo el nuestro (%d): %s" % (len(solo_m), ", ".join(solo_m)))

    print()
    print("Medidas que solo tenemos nosotros: %s"
          % ", ".join(sorted(set(nuestro) - set(nativo))) or "ninguna")
    print("Medidas nativas que no reproducimos: %s"
          % (", ".join(sorted(set(nativo) - set(nuestro))) or "ninguna"))
    print("\nCampos con el mismo nombre en las medidas comparables: %d"
          % total_iguales)
    print("Campos que solo trae el nativo: %d" % total_solo_nativo)
    print("Campos que solo traemos nosotros: %d" % total_solo_nuestro)


if __name__ == "__main__":
    main()
