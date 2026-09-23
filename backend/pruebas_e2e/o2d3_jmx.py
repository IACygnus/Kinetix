"""ETAPA O2d.3 — la insercion del Backend Listener (O-D45, O-D46).

    docker exec jmeter_backend python3 /tmp/e2e/o2d3_jmx.py

Los tres casos que pide el sub-paso, con ficheros de verdad:
  1. Un `.jmx` SIN Backend Listener -> se le anade.
  2. Uno que YA lo trae -> se reemplaza, no se duplica, y se avisa.
  3. Un XML invalido -> error claro, no un volcado de pila.

Y lo que de verdad importa: que el resultado **lo abra JMeter** y que sus
valores sean los de la sesion. Eso no se comprueba leyendo el XML: se comprueba
lanzandolo.
"""
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, "/app")
from app.services.observabilidad.jmx_listener import (   # noqa: E402
    JmxInvalido, insertar, mensaje,
)

JMETER = "/opt/apache-jmeter-5.6.3/bin/jmeter"
URL = "http://influxdb:8086/api/v2/write?org=performance&bucket=jmeter"
TOKEN = "zztest-token-de-mentira"
CORRIDA = "zztest-o2d3-insercion"

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


SIN_LISTENER = b"""<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="ZZTEST sin listener" enabled="true">
      <boolProp name="TestPlan.functional_mode">false</boolProp>
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" testname="UDV" enabled="true">
        <collectionProp name="Arguments.arguments"/>
      </elementProp>
    </TestPlan>
    <hashTree>
      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="Usuarios ZZTEST" enabled="true">
        <stringProp name="ThreadGroup.num_threads">2</stringProp>
        <stringProp name="ThreadGroup.ramp_time">1</stringProp>
        <elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController" testname="Loop" enabled="true">
          <boolProp name="LoopController.continue_forever">false</boolProp>
          <stringProp name="LoopController.loops">2</stringProp>
        </elementProp>
        <stringProp name="ThreadGroup.on_sample_error">continue</stringProp>
      </ThreadGroup>
      <hashTree>
        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="ZZTEST salud" enabled="true">
          <stringProp name="HTTPSampler.domain">localhost</stringProp>
          <stringProp name="HTTPSampler.port">8001</stringProp>
          <stringProp name="HTTPSampler.protocol">http</stringProp>
          <stringProp name="HTTPSampler.path">/health</stringProp>
          <stringProp name="HTTPSampler.method">GET</stringProp>
          <elementProp name="HTTPsampler.Arguments" elementType="Arguments" guiclass="HTTPArgumentsPanel" testclass="Arguments" testname="args" enabled="true">
            <collectionProp name="Arguments.arguments"/>
          </elementProp>
        </HTTPSamplerProxy>
        <hashTree/>
      </hashTree>
    </hashTree>
  </hashTree>
</jmeterTestPlan>
"""


