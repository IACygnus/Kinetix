"""Las filas del panel «Transacciones del JTL» y su marca «crítica».

BLOQUE 5 (reporte 147): extraído TAL CUAL de `/extract-jtl-transactions`
(N3.2, ETAPA 5) para que la ficha del «Analista IA» marque las críticas con la
misma regla que la pantalla Nuevo Reporte. Una sola definición.

La criticidad es determinista, sin IA (D3), y se dispara con tres señales:
  (a) el veredicto por transacción de KNX-09 (p90 vs tiempo, tasa de error vs
      disponibilidad). Requiere criterios; sin ellos se omite.
  (b) pico relativo: max >= 10x el promedio.
  (c) pico absoluto: max >= 10000 ms.
Cualquiera de las tres marca.

Con criterios del analista (`criterios.declarados`) el umbral de cada
transacción sale de `criterios_efectivos` y lo que no se declaró no se nombra.
Sin esa marca, el texto es byte a byte el de antes.
"""
from typing import Any, Dict, List, Optional

from app.services.ai.criterios import criterios_efectivos, declarados
from app.services.ai.estilo import ms, num, pct, veces


def filas_del_panel(summary_df, criteria: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Una fila por transacción, ordenadas: primero las críticas, y por pico."""
    from app.services.ai.gemini import compute_per_transaction_verdicts
    verdicts = compute_per_transaction_verdicts(summary_df, criteria).get(
        'verdicts_per_transaction', {}) if criteria else {}
    analista = declarados(criteria)

    transactions = []
    for _, row in summary_df.iterrows():
        label = str(row['label'])
        avg, mx = float(row['promedio']), float(row['max'])
        # ETAPA 5 (D45): el motivo se redacta como el resto del informe —
        # sin jerga, con tildes y en formato espanol.
        motivos = []
        veredicto = verdicts.get(label)
        if veredicto in ("NO APTO", "APTO CON RESERVAS"):
            p90 = float(row['p90'])
            if analista:
                umbral_rt, disp, _ = criterios_efectivos(criteria, label)
                umbral_err = None if disp is None else 100.0 - disp
            else:
                umbral_rt = float((criteria or {}).get('response_time', 2000))
                umbral_err = 100.0 - float((criteria or {}).get('availability', 99.0))
            partes = []
            if umbral_rt is not None and p90 > umbral_rt * 0.8:
                partes.append(f"1 de cada 10 usuarios espera más de {ms(p90)} "
                              f"(el límite son {ms(umbral_rt)})")
            if umbral_err is not None and float(row['tasa_error']) > umbral_err:
                partes.append(f"{pct(row['tasa_error'])} de errores "
                              f"(el límite es {pct(umbral_err)})")
            encabezado = "no cumple: " if veredicto == "NO APTO" else "queda al límite: "
            motivos.append(encabezado + " · ".join(partes))
        if avg > 0 and mx >= 10 * avg:
            motivos.append(f"pico de {ms(mx)}, {veces(mx / avg)} su promedio")
        if mx >= 10000:
            motivos.append(f"pico de {num(mx / 1000, 1)} segundos, "
                           f"que apunta a una espera agotada")

        transactions.append({
            'label': label,
            'muestras': int(row['muestras']),
            'promedio': round(avg, 2),
            'p90': round(float(row['p90']), 2),
            'p95': round(float(row['p95']), 2),
            'max': round(mx, 2),
            # ETAPA 5 (D39): TPS = muestras / duracion de toda la prueba. Ya
            # venia calculado como `rendimiento` en get_summary_table_data;
            # aqui solo se devuelve, para que el panel no lo recalcule mal.
            'tps': round(float(row['rendimiento']), 2),
            'errores': int(row['errores']),
            'tasa_error': round(float(row['tasa_error']), 4),
            'verdict': veredicto,
            'is_critical_suggested': bool(motivos),
            'motivo': " · ".join(motivos),
        })

    transactions.sort(key=lambda t: (not t['is_critical_suggested'], -t['max']))
    return transactions
