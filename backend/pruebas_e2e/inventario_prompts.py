"""BLOQUE 2, paso 1 — el inventario de los prompts de analisis, legible para Fredy.

    docker exec -w /app jmeter_backend python3 /app/pruebas_e2e/inventario_prompts.py

Escribe /tmp/r2/inventario_prompts.html: cada prompt entero y, al lado, lo que
produjo en el «despues» de Nova (`/tmp/r2/corrida_despues_35ca5b92.json`, R2).
LLEVA DATOS DE CLIENTES: se copia a C:\\proyectos\\Kinetix_pruebas\\r2\\, nunca a
docs/. Los prompts que no se corrieron en R2 (capturas, comparativo, integrado)
se ensenan como plantilla, leida del codigo en el momento.

Solo lectura: no llama a la IA ni abre la base. Las fichas son el analisis del
reporte 137.
"""
import html
import json
import sys

sys.path.insert(0, "/app")

from app.services.ai import gemini as G
from app.services.ai.estilo import PERMISO_VEREDICTO

CORRIDA = "/tmp/r2/corrida_despues_35ca5b92.json"
SALIDA = "/tmp/r2/inventario_prompts.html"

GENERAL_PARAMS = ("gpt-5.5 · esfuerzo de razonamiento «medium» (el de la configuración) · "
                  "sin temperatura (la familia gpt-5 no la admite: se filtra) · tope de salida 16.384 tokens")