def main():
    # ---------- 1. Sin Backend Listener ----------
    print("--- 1. Un .jmx SIN Backend Listener ---")
    nuevo, informe = insertar(SIN_LISTENER, URL, TOKEN, CORRIDA)
    ok(not informe["reemplazado"], "no dice que haya reemplazado nada")
    print(f"    {mensaje(informe)[:110]}")

    raiz = ET.fromstring(nuevo)
    listeners = raiz.findall(".//BackendListener")
    ok(len(listeners) == 1, f"queda exactamente UN Backend Listener ({len(listeners)})")

    valores = {e.find("stringProp[@name='Argument.name']").text:
               e.find("stringProp[@name='Argument.value']").text
               for e in raiz.findall(".//BackendListener//elementProp[@elementType='Argument']")}
    ok(valores.get("application") == CORRIDA,
       f"la corrida es la de la sesion: {valores.get('application')}")
    ok(valores.get("influxdbToken") == TOKEN, "y el token, el de la sesion")
    ok(valores.get("summaryOnly") == "false",
       "summaryOnly en «false», para ver transaccion por transaccion")

    # El original no se toca (O-D46).
    ok(b"BackendListener" not in SIN_LISTENER,
       "el contenido original sigue sin Backend Listener: se devolvio una copia")

    # Dentro del grupo de hilos, que es donde JMeter lo espera.
    ok("grupo de hilos" in str(informe["donde"]),
       f"se colgo {informe['donde']}")

    # ---------- Y LO QUE IMPORTA: ¿lo abre JMeter? ----------
    print("\n--- ¿Lo abre JMeter de verdad? ---")
    open("/tmp/zztest_o2d3.jmx", "wb").write(nuevo)
    salida = subprocess.run(
        [JMETER, "-n", "-t", "/tmp/zztest_o2d3.jmx", "-l", "/tmp/zztest_o2d3.jtl"],
        capture_output=True, text=True, timeout=180, cwd="/tmp")
    texto = salida.stdout + salida.stderr
    ok("Created the tree successfully" in texto,
       "JMeter carga el plan sin quejarse")
    ok("end of run" in texto, "y lo ejecuta hasta el final")
    resumen = [l for l in salida.stdout.splitlines() if l.startswith("summary =")]
    print(f"    {resumen[-1] if resumen else texto[-160:]}")
    # El token es de mentira: el listener se quejara al ESCRIBIR, y eso esta
    # bien. Lo que no puede pasar es que el plan no cargue.
    ok("ERROR" not in texto.split("Created the tree successfully")[0],
       "no hay errores ANTES de cargar el plan")

    # ---------- 2. Uno que YA lo trae ----------
    print("\n--- 2. Un .jmx que YA trae un Backend Listener ---")
    otra = "zztest-o2d3-la-segunda"
    segundo, informe2 = insertar(nuevo, URL, "otro-token", otra)
    ok(informe2["reemplazado"], "avisa de que ha reemplazado uno")
    print(f"    {mensaje(informe2)[:150]}")
    raiz2 = ET.fromstring(segundo)
    ok(len(raiz2.findall(".//BackendListener")) == 1,
       "sigue habiendo UNO, no dos")
    valores2 = {e.find("stringProp[@name='Argument.name']").text:
                e.find("stringProp[@name='Argument.value']").text
                for e in raiz2.findall(".//BackendListener//elementProp[@elementType='Argument']")}
    ok(valores2.get("application") == otra,
       "y es el de la sesion nueva, no el viejo")

    open("/tmp/zztest_o2d3b.jmx", "wb").write(segundo)
    salida2 = subprocess.run(
        [JMETER, "-n", "-t", "/tmp/zztest_o2d3b.jmx", "-l", "/tmp/zztest_o2d3b.jtl"],
        capture_output=True, text=True, timeout=180, cwd="/tmp")
    ok("Created the tree successfully" in salida2.stdout + salida2.stderr,
       "tras reemplazar, JMeter sigue abriendo el plan")

    # ---------- 3. Lo que no vale ----------
    print("\n--- 3. Archivos que no valen ---")
    for datos, que in (
        (b"esto no es xml ni de lejos", "un archivo que no es XML"),
        (b"<?xml version='1.0'?><otraCosa><a/></otraCosa>", "un XML que no es de JMeter"),
        (b"<?xml version='1.0'?><jmeterTestPlan version='1.2'><hashTree/></jmeterTestPlan>",
         "un plan de JMeter sin Test Plan"),
    ):
        try:
            insertar(datos, URL, TOKEN, CORRIDA)
            ok(False, f"{que}: deberia haber fallado y no fallo")
        except JmxInvalido as exc:
            ok(len(str(exc)) > 20 and "Traceback" not in str(exc),
               f"{que}: error claro -> {str(exc)[:70]}")

    print()
    if fallos:
        print(f"FALLOS: {len(fallos)}")
        for texto in fallos:
            print(f"  - {texto}")
        sys.exit(1)
    print("O2d.3 — LA INSERCION EN EL JMX: TODO PASA")


if __name__ == "__main__":
    main()
