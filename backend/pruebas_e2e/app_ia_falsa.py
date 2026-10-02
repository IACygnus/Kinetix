"""La app de Kinetix con la IA del CHAT del «Analista IA» sustituida por un guion.

    docker exec jmeter_backend sh /app/pruebas_e2e/reiniciar_8002.sh --ia-falsa

Solo para el 8002 (base de PRUEBAS). Cada llamada del chat toma la primera
entrada de /tmp/b5_ia_guion.json y la quita:
  - un objeto o un texto  -> es lo que «responde» la IA;
  - null                  -> la IA falla (como si se cayera).
**Sin guion, o con el guion vacío, se comporta igual que el 8002 sin IA**: por
eso las demás suites (cierre_r1.sh, cierre_b5.sh) corren igual contra él.
El informe (generar) no pasa por aquí: sin clave, sale con el respaldo.
"""
import json
import sys

sys.path.insert(0, "/app")
from app.main import app   # noqa: E402,F401
from app.api.v1.endpoints import analista as EP   # noqa: E402

GUION = "/tmp/b5_ia_guion.json"


async def _llamador(db):
    async def falsa(prompt, sistema, sanear):
        try:
            lista = json.load(open(GUION, encoding="utf-8"))
        except Exception:
            lista = []
        if not lista:
            return None, "la IA no está configurada"
        x = lista.pop(0)
        json.dump(lista, open(GUION, "w", encoding="utf-8"), ensure_ascii=False)
        if x is None:
            return None, "la IA no respondió (guion de prueba)"
        return (x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)), ""
    return falsa


EP.llamador = _llamador
