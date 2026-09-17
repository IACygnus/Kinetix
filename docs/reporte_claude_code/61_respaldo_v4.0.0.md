7f1ca61 · 2026-09-17

# Respaldo en git — etiqueta `v4.0.0`

**0 llamadas a la IA. No se tocó código de producto, ni ningún compose, ni el servidor.
`azure` no recibió nada.**

---

## 1. Qué quedó etiquetado

| | |
|---|---|
| Etiqueta | **`v4.0.0`**, anotada |
| Commit etiquetado | **`7f1ca61`** — *etapa7(7.5): cierre — reporte 60 para Fredy* |
| Objeto de la etiqueta | `56d71b0f5859394bf9f9f26944533200eff9a987` |
| Rama | `backup-trabajo-local` |
| En el remoto | `github` — verificado con `git ls-remote --tags` |

El mensaje de la etiqueta lleva el resumen de las ocho etapas (1, 2, 3, 5, 5b, 6, 7), con
cuáles están validadas por Fredy y cuáles pendientes, y apunta a la especificación v1.3 y a
los reportes `01…60`.

Estado de partida, verificado antes de tocar nada:

```
rama          : backup-trabajo-local
git status    : limpio
sin empujar   : nada  (git log github/backup-trabajo-local..HEAD vacío)
```

`git push github backup-trabajo-local` respondió **"Everything up-to-date"**: el contenido
ya estaba respaldado desde el cierre de la Etapa 7; lo que faltaba era la etiqueta.

## 2. Dos cosas del plan que NO se hicieron, y por qué

### 2.1 La especificación del módulo de horas

El paso 2 pedía guardar `docs/ESPECIFICACION-horas.md`. **No venía adjunta y el archivo no
existía.** No se inventó nada.

Consultado con Fredy, que eligió **etiquetar ya sobre `7f1ca61`** en vez de esperar. Encaja
con lo que la etiqueta describe: `7f1ca61` es exactamente el final del plan de corrección
del informe, que es de lo que habla su mensaje. La especificación de horas es lo siguiente
y se commiteará aparte, **fuera de `v4.0.0`**.

**Pendiente:** el commit `docs: especificacion funcional del modulo de horas v1.0`, cuando
Fredy pase el texto.

### 2.2 Alinear `main` — imposible por avance rápido

El paso 5 pedía `git merge --ff-only backup-trabajo-local`, y **parar sin forzar si no era
posible**. No lo es:

```
main                 76e58f4  Initial commit   ·  1 commit,  1 archivo (README.md)
backup-trabajo-local 7f1ca61  etapa7(7.5)      ·  206 commits, 472 archivos

git merge-base main backup-trabajo-local  ->  exit 1, sin salida
```

**Las dos ramas no tienen ancestro común.** Son dos historias independientes, cada una con
su propio `Initial commit` (`76e58f4` en `main`, `fc700e0` en `backup-trabajo-local`). Un
`--ff-only` no puede funcionar: no hay nada que adelantar.

Se paró y se reportó, como pedía el plan. Fredy eligió **dejar `main` como está**.

- `main` sigue en `76e58f4`, local y en el remoto. **Sin tocar.**
- Las alternativas —reapuntar `main` con `push --force`, o fusionar con
  `--allow-unrelated-histories`— quedaron descartadas por ahora. La primera descartaría el
  `Initial commit` de `main`; la segunda dejaría el historial con dos raíces para siempre.
- **No hay riesgo de pérdida:** el producto vive en `backup-trabajo-local`, está en
  `github`, y ahora además tiene una etiqueta anotada apuntándole.

## 3. `azure` no recibió nada

Verificado **sin salir a la red**, que es la mejor evidencia:

```
remote.azure.pushurl  =  NO-PUSH-USAR-COMANDO-EXPLICITO
refs/remotes/azure    =  (vacío)
```

El push de `azure` apunta a un placeholder a propósito, así que cualquier `git push azure`
falla en vez de subir algo por error. Y no hay ni una referencia local de `azure`: en esta
sesión no se habló con ese remoto. Los dos únicos comandos de red fueron
`git push github backup-trabajo-local` y `git push github v4.0.0`.

> Una consulta de red a `azure` (`git ls-remote`) se quedó colgada pidiendo credenciales y
> se cortó. No hacía falta: la comprobación local de arriba prueba lo mismo y no depende de
> que ese remoto conteste.

## 4. Cómo volver aquí

```bash
git fetch github --tags
git checkout v4.0.0          # el plan de correccion completo, tal cual quedo hoy
git switch backup-trabajo-local
```

---

## 5. Lo que queda abierto

1. **La especificación del módulo de horas** — pendiente de que Fredy la pase, para
   guardarla y commitearla (§2.1).
2. **`main`** — sigue en su `Initial commit`. Decisión aplazada, sin urgencia (§2.2).
3. **Validación de Fredy** de las Etapas 5b, 6 y 7 — guiones en los reportes 56, 52 y 60.
4. **Despliegue** — `59_handoff_despliegue_analisis.md`, con sus cinco preguntas abiertas.

---

**Estado: respaldo hecho. `v4.0.0` publicada en `github` sobre `7f1ca61`.**
