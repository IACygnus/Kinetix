8d2c545 · 2026-09-16

# ETAPA 2.11 — Verificación de punta a punta

**Llamadas reales a la IA en este sub-paso: 0.** Presupuesto de etapa: **1 / 50**.

Un solo comando vuelve a verificar la etapa entera sobre las **cuatro salidas**. Sirve de
cierre y de regresión para etapas futuras:

```bash
docker exec -e KX_PWD=<clave> jmeter_backend python3 /tmp/e2e/verificar_etapa2.py
```

Encadena ocho pasos y devuelve código de error si alguno falla.

---

## Resultado — **las cuatro salidas pasan**

| # | Paso | Qué comprueba | Resultado |
|---|---|---|---|
| 1 | **Pantalla** — carga | `captura_informe.py`: la página trae **26 gráficas** (11 generales + 5 × 3 transacciones) | PASA |
| 2 | **Pantalla** — cableado C2 | 9 comprobaciones: editar dentro del bloque escribe en `transaction_chart_analyses/chart_latency` de esa transacción y **no** toca `ai_analysis_latency`; en el general, al revés; los dos textos quedan como estaban | PASA |
| 3 | **PDF individual** | 8 comprobaciones sobre el HTML real que se renderiza: sin Throughput, el KPI sigue, sin la palabra prohibida, transacciones antes de conclusiones, 3 bloques, sin conclusiones ni recomendaciones por transacción, cada bloque abre página (D24). **16 páginas** | PASA |
| 4-5 | **HTML individual** | 11 comprobaciones: además de lo anterior, que el `div` de throughput no exista, que haya 15 gráficas por transacción, que lleven controles y que los títulos sean los del general | PASA |
| 6 | **HTML individual** — se abre | Chromium sobre el archivo descargado: **22 divs de gráfica, 22 pintadas por Plotly, cero errores de consola** | PASA |
| 7 | **Integrado** | `export-html` 200 (1.508.480 bytes, 1,7 s) y `export-pdf` 200 (1.518.807 bytes, 5,0 s), con las mismas comprobaciones de contenido | PASA |
| 8 | **Integrado** — recorte | El riesgo de la regla 18: los **3 bloques por transacción sobreviven** al recorte de las conclusiones individuales, y no queda ninguna conclusión individual | PASA |

Más de cuarenta comprobaciones en total, todas sobre **datos reales** (`ff186cc7` y el
informe integrado `fa724249`), ninguna sobre datos de juguete.

---

## Lo que esta verificación **no** cubre

- **El aspecto.** Comprueba estructura, orden y contenido, no si el informe se ve bien. La
  validación visual de Fredy sigue siendo el único criterio de éxito (regla 9).
- **La generación con IA.** Todo se verifica con los textos ya guardados; no se genera
  ninguno nuevo. La corrida de confirmación de tiempos sigue pendiente de autorización
  (reporte 23 §3).
- **El selector de exportación** de v1.2 §6 y el **panel de selección** de v1.2 §2, que no
  son de esta etapa.
- **La tabla resumen filtrada** dentro de cada bloque por transacción en pantalla: en el PDF
  y en el HTML sí está; en pantalla falta (reporte 20 §5).

---

## Cómo dejar el entorno listo

Los scripts viven en `C:\proyectos\Kinetix_pruebas\e2e\` y corren **dentro** de
`jmeter_backend`, que es donde hay python y Chromium:

```bash
docker cp C:/proyectos/Kinetix_pruebas/e2e jmeter_backend:/tmp/e2e
docker exec -d jmeter_backend python3 /tmp/e2e/rele_5173.py
docker exec jmeter_backend python3 -c "import socket;print(socket.socket().connect_ex(('127.0.0.1',5173)))"
```

Recordatorio caro de aprender: en la sesión guardada de Playwright, **`csrf_token` no puede
ser `httpOnly`** — si lo es, la cabecera `X-CSRF-Token` viaja vacía, toda mutación responde
403 y el navegador lo reporta como error de CORS.
