"""Qué incluye un informe exportado — alcance y capas (ETAPA 6, D49-D51).

Dos parametros opcionales que los dos exportadores individuales (PDF y HTML)
interpretan EXACTAMENTE igual. Vive aparte de `export_pdf.py` y `export_html.py`
—los dos protegidos— para que el cambio en ellos se quede en unas pocas lineas y
para que las dos salidas no puedan divergir en lo que significa cada parametro.

    ?tx=<label>&tx=<label>      que transacciones entran (v1.2 §6, D50/D51)
    ?capa=<idGrafica>:<valor>   con que capas se dibuja cada grafica (§3, D49)

Compatibilidad (D51): **sin ninguno de los dos, la salida es la de siempre** —
todas las transacciones y las dos capas. Es la diferencia entre "el parametro no
vino" (None) y "vino vacio" ([]), que es lo que distingue "todo" de "solo el
informe general".

El informe integrado no pasa por aqui: combina varias ejecuciones y v1.2 §6 lo
deja fuera del selector por ahora.
"""
from typing import Dict, List, Optional

from fastapi import HTTPException

# Valores admitidos del control de capas. 'ambas' es el de siempre.
CAPAS_VALIDAS = ('ambas', 'promedio', 'maximo')
CAPA_POR_DEFECTO = 'ambas'


def seleccion_de_query(tx: Optional[List[str]]) -> Optional[List[str]]:
    """El parametro `tx` tal como lo manda el navegador -> seleccion.

    - `None` (el parametro no viene)  -> `None`: TODAS las transacciones, que es
      el comportamiento de siempre y lo que reciben los clientes antiguos.
    - `['']` o `[]` (viene vacio)     -> `[]`: SOLO el informe general.
    - `['Auth', 'Login']`             -> esas dos.

    Un `?tx=` vacio es la forma de pedir "solo el general" sin inventar un
    segundo parametro booleano que pudiera contradecir a la lista.
    """
    if not isinstance(tx, (list, tuple)):
        # `None`, y tambien el objeto `Query(None)` que llega cuando alguien
        # invoca el endpoint en proceso (las pruebas lo hacen) sin pasar el
        # parametro: FastAPI solo lo resuelve cuando la llamada viene por HTTP.
        return None
    return [t for t in tx if t and t.strip()]


def filtrar_transacciones(etiquetas: List[str],
                          seleccion: Optional[List[str]]) -> List[str]:
    """Aplica la seleccion al orden ya calculado de transacciones con analisis.

    `etiquetas` llega ordenada como la tabla resumen y ese orden se respeta: la
    seleccion dice QUE entra, no en que orden.

    Una etiqueta que no exista en la ejecucion es un **400**, no un silencio
    (D51). Exportar un PDF sin el bloque que se pidio, y sin decirlo, seria peor
    que fallar: quien lo abre no tiene forma de notar lo que falta.
    """
    if seleccion is None:
        return etiquetas
    conocidas = set(etiquetas)
    desconocidas = [t for t in seleccion if t not in conocidas]
    if desconocidas:
        raise HTTPException(
            status_code=400,
            detail=("Transaccion sin analisis en esta ejecucion: "
                    + ", ".join(sorted(desconocidas))),
        )
    pedidas = set(seleccion)
    return [e for e in etiquetas if e in pedidas]


def capas_de_query(capa: Optional[List[str]]) -> Dict[str, str]:
    """`?capa=general|rt:maximo` -> `{'general|rt': 'maximo'}`.

    Lo que no se entienda se ignora en silencio y esa grafica se dibuja con las
    dos capas: un parametro mal formado no puede tumbar una exportacion que, por
    lo demas, se puede entregar entera. Un valor fuera de `CAPAS_VALIDAS` cae en
    el mismo caso.
    """
    mapa: Dict[str, str] = {}
    if not isinstance(capa, (list, tuple)):
        return mapa          # mismo motivo que en `seleccion_de_query`
    for item in capa:
        if not item or ':' not in item:
            continue
        ident, _, valor = item.rpartition(':')
        ident, valor = ident.strip(), valor.strip().lower()
        if ident and valor in CAPAS_VALIDAS:
            mapa[ident] = valor
    return mapa


def id_grafica(alcance: str, grafica: str) -> str:
    """El mismo identificador que arma el frontend (`useChartLayers.idGrafica`).

    `alcance` es 'general' o 'tx:<nombre de la transaccion>'. Tenerlo en una
    funcion evita que los dos exportadores compongan la cadena a mano y se
    separen del frontend por un caracter.
    """
    return f"{alcance}|{grafica}"


def capa_de(capas: Dict[str, str], alcance: str, grafica: str = 'rt') -> str:
    return capas.get(id_grafica(alcance, grafica), CAPA_POR_DEFECTO)