# (clave, titulo, fuente, ficha). fuente: ("run", seccion, con_transaccion) o ("tpl", archivo, desde, hasta)
FICHAS = [
    ("summary_table", "Resumen de la prueba (tabla resumen)", ("run", "summary_table", False), {
        "produce": "El análisis debajo de la tabla resumen del informe general. Es la «lectura base»: las demás secciones generales la reciben.",
        "donde": "services/ai/gemini.py:1413 (analyze_summary_table), prompt en :1450",
        "datos": "Tabla por transacción, transacciones agrupadas por tiempo, percentiles en personas, resumen global, criterios de aceptación y los «hechos de la prueba» de R2 (quién concentra los fallos, primer y último fallo).",
        "reglas": "Máximo 180 palabras. Nombrar todas las transacciones. Decir qué transacción concentra los fallos, si es puntual o sostenido y cuál es el cuello. Sin dictamen de producción.",
        "rampa": "No. Recibe la duración, pero no dónde acaba la subida ni empieza la bajada.",
        "fallos": "Solo primero y último, más «repartidos a lo largo de toda la prueba» o no.",
        "cache": "Nada propio que adelantar: es la primera sección. El bloque común «unidad de medida + tipo de prueba» ya va delante.",
    }),
    ("errors", "Errores", ("run", "errors", False), {
        "produce": "El análisis de la tabla de errores del informe general.",
        "donde": "services/ai/gemini.py:1496 (analyze_errors), prompt en :1550",
        "datos": "Errores por transacción, código y mensaje con «Cuándo: del min A al min B», agrupados por código, contexto global, criterios y la lectura base.",
        "reglas": "Máximo 140 palabras. Nombrar cada transacción con error. Causa probable como hipótesis. Sin dictamen ni plan de trabajo.",
        "rampa": "No.",
        "fallos": "Solo primero y último de cada error («del min A al min B»). No pide dónde se concentran.",
        "cache": "La lectura base (~1.300 caracteres, igual en 7 secciones: esta y las 6 gráficas) y los criterios podrían ir delante; hoy van detrás de los datos.",
    }),
    ("chart_response_times", "Tiempos de respuesta por transacción (gráfica)", ("run", "chart_response_times", False), {
        "produce": "El análisis de la gráfica «Response Times» del informe general.",
        "donde": "services/ai/gemini.py:1582 (analyze_chart), prompt en :1652; instrucción en :1609",
        "datos": "Promedio, mínimo, máximo y percentiles por transacción, la serie de R2 de cada una (extremos, tramos de 5 min, episodios sostenidos, tendencia, sus 3 tiempos más altos), agrupación por tiempo, criterios y lectura base.",
        "reglas": "Máximo 130 palabras. Nombrar todas. Contrastar la más rápida con la más lenta con la cifra dada. Señalar los picos (10 veces el promedio o más). Decir cuándo aparecen los picos, si coinciden y si son tramos sostenidos o puntos aislados.",
        "rampa": "No. Los tramos son de 5 minutos fijos, no las fases de la prueba.",
        "fallos": "Degradación: sí, pide dónde (tramos, episodios, coincidencias entre transacciones).",
        "cache": "La lectura base y los criterios, delante. Es el prompt más largo (5.200-6.200 tokens).",
    }),
    ("chart_latency", "Latencia (gráfica)", ("run", "chart_latency", False), {
        "produce": "El análisis de la gráfica «Latency».",
        "donde": "services/ai/gemini.py:1582 (analyze_chart), instrucción en :1638",
        "datos": "Latencia y tiempo medio, volumen enviado y recibido, la serie de R2 de la latencia, criterios y lectura base.",
        "reglas": "Máximo 130 palabras. Espera hasta el primer byte frente a descarga, tramos, tendencia y cuándo son los picos. No atribuirla solo a la red.",
        "rampa": "No.",
        "fallos": "Degradación: sí (tramos, episodios, picos con su minuto).",
        "cache": "La lectura base y los criterios, delante.",
    }),
    ("chart_error_rate", "Tasa de error (gráfica)", ("run", "chart_error_rate", False), {
        "produce": "El análisis de la gráfica «Error Rate».",
        "donde": "services/ai/gemini.py:1582 (analyze_chart), instrucción en :1640",
        "datos": "Tasa global, la serie de R2 (extremos, lo habitual, tramos, episodios, tendencia, primer y último fallo), criterios y lectura base.",
        "reglas": "Máximo 130 palabras. Entre qué valores se movió, picos y cuándo, sostenido o aislado, momentos sin fallos y disponibilidad real.",
        "rampa": "No.",
        "fallos": "Sí: es la única sección general que pide si el fallo es constante, intermitente o va a más. Pero la serie también le da el primero y el último, y el modelo los cita.",
        "cache": "La lectura base y los criterios, delante.",
    }),
    ("chart_codes_per_second", "Códigos de respuesta (gráfica)", ("run", "chart_codes_per_second", False), {
        "produce": "El análisis de la gráfica «Response Codes».",
        "donde": "services/ai/gemini.py:1582 (analyze_chart), instrucción en :1642",
        "datos": "Recuento por código, y por código: primera y última aparición, pico por segundo y reparto por tramos de 5 min. Criterios y lectura base.",
        "reglas": "Máximo 130 palabras. Qué significa cada código, cuándo aparece por primera vez cada código de fallo y si se concentra o se reparte.",
        "rampa": "No.",
        "fallos": "Pide «cuándo aparece por primera vez» y «si se concentra en algún tramo»: las dos cosas. La primera empuja a citar el primero.",
        "cache": "La lectura base y los criterios, delante.",
    }),
    ("chart_transactions_per_second", "Transacciones por segundo (gráfica)", ("run", "chart_transactions_per_second", False), {
        "produce": "El análisis de la gráfica «TPS».",
        "donde": "services/ai/gemini.py:1582 (analyze_chart), instrucción en :1644",
        "datos": "Caudal por transacción y su serie de R2 (tramos, tendencia, arranque), criterios y lectura base.",
        "reglas": "Máximo 130 palabras. Reparto entre transacciones, si se sostiene o cae y en qué minutos, cómo fue el arranque.",
        "rampa": "Solo de forma indirecta: pide «cómo fue el arranque», pero no recibe dónde acaba la subida.",
        "fallos": "No aplica (es caudal).",
        "cache": "La lectura base y los criterios, delante.",
    }),
    ("chart_active_threads", "Usuarios activos (gráfica)", ("run", "chart_active_threads", False), {
        "produce": "El análisis de la gráfica «Active Threads». Solo en el informe general.",
        "donde": "services/ai/gemini.py:1582 (analyze_chart), instrucción en :1646",
        "datos": "La serie de hilos: máximo, cuándo se alcanza por primera y por última vez, arranque, final, y tiempo y error por nivel de concurrencia. Criterios y lectura base.",
        "reglas": "Máximo 130 palabras. Cómo entraron los usuarios (subida, meseta y bajada si la hubo), cuánto se sostuvo el máximo.",
        "rampa": "**Sí.** Es el único prompt que sabe dónde acaban la subida y la meseta. Pero lo que sabe no llega a los demás como dato: solo como el texto que escribe.",
        "fallos": "Error por nivel de concurrencia, no por momento.",
        "cache": "La lectura base y los criterios, delante, como en las demás gráficas.",
    }),
    ("conclusions", "Conclusiones", ("run", "conclusions", False), {
        "produce": "Las conclusiones del final del informe. Una sola vez, de toda la prueba. Sí dictamina.",
        "donde": "services/ai/gemini.py:1718 (generate_conclusions), prompt en :1784",
        "datos": "Cifras clave, percentiles, agrupación por tiempo, criterios y veredicto, y **los textos ya escritos de todas las secciones generales**. No recibe ninguna serie.",
        "reglas": "6 conclusiones numeradas de 3 a 5 oraciones, máximo 350 palabras. Resultado frente a criterios, tiempos, errores, capacidad, estabilidad, qué resolver primero. Mensaje de sistema con permiso de dictamen.",
        "rampa": "Solo si la sección de usuarios activos lo escribió. No como dato.",
        "fallos": "Hereda lo que digan las secciones: en Nova, primero y último.",
        "cache": "Usa la variante del mensaje de sistema con permiso de dictamen: comparte con los demás solo hasta la regla 15.",
    }),
    ("recommendations", "Recomendaciones", ("run", "recommendations", False), {
        "produce": "Las recomendaciones del final del informe. Sí dictamina.",
        "donde": "services/ai/gemini.py:1842 (generate_recommendations), prompt en :1903",
        "datos": "Cifras, criterios y los textos ya escritos de las secciones, agrupados por tema (errores, tasa, códigos, tiempos, capacidad, infraestructura).",
        "reglas": "Máximo 350 palabras. 2-3 críticas, 2-3 altas, 1-2 medias; cada una de 3 o 4 oraciones con problema, acción y transacciones con cifras.",
        "rampa": "Igual que las conclusiones: de segunda mano.",
        "fallos": "De segunda mano.",
        "cache": "Comparte con las conclusiones la variante de dictamen y casi todos los textos de las secciones: si fueran en el mismo orden y delante, la segunda llamada reutilizaría la primera.",
    }),
    ("redirects", "Redirecciones", ("tpl", "/app/app/services/ai/gemini.py", 1686, 1712), {
        "produce": "El análisis de las redirecciones. Solo si la prueba las tiene: ninguna de las tres de R2 las tenía.",
        "donde": "services/ai/gemini.py:1671 (analyze_redirects), prompt en :1686",
        "datos": "Número de redirecciones y de muestras principales, y las etiquetas.",
        "reglas": "Las del mensaje de sistema y las de la plantilla (ver a la izquierda).",
        "rampa": "No.",
        "fallos": "No aplica.",
        "cache": "Lo mismo que las demás generales.",
    }),
    ("txreport_summary", "Transacción — resumen", ("run", "txreport_summary", True), {
        "produce": "El resumen de una transacción en su propio informe. Es la lectura base de esa transacción.",
        "donde": "services/ai/transaction_report.py:150 (build_section_prompts); instrucciones en :84 (INSTRUCCIONES)",
        "datos": "Métricas de la transacción, percentiles, el criterio que se le aplica, y **las cinco series de R2** de esa transacción (tiempos, latencia, error, códigos, caudal).",
        "reglas": "Máximo 200 palabras. Solo esa transacción. Máximo y ratio obligatorios. Con los minutos de las series: si fallos y picos son puntuales o sostenidos.",
        "rampa": "No. Las series de transacción no llevan los hilos.",
        "fallos": "Pide puntual o sostenido; la serie de error le da además el peor minuto y el primero y el último.",
        "cache": "Empieza por el nombre de la transacción, no por el bloque común: de una transacción a otra solo comparten el mensaje de sistema.",
    }),
    ("txreport_chart_response_times", "Transacción — tiempos de respuesta", ("run", "txreport_chart_response_times", True), {
        "produce": "El análisis de la gráfica de tiempos de esa transacción.",
        "donde": "services/ai/transaction_report.py:150; instrucción en :87",
        "datos": "Métricas y criterio de la transacción, su serie de tiempos de R2, y el resumen ya escrito de esa transacción (lectura base).",
        "reglas": "Máximo 130 palabras. Nivel base, picos y en qué minuto, tramos sostenidos o puntos aislados.",
        "rampa": "No.",
        "fallos": "Degradación: sí.",
        "cache": "La cabecera de la transacción ya va delante y es igual en sus 6 secciones. Falta que lo común a todas las transacciones vaya antes que el nombre.",
    }),
    ("txreport_chart_latency", "Transacción — latencia", ("run", "txreport_chart_latency", True), {
        "produce": "El análisis de la gráfica de latencia de esa transacción.",
        "donde": "services/ai/transaction_report.py:150; instrucción en :88",
        "datos": "Como la anterior, con la serie de latencia.",
        "reglas": "Máximo 130 palabras. Espera hasta el primer byte frente a descarga y cómo se mueve.",
        "rampa": "No.",
        "fallos": "Degradación: sí.",
        "cache": "Igual que la anterior.",
    }),
    ("txreport_chart_error_rate", "Transacción — tasa de error", ("run", "txreport_chart_error_rate", True), {
        "produce": "El análisis de la gráfica de error de esa transacción.",
        "donde": "services/ai/transaction_report.py:150; instrucción en :89",
        "datos": "Como la anterior, con la serie de error (incluye el reparto por minuto, el peor y el mejor minuto, y el primer y el último fallo).",
        "reglas": "Máximo 130 palabras. Entre qué valores se movió, peor y mejor minuto, constante, intermitente o concentrado.",
        "rampa": "No.",
        "fallos": "Sí: pide concentración y peor minuto.",
        "cache": "Igual que la anterior.",
    }),
    ("txreport_chart_codes", "Transacción — códigos de respuesta", ("run", "txreport_chart_codes", True), {
        "produce": "El análisis de la gráfica de códigos de esa transacción.",
        "donde": "services/ai/transaction_report.py:150; instrucción en :90",
        "datos": "Como la anterior, con los códigos en el tiempo.",
        "reglas": "Máximo 130 palabras. Qué indica el reparto, cuándo aparece cada código de fallo y si se reparte o se concentra.",
        "rampa": "No.",
        "fallos": "Las dos cosas, como la general de códigos.",
        "cache": "Igual que la anterior.",
    }),
    ("txreport_chart_tps", "Transacción — caudal", ("run", "txreport_chart_tps", True), {
        "produce": "El análisis de la gráfica de caudal de esa transacción.",
        "donde": "services/ai/transaction_report.py:150; instrucción en :91",
        "datos": "Como la anterior, con la serie de caudal.",
        "reglas": "Máximo 130 palabras. Si se sostiene o cae y en qué minutos, cómo fue el arranque.",
        "rampa": "Indirecta: pide el arranque sin saber dónde acaba la subida.",
        "fallos": "No aplica.",
        "cache": "Igual que la anterior.",
    }),
    ("image", "Captura (cada imagen de monitoreo o de evidencia)", ("tpl", "/app/app/services/ai/gemini.py", 1265, 1302), {
        "produce": "El texto debajo de cada captura, en «Capturas de infraestructura» y en «Evidencias».",
        "donde": "services/ai/gemini.py:1254 (analyze_image), prompt en :1295",
        "datos": "La imagen, su categoría, su título y la descripción que escribe el analista.",
        "reglas": "Máximo 300 palabras, párrafos de 3 a 5 oraciones, no inventar cifras. Monitoreo: tendencias, picos, umbrales. Evidencia: tipo de error, severidad, causa raíz.",
        "rampa": "No: ni siquiera sabe cuándo empezó la prueba.",
        "fallos": "No aplica.",
        "cache": "Lleva el bloque de estilo DENTRO del mensaje del usuario y sin la presentación del analista: no comparte prefijo con ningún otro prompt.",
        "params": "gpt-5.5 · sin esfuerzo de razonamiento (no se envía) · tope de salida 1.024 tokens, que en gpt-5.5 incluye el razonamiento · temperatura 0,3 (filtrada)",
    }),
    ("ocr", "Captura por OCR (respaldo de la anterior)", ("tpl", "/app/app/services/ai/gemini.py", 1368, 1377), {
        "produce": "El texto de una captura cuando falla el análisis de imagen: se lee el texto con OCR y se analiza.",
        "donde": "services/ai/gemini.py:1349 (_analyze_image_ocr_fallback), prompt en :1368",
        "datos": "El texto extraído por OCR, la categoría, el título y la descripción.",
        "reglas": "Máximo 200 palabras. «Si el texto es pobre o está vacío, di que no fue posible analizar el contenido»: contradice la regla 15 (sin disculpas).",
        "rampa": "No.",
        "fallos": "No aplica.",
        "cache": "Pasa por el mensaje de sistema normal.",
    }),
    ("monitoring_analysis", "Análisis global de las capturas de infraestructura", ("tpl", "/app/app/api/v1/endpoints/analysis_ai.py", 75, 99), {
        "produce": "El análisis que cruza todas las capturas de monitoreo con la prueba. Va a las conclusiones del integrado.",
        "donde": "api/v1/endpoints/analysis_ai.py:75",
        "datos": "Cifras globales de la prueba, percentiles y los textos ya escritos de cada captura.",
        "reglas": "Máximo 500 palabras. Relacionar picos de consumo con los momentos de mayor carga y proponer umbrales de alerta.",
        "rampa": "No, y se le pide relacionar picos con momentos de carga **sin darle ninguna línea de tiempo**.",
        "fallos": "No recibe series.",
        "cache": "Mensaje de sistema normal.",
        "extra": "Pide «propón umbrales», pero el mensaje de sistema que recibe (sin permiso de dictamen) prohíbe convertir el análisis en lista de tareas (regla 10).",
    }),
    ("evidence_analysis", "Análisis global de las evidencias", ("tpl", "/app/app/api/v1/endpoints/analysis_ai.py", 185, 207), {
        "produce": "El análisis que cruza todas las evidencias con la prueba. Va a las conclusiones del integrado.",
        "donde": "api/v1/endpoints/analysis_ai.py:185",
        "datos": "Cifras globales, percentiles y los textos ya escritos de cada evidencia.",
        "reglas": "Máximo 400 palabras. Ordenar por gravedad y proponer acciones correctivas.",
        "rampa": "No.",
        "fallos": "No recibe series.",
        "cache": "Mensaje de sistema normal.",
        "extra": "Misma contradicción que el de monitoreo: pide acciones con el mensaje de sistema que las prohíbe.",
    }),
    ("comparison_analysis", "Comparativa carga frente a estrés", ("tpl", "/app/app/api/v1/endpoints/compare.py", 108, 139), {
        "produce": "El informe comparativo entre una prueba de carga y una de estrés. Sí dictamina.",
        "donde": "api/v1/endpoints/compare.py:108",
        "datos": "Cifras globales de las dos pruebas, sus percentiles y el cambio porcentual. Ni series, ni textos de secciones, ni transacciones.",
        "reglas": "Máximo 500 palabras. Qué cambia para el usuario, dónde se rompe, si aguanta y qué hace falta en capacidad.",
        "rampa": "No, y en un estrés es justo lo que importa: en qué escalón se rompe.",
        "fallos": "No recibe series.",
        "cache": "Variante de dictamen.",
    }),
    ("unified_conclusions", "Conclusiones unificadas del integrado (POST /reports/integrated)", ("tpl", "/app/app/api/v1/endpoints/integrated_report.py", 1730, 1743), {
        "produce": "Las conclusiones y recomendaciones unificadas del informe integrado. Sí dictamina.",
        "donde": "api/v1/endpoints/integrated_report.py:1730",
        "datos": "Las conclusiones de cada ejecución y los textos de sus capturas y evidencias.",
        "reglas": "2 o 3 párrafos, luego hasta 7 conclusiones y hasta 7 recomendaciones. **Sin límite de palabras.**",
        "rampa": "No.",
        "fallos": "No recibe series.",
        "cache": "Variante de dictamen.",
    }),
    ("consolidated", "Análisis consolidado del integrado (por tipo de prueba)", ("tpl", "/app/app/api/v1/endpoints/integrated_report.py", 2219, 2261), {
        "produce": "El consolidado del integrado: un bloque de conclusiones y otro de recomendaciones por cada tipo de prueba (carga, estrés).",
        "donde": "api/v1/endpoints/integrated_report.py:2219",
        "datos": "Cifras, veredictos, conclusiones y recomendaciones originales, los análisis de las secciones (con las **correcciones del analista**, que tienen prioridad), las transacciones que incluye el documento, monitoreo y evidencias.",
        "reglas": "Dos bloques con encabezados exactos, 400 palabras cada uno. Recomendaciones por prioridad. No repetir literalmente.",
        "rampa": "No.",
        "fallos": "De segunda mano, de los textos.",
        "cache": "Variante de dictamen. Es el único prompt que recibe texto corregido por el analista.",
    }),
]


