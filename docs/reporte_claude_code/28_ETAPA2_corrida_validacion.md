e43cd71 · 2026-09-16

# ETAPA 2 — Corrida real de validación (`E2-validacion`)

**Llamadas reales a la IA en este sub-paso: 29** (28 del informe + 1 del consolidado del
integrado). **Presupuesto de etapa: 30 / 50.**

Corrida autorizada por Fredy. Misma herramienta, mismo JTL y mismos parámetros que la línea
base de la Etapa 1, para que los números se puedan comparar uno a uno:

| | |
|---|---|
| Ejecución | **`59e25069-5104-4b23-9b79-d305f5b38abd`** — `E2-validacion` |
| JTL | `20251222_201217_resultados_general_carga_22-dic-2025-150249.jtl` (10.075 muestras) |
| Cliente / criterios | `iaperformance` · concurrencia 30, tiempo 2.000 ms, disponibilidad 99,5 % |
| Transacciones críticas | `4. Get_Booking_Id`, `5. Put_Update_Booking`, `6. Delete_Booking_Id` |
| Configuración de IA | `openai` · **`gpt-5.5`** · **`reasoning_effort=low`** |

---

## 1. Controles exigidos — todos pasan

| Control | Resultado |
|---|---|
| 28 llamadas (10 generales + 6 × 3 transacciones) | **28** |
| Todas con `outcome="ok"` | **28 / 28** |
| Todas con `reasoning_effort="low"` | **28 / 28** |
| Ninguna de throughput | **ninguna** |
| Ninguna de conclusiones / recomendaciones por transacción | **ninguna** |

No se activó la PARADA: no hubo ningún otro `outcome`.

---

## 2. Tiempos, frente a la línea base

| | Corrida 1 | Corrida 2 | **E2-validacion** | |
|---|---|---|---|---|
| Llamadas de IA | 35 | 35 | **28** | −20 % |
| **T1 − T0** (bloque general) | 119,1 s | 112,1 s | **55,9 s** | **−50 %** |
| **T2 − T0** (percibido total) | 354,3 s | 357,4 s | **141,0 s** | **−61 %** |
| Latencia total de IA | 351,6 s | 357,0 s | **137,9 s** | −61 % |
| Latencia media por llamada | 10,0 s | 10,2 s | **4,9 s** | −52 % |

**De casi 6 minutos a 2 minutos y 21 segundos.**

El recorte viene de dos sitios que se multiplican:

- **menos llamadas** (35 → 28): lo que hizo esta etapa con D19 y D20;
- **cada llamada tarda la mitad** (10,2 → 4,9 s): eso lo hizo `reasoning_effort=low`, de 2.2.

Reparto actual: **55,7 s** en las 10 llamadas del informe general y **82,2 s** en las 18 de
las tres transacciones.

> Por eso la proyección del reporte 23 (−20 %) **no valía como dato**: restaba llamadas de un
> total medido con el `reasoning_effort` por defecto. La mejora real es tres veces mayor.

---

## 3. Tokens — dónde se fue el ahorro

| | Corrida 2 | **E2-validacion** |
|---|---|---|
| Tokens de salida | 28.461 | **9.498** |
| De ellos, razonamiento | 19.924 (**70,0 %**) | **3.175 (33,4 %)** |
| Razonamiento **por llamada** | 569 | **113** |
| Texto visible **por llamada** | 244 | **226** |
| Caché de prompt | 64.256 / 115.751 (55,5 %) | 7.168 / 92.379 (7,8 %) |

Tres lecturas:

1. **El razonamiento cae un 80 % por llamada** (569 → 113 tokens). Es el efecto directo de
   `low`, y explica la mitad del ahorro de tiempo. La H1 de la Etapa 1 —«el 70 % de lo que
   genera el modelo es razonamiento»— **deja de cumplirse**: ahora es el 33 %.
2. **El texto visible apenas se acorta: 244 → 226 tokens por llamada (−7 %).** Es el número
   que hay que vigilar: dice que el informe no se ha quedado corto, pero no dice si se ha
   quedado más pobre. **Eso solo lo puede juzgar Fredy leyéndolo** (guion de prueba, paso 3).
3. **La caché vuelve al 7,8 %**, que es el valor realista que ya anticipaba el reporte 10: el
   55,5 % de la corrida 2 era el premio de repetir prompts idénticos minutos después. Sigue
   pendiente el `SYSTEM_PROMPT` duplicado, material de la Etapa 4.

---

## 4. La sonda `/auth/me` durante la generación

| | Corrida 1 | Corrida 2 | **E2-validacion** |
|---|---|---|---|
| Latidos | 122 | 181 | **73** |
| Errores | 1 | 0 | **0** |
| Peor latido | **54.922 ms** | 21,0 ms | **10,7 ms** |
| p95 | 7,9 ms | 4,9 ms | **6,6 ms** |

Durante los 141 segundos de generación, **el proceso respondió siempre por debajo de 11 ms**.
El pico de 55 segundos de la corrida 1 era el event loop bloqueado que se corrigió en 1.4.

---

## 5. Informe integrado de la validación

`E2-validacion` + `E1.3-baseline-2`, informe **`998090d0-9bab-4935-8a2e-ffd7f23000fb`**:

- Consolidado con IA: **1 llamada** (las dos ejecuciones son de tipo `load`, así que van en un
  solo grupo) — 16,2 s, conclusiones de 2.828 y recomendaciones de 3.025 caracteres.
- `export-pdf` **200**, 2.565.644 bytes, 9,5 s · `export-html` **200**, 987.203 bytes, 1,0 s.
- En el HTML: **6 bloques por transacción** (3 por ejecución) y **una sola** sección de
  conclusiones, la consolidada. Sin gráfica de throughput y sin la palabra prohibida.

---

## 6. `verificar_etapa2.py` sobre `E2-validacion`

Los **diez pasos pasan** sobre la ejecución nueva: 26 gráficas en pantalla, cableado C2 del
general y de las transacciones, las tres tablas resumen filtradas, PDF de 16 páginas con cada
transacción en página nueva, HTML con 22 gráficas pintadas por Plotly y cero errores de
consola, y el integrado con su recorte de conclusiones correcto.

El registro completo de la corrida (parámetros, tiempos, sonda y las 28 líneas de telemetría)
queda en `Kinetix_pruebas/e2_validacion.json`, junto a `baseline1.json` y `baseline2.json`.
