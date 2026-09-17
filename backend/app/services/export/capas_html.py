"""El control de capas del HTML exportado (ETAPA 6, D49).

Todo lo que el documento necesita para que quien lo reciba pueda apagar la capa
de promedios o la de maximos: el estilo de los botones, el JavaScript que alterna
las trazas, el markup del selector y la visibilidad inicial de cada traza.

Vive aqui —y no dentro de `export_html.py`, que es un archivo protegido— por dos
razones:

1. El informe individual y el integrado tienen plantillas distintas y los dos lo
   necesitan. Una sola definicion es lo que impide que acaben divergiendo, que es
   justo el problema que la ETAPA 2 vino a quitar.
2. Mantiene el cambio en los protegidos dentro de lo estimado en el reporte 46:
   son ~70 lineas de JS y CSS que no tienen por que engordar el endpoint.

Nota sobre el hover: con `hovermode:'x unified'`, Plotly deja fuera del hover
cualquier traza que no este visible. Por eso apagar una capa basta para que el
tooltip muestre solo la otra, sin tocar los `hovertemplate` (v1.2 §3).
"""
from app.services.export.report_generator import MAX_SERIES_SUFFIX

# Las tres opciones del selector, en el orden en que se pintan. Mismo vocabulario
# que `useChartLayers.ts` en el frontend.
CAPAS_HTML = (('ambas', 'Ambas'), ('promedio', 'Promedio'), ('maximo', 'Máximo'))

# Se inserta tal cual en las dos plantillas, sin llaves de formato.
JS_CAPAS = """
if (typeof window.kxCapa !== 'function') {
  window.kxEsMax = function(nombre) {
    return typeof nombre === 'string' && nombre.slice(-6) === ' (max)';
  };
  window.kxCapa = function(id, capa, boton) {
    var div = document.getElementById(id);
    if (!div || !div.data) return;
    // 'legendonly' en vez de false: la traza sigue en la leyenda de Plotly y se
    // puede recuperar a mano, pero NO entra en el hover unificado.
    var vis = div.data.map(function(t) {
      var esMax = window.kxEsMax(t.name);
      if (capa === 'promedio') return esMax ? 'legendonly' : true;
      if (capa === 'maximo') return esMax ? true : 'legendonly';
      return true;
    });
    Plotly.restyle(div, {'visible': vis});
    if (boton && boton.parentNode) {
      var hs = boton.parentNode.querySelectorAll('.capa-btn');
      for (var i = 0; i < hs.length; i++) hs[i].classList.remove('active');
      boton.classList.add('active');
    }
  };
}
"""

# Selector suelto (no anidado) a proposito: vale igual en el informe individual y
# en el integrado, que tienen hojas de estilo distintas y nombres de clase
# distintos para la barra de controles.
CSS_CAPAS = (
    ".capa-btn{background:#fff;border:1px solid #cbd5e1;color:#334155;"
    "border-radius:6px;padding:.3rem .7rem;font-size:.75rem;font-weight:700;"
    "cursor:pointer;transition:all .15s}"
    ".capa-btn:hover{border-color:#f5a623}"
    ".capa-btn.active{background:#f5a623;color:#0a1628;border-color:#f5a623}"
    ".capa-grupo{display:inline-flex;gap:.3rem}"
)


def ctrl_capas(chart_id: str, capa: str = 'ambas') -> str:
    """El selector segmentado de una grafica, con su capa ya marcada."""
    botones = ''.join(
        f'<button class="ctrl-btn capa-btn{" active" if capa == v else ""}" '
        f'data-capa="{v}" onclick="kxCapa(\'{chart_id}\',\'{v}\',this)">{t}</button>'
        for v, t in CAPAS_HTML
    )
    return (f'<span class="ctrl-sep">|</span><span class="ctrl-label">Capas:</span>'
            f'<span class="capa-grupo" data-chart="{chart_id}">{botones}</span>')


def aplicar_capa(traces, capa):
    """Deja visible solo la capa pedida.

    'ambas' no toca nada y el documento sale byte a byte como el de siempre. Las
    demas usan 'legendonly' —no `False`— para que la traza siga existiendo y el
    lector la pueda recuperar con los botones, y para que quede fuera del hover.
    """
    if capa == 'ambas':
        return traces
    for t in traces:
        es_max = str(t.get('name', '')).endswith(MAX_SERIES_SUFFIX)
        t['visible'] = True if es_max == (capa == 'maximo') else 'legendonly'
    return traces