def leer(ruta, a, b):
    lineas = open(ruta, encoding="utf-8").read().splitlines()
    return "\n".join(lineas[a - 1:b])


CSS = """
:root{--fondo:#f6f7fb;--papel:#fff;--tinta:#1d2433;--suave:#5b6477;--borde:#dfe3ec;--acento:#4f46e5;
--si:#0f7b4f;--no:#b42318;--codigo:#f1f3f8}
@media (prefers-color-scheme:dark){:root{--fondo:#12151c;--papel:#1b2029;--tinta:#e6e9f0;--suave:#9aa3b5;
--borde:#2c3340;--acento:#8b85ff;--si:#5fd49c;--no:#ff8a80;--codigo:#151922}}
*{box-sizing:border-box}body{margin:0;background:var(--fondo);color:var(--tinta);
font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1440px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:26px;margin:0 0 6px}h2{font-size:20px;margin:40px 0 10px;padding-top:12px;border-top:3px solid var(--acento)}
.nota{color:var(--suave);max-width:900px}
nav{columns:3 260px;margin:12px 0 0}nav a{display:block;color:var(--acento);text-decoration:none;padding:2px 0}
dl.ficha{display:grid;grid-template-columns:200px 1fr;gap:6px 14px;background:var(--papel);border:1px solid var(--borde);
border-radius:10px;padding:12px 16px;margin:0 0 12px}
dl.ficha dt{font-weight:600;color:var(--suave)}dl.ficha dd{margin:0}
.par{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.col{background:var(--papel);border:1px solid var(--borde);border-radius:10px;padding:12px 14px;min-width:0}
.col h4{margin:0 0 8px;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--suave)}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--codigo);border-radius:8px;padding:10px 12px;
margin:0;font:12.5px/1.5 ui-monospace,Consolas,monospace;max-height:640px;overflow:auto}
.texto{white-space:pre-wrap;overflow-wrap:anywhere}
.vacio{color:var(--suave);font-style:italic}
@media (max-width:820px){.par{grid-template-columns:1fr}dl.ficha{grid-template-columns:1fr}}
"""


