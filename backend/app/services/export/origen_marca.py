"""
F1 (aviso de respaldo) — la marca invisible de los exportados INDIVIDUALES.

`export_pdf.py` y `export_html.py` estan protegidos: toda la logica vive aqui y
alli solo entra una llamada. Mete en el <head> las <meta> de
`origen.metas_para` (cuantas secciones no las escribio la IA, cuando y por
que). WeasyPrint pasa `description` y `keywords` a los metadatos del PDF; en el
HTML quedan en la cabecera. Nada se pinta en la pagina.

Nunca lanza: una marca que falla no puede costar una exportacion.
"""
import logging
import re

logger = logging.getLogger(__name__)

_HEAD = re.compile(r"<head[^>]*>", re.I)


async def con_marca(db, execution, html: str) -> str:
    try:
        from app.services.ai.origen import metas_para
        metas = await metas_para(db, [execution.id])
        if not metas:
            return html
        m = _HEAD.search(html)
        if not m:
            return html
        return html[:m.end()] + "\n" + metas + html[m.end():]
    except Exception as e:
        logger.warning(f"F1: sin marca de origen en el exportado de {getattr(execution, 'id', '?')}: {e}")
        return html
