0c49419 · 2026-09-15

# ADENDA A — Liberación del flag de prueba del circuit breaker

**Llamadas reales a la IA en este sub-paso: 0.**
Archivo: `services/ai/gemini.py`. **Defecto introducido por mí en 1.5 y no cubierto por sus
12 escenarios.**

---

## 1. Verificación por lectura: tres caminos no liberaban el flag

`_circuito_bloquea()` pone `_probe_in_flight = True` cuando deja pasar la llamada de prueba.
Rastreados los seis desenlaces posibles:

| Camino de la prueba | ¿Libera `_probe_in_flight`? | Por qué |
|---|---|---|
| Éxito | ✅ | pasa por `_cerrar_circuito()` |
| `quota_exhausted` | ✅ | pasa por `_abrir_circuito()` |
| `rate_limit` (agota los 3 intentos) | ✅ | pasa por `_abrir_circuito()` |
| **Respuesta vacía (`finish_reason=length`)** | ❌ | `return None` directo |
| **Error no-rate-limit** | ❌ | `return None` directo |
| **Provider no soportado** | ❌ | `return None` directo |

La excepción inesperada cae en el camino de error, así que también fugaba.

### La consecuencia es peor que la fuga

`_circuito_bloquea()` corta en seco mientras el flag esté puesto:

```python
if cls._probe_in_flight:       # ya hay otra prueba en curso
    return True
```

Con el flag colgado, **ninguna llamada posterior vuelve a pasar jamás**: ni al cumplirse el
enfriamiento, ni con el proveedor ya recuperado. El circuito queda abierto de forma permanente y
sólo se sale guardando la config o reiniciando el proceso.

Es el mismo defecto que 1.5 vino a corregir, reintroducido en una capa más abajo: allí el
circuito no se cerraba nunca; aquí es **el propio mecanismo de recuperación** el que se bloquea a
sí mismo. Los 12 escenarios de 1.5 no lo detectaron porque sólo probaban pruebas que terminaban
en éxito o en rate-limit, que son justo los dos caminos que sí liberaban.

### Evidencia del defecto, medida antes de tocar nada

Los escenarios nuevos se ejecutaron **contra el código de 1.5**:

```
FALLA | prueba tras 60 s / error no-rate-limit   | probe_in_flight=True abierto=True
FALLA |     ... y tras otros 60 s una prueba OK  | r=None abierto=True
FALLA | prueba tras 60 s / respuesta vacia       | probe_in_flight=True abierto=True
FALLA |     ... y tras otros 60 s una prueba OK  | r=None abierto=True
FALLA | prueba tras 60 s / excepcion inesperada  | probe_in_flight=True abierto=True
FALLA |     ... y tras otros 60 s una prueba OK  | r=None abierto=True
PASA  | regresion: prueba OK cierra
PASA  | regresion: prueba con rate-limit reabre y libera
=== 2/8 escenarios PASAN ===
```

El renglón que lo demuestra es el encadenado: **`r=None` con el proveedor sano y el enfriamiento
cumplido dos veces**. No hay recuperación posible.

---

## 2. Implementación

**Regla aplicada:** la prueba que no termina en éxito **reabre** el circuito con marca nueva
(otro enfriamiento de 60 s); **sólo el éxito lo cierra**.

`_circuito_bloquea()` pasa a devolver `(bloquea, es_prueba)`, porque quien recibe la prueba es
quien tiene que soltarla:

```python
def _circuito_bloquea(cls) -> Tuple[bool, bool]:
    ...
    cls._probe_in_flight = True    # esta llamada es la prueba
    return False, True
```

Y el desenlace se cierra siempre, en un `finally`:

```python
@classmethod
def _fin_de_prueba(cls, motivo: str) -> None:
    with cls._lock:
        ya_cerrado = not cls._circuit_open      # el exito lo cerro por su cuenta
        cls._probe_in_flight = False
    if not ya_cerrado:
        cls._abrir_circuito(motivo)             # marca nueva -> otros 60 s
```

```python
        try:
            for attempt in range(max_retries):
                ...
        finally:
            # ADENDA A: la prueba suelta el flag pase lo que pase.
            if es_prueba:
                GeminiAnalyzer._fin_de_prueba(
                    f"la llamada de prueba de {section_name} no tuvo exito")
```

`_abrir_circuito` se invoca **fuera** del `with cls._lock`, porque toma el lock por su cuenta.

### Sobre el tamaño del diff

`git diff --stat` marca **112 inserciones / 84 eliminaciones**, pero **84 de esas líneas son sólo
reindentación** por meter el bucle dentro del `try`.

`git diff -w` (ignorando espacios) muestra el cambio real: la firma de `_circuito_bloquea`, sus
4 `return`, el método `_fin_de_prueba` nuevo, el desempaquetado en el sitio de llamada y el
bloque `try/finally`. Nada más.

---

## 3. Validación — 0 llamadas reales

Con stubs y reloj simulado (`time.sleep` sustituido por un acumulador):

| Escenario | Resultado |
|---|---|
| Prueba tras 60 s falla con error no-rate-limit | **PASA** — flag liberado, circuito reabierto con marca nueva |
| … y tras otros 60 s, prueba OK | **PASA** — devuelve texto y cierra |
| Prueba tras 60 s devuelve vacío por `length` | **PASA** — flag liberado, circuito reabierto |
| … y tras otros 60 s, prueba OK | **PASA** — devuelve texto y cierra |
| Prueba tras 60 s lanza excepción inesperada | **PASA** — flag liberado, circuito reabierto |
| … y tras otros 60 s, prueba OK | **PASA** — devuelve texto y cierra |
| Regresión: prueba OK cierra | **PASA** — sin cambios respecto a 1.5 |
| Regresión: prueba con rate-limit reabre y libera | **PASA** |

**8/8** (eran 2/8 antes del fix).

**Regresión de 1.5: los 12 escenarios de HF-2 siguen pasando 12/12.** `py_compile` OK.

---

## 4. Nota de método

El fix de 1.5 se dio por bueno con 12 escenarios que cubrían los caminos que yo tenía en mente,
no todos los que existían. La lección para el resto de etapas: cuando un cambio introduce un
flag de exclusión, hay que enumerar **todas** las salidas de la región que lo sostiene antes de
declararlo validado — y la forma barata de hacerlo es la que se usó aquí, escribir primero los
escenarios y ejecutarlos **contra el código sin arreglar** para ver si realmente fallan.

---

## Estado

ADENDA A completada. Se continúa con 1.7 (análisis de la línea base, 0 llamadas).