def md(t):
    """Negritas **x** de las fichas, y nada mas."""
    partes = html.escape(t).split("**")
    return "".join(f"<strong>{p}</strong>" if i % 2 else p for i, p in enumerate(partes))


def main():
    d = json.load(open(CORRIDA, encoding="utf-8"))
    por_seccion = {}
    for c in d["detalle"]:
        # De las transacciones, la primera: el mismo texto de prompt para las demas.
        por_seccion.setdefault(c["seccion"].replace("txreport_", "txreport_"), c)
    tokens = {}
    for c, t in zip(d["detalle"], d["tokens"]):
        tokens.setdefault(c["seccion"], t)

    cuerpo, indice = [], []
    indice.append('<a href="#sistema">0. El mensaje común (sistema)</a>')
    cuerpo.append(
        '<h2 id="sistema">0. El mensaje común que reciben casi todos (el «sistema»)</h2>'
        '<p class="nota">Va delante de cada prompt de análisis salvo el de cada captura. '
        'Es la presentación del analista y las 15 reglas de estilo. Las conclusiones, las recomendaciones, '
        'la comparativa y el integrado reciben una variante con el permiso de dictaminar (abajo).</p>'
        f"<div class='par'><div class='col'><h4>Sistema normal · {len(G.SYSTEM_PROMPT):,} caracteres</h4>".replace(",", ".")
        + f"<pre>{html.escape(G.SYSTEM_PROMPT)}</pre></div>"
        f"<div class='col'><h4>Lo que añade la variante con permiso de dictamen (entre la regla 15 y el ejemplo de tono)</h4>"
        f"<pre>{html.escape(PERMISO_VEREDICTO)}</pre></div></div>")
    for n, (clave, titulo, fuente, f) in enumerate(FICHAS, 1):
        ancla = f"p{n}"
        indice.append(f'<a href="#{ancla}">{n}. {html.escape(titulo)}</a>')
        if fuente[0] == "run":
            c = por_seccion.get(fuente[1])
            t = tokens.get(fuente[1]) or {}
            prompt_txt = c["prompt"] if c else ""
            salida = c["respuesta"] if c else None
            tam = (f"{t.get('prompt_tokens', 0):,} tokens de entrada con el sistema incluido; "
                   f"{len(prompt_txt):,} caracteres sin él. Salida {t.get('completion_tokens', 0):,} tokens, "
                   f"{t.get('reasoning_tokens', 0):,} de razonamiento.").replace(",", ".")
            izq = "Prompt tal como se envió (Nova, «después» de R2" + (", primera transacción" if fuente[2] else "") + ")"
            der = "Lo que escribió la IA"
        else:
            _, ruta, a, b = fuente
            prompt_txt = leer(ruta, a, b)
            salida = None
            tam = "No se corrió en R2: la plantilla sola. Las llaves {…} se rellenan con los datos."
            izq = f"Plantilla, tal como está en el código ({ruta.replace('/app/app/', '')}:{a}-{b})"
            der = "Lo que escribió la IA"
        filas = [("Qué produce", f["produce"]), ("Dónde vive", f["donde"]), ("Qué datos recibe", f["datos"]),
                 ("Reglas propias", f["reglas"]), ("Parámetros", f.get("params", GENERAL_PARAMS)),
                 ("Tamaño", tam), ("¿Sabe dónde están las rampas?", f["rampa"]),
                 ("¿Dónde se concentran los fallos?", f["fallos"]), ("Caché: qué podría ir delante", f["cache"])]
        if f.get("extra"):
            filas.append(("Ojo", f["extra"]))
        ficha = "".join(f"<dt>{html.escape(k)}</dt><dd>{md(v)}</dd>" for k, v in filas)
        der_html = (f"<div class='texto'>{html.escape(salida)}</div>" if salida
                    else "<span class='vacio'>No se generó en la corrida de R2.</span>")
        cuerpo.append(f"<h2 id='{ancla}'>{n}. {html.escape(titulo)}</h2><dl class='ficha'>{ficha}</dl>"
                      f"<div class='par'><div class='col'><h4>{html.escape(izq)}</h4><pre>{html.escape(prompt_txt)}</pre></div>"
                      f"<div class='col'><h4>{der}</h4>{der_html}</div></div>")

    doc = ("<!doctype html><html lang='es'><head><meta charset='utf-8'>"
           "<meta name='viewport' content='width=device-width,initial-scale=1'><title>Inventario de prompts</title>"
           f"<style>{CSS}</style></head><body><main>"
           "<h1>Inventario de los prompts de análisis</h1>"
           "<p class='nota'>Un <em>prompt</em> es lo que Kinetix le escribe a la IA para que redacte una sección del informe. "
           "Aquí está cada uno: a la izquierda lo que se le manda, a la derecha lo que escribió en la corrida de R2 de "
           "«Nova capa media» (el código actual). Encima de cada par, una ficha: qué produce, qué datos recibe, qué reglas lleva, "
           "si sabe dónde están las rampas de la prueba y qué parte podría ir delante para gastar menos. "
           "<strong>Lleva datos de clientes: no sale de esta carpeta.</strong></p>"
           f"<nav>{''.join(indice)}</nav>{''.join(cuerpo)}</main></body></html>")
    open(SALIDA, "w", encoding="utf-8").write(doc)
    print(f"{SALIDA}: {len(FICHAS)} prompts, {len(doc):,} caracteres")


if __name__ == "__main__":
    main()
