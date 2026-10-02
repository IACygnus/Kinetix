"""Reporte 151, parte 2 — los percentiles, tal cual los escribe Fredy (regla 3 del estilo).

    docker exec -w /app -e PYTHONPATH=/app/pruebas_e2e:/app jmeter_backend python3 /app/pruebas_e2e/b5_i_percentiles.py

Sin IA y sin base:
  - la regla 3 de la guía y el modelo de resumen de Fredy con su frase original
    («percentil 95 de 8.108 ms»);
  - las frases que reciben los prompts ya no traducen a personas;
  - el detector avisa de la LISTA (más de dos percentiles en un párrafo o
    viñeta), no de nombrar uno tal cual.
"""
import sys

import b5_comun as B
from b5_comun import ok

sys.path.insert(0, "/app")
from app.services.ai import gemini as G   # noqa: E402
from app.services.ai.estilo import BLOQUE_ESTILO, REFERENCIA_ESTILO, detectar_estilo, percentil_frase, terminos_de   # noqa: E402

print("== 1. La guía")
ok("3. PERCENTILES TAL CUAL" in BLOQUE_ESTILO and "«percentil 95 de\n   8.108 ms»" in BLOQUE_ESTILO,
   "la regla 3: tal cual, con el ejemplo de Fredy")
ok("uno o dos por párrafo" in BLOQUE_ESTILO and "P50/P90/P95/P99" in BLOQUE_ESTILO, "como mucho uno o dos; nunca la lista")
ok("en personas" not in BLOQUE_ESTILO and "1 de cada" not in BLOQUE_ESTILO, "ya no se pide contarlos en personas")
ok("percentil 95 de 8.108 ms y un máximo de 9.221 ms" in REFERENCIA_ESTILO, "el modelo de resumen, con la frase original de Fredy")
ok("percentil 95 de 8.108 ms" in G.SYSTEM_PROMPT, "y así llega al sistema")

print("== 2. Lo que reciben los prompts")
ok(percentil_frase(95, 8108) == "percentil 95 de 8.108 ms" and percentil_frase(50, 142) == "mediana de 142 ms",
   "percentil_frase: «percentil 95 de 8.108 ms», «mediana de 142 ms»")

print("== 3. El detector")
uno = "El Servicio A tuvo un promedio de 4.823 ms, percentil 95 de 8.108 ms y un máximo de 9.221 ms."
dos = "Percentil 90 de 7.753 ms y percentil 95 de 8.108 ms en el Servicio A."
lista = "Los tiempos fueron P50 de 4.800 ms, P90 de 7.753 ms, P95 de 8.108 ms y P99 de 8.900 ms."
ok(detectar_estilo(uno, "summary_table") == [], "un percentil tal cual: sin aviso")
ok(detectar_estilo(dos, "summary_table") == [], "dos en el mismo párrafo: sin aviso")
av = detectar_estilo(lista, "summary_table")
ok(len(av) == 1 and av[0]["tipo"] == "demasiados_percentiles" and terminos_de(av) == ["4 percentiles en un párrafo"],
   "la lista P50/P90/P95/P99: aviso «4 percentiles en un párrafo»")
vinetas = "• Servicio A: percentil 90 de 7.753 ms y percentil 95 de 8.108 ms.\n• Servicio C: percentil 99 de 900 ms."
ok(detectar_estilo(vinetas, "conclusions") == [], "se cuenta por viñeta: dos y uno, sin aviso")
ok(detectar_estilo(REFERENCIA_ESTILO.split("«", 1)[1].split("»", 1)[0], "summary_table") == [],
   "el ejemplo de sección de la guía, sin aviso")

B.fin("B5 I (percentiles)")
