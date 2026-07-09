# Auditoría Forense — Remotes Post-HF20

Fecha: 2026-07-09

## Contexto
Detectado durante conversación posterior al push del commit `58aab74` (HF20).
Fredy señaló que los push del HF20 nunca debieron ir a Azure DevOps. La política
interna es:
- **Azure DevOps (`origin`)** = REPO DE PRODUCCIÓN ESTABLE, solo releases
  autorizadas por Fredy.
- **GitHub (`github`, `IACygnus/Kinetix`)** = repositorio de trabajo activo.

Los prompts previos (backup pre-Sprint 3.0 y consolidación HF20) incluyeron
`git push origin` por asunción incorrecta de "hacer backup a ambos remotes". Esta
auditoría verifica el impacto real en Azure y confirma que producción (`main`) no
fue afectada.

> Auditoría **read-only**: solo se usaron `git remote/log/branch/ls-remote` y un
> `git fetch` (que únicamente actualiza refs de tracking). No se modificó ningún
> archivo, branch local, ni se hizo push/pull/merge.

## Configuración de remotes verificada

```
github  https://github.com/IACygnus/Kinetix.git                         (fetch/push)
origin  https://PlataformasSQA@dev.azure.com/PlataformasSQA/COE/_git/COE (fetch/push)
```
No hay otros remotes configurados.

## Estado de Azure DevOps (origin) pre-limpieza

### Azure/main — INTACTA
- Último commit: `2cfe0ea "feat: v3.1.0 - high cardinality chart optimization"`
  del **2026-04-21**.
- NO recibió ningún commit de desarrollo (HF16, HF17, HF18a, HF18b, HF20).
- Producción a salvo. Coincide con lo que Fredy recordaba ("última = 21 abril").

### Azure/backup-trabajo-local — CREADA POR ERROR
Branch lateral que recibió, a lo largo de sesiones previas, los push de trabajo
de desarrollo. Contenía **6 commits por delante de main** (merge-base = `2cfe0ea`,
el propio tip de main):

| Commit | Fecha | Descripción |
|---|---|---|
| `58aab74` | 2026-07-09 | HF20 — parser listener anidado + persistencia |
| `b45dfd5` | 2026-07-08 | Snapshot pre-Sprint 3.0 (HAR-first) |
| `a526897` | 2026-06-16 | Sprint 2.7 + HF14 cierre |
| `b20c6e3` | 2026-06-03 | Backup Sprint 2.5 + 2.5.1 + 2.6 |
| `2740786` | 2026-05-28 | wip: AI Designer + Editor + parser (pre-revert main) |
| `9531eb3` | 2026-05-22 | AI Script Designer + ChatGPT + PDF + XML parser |

> Nota: HF16/17/18a/18b **no son commits sueltos** — están empaquetados dentro de
> los snapshots `b45dfd5` y `a526897`. Todo ese trabajo llegó a Azure como parte
> de esta branch lateral, nunca a `main`.

Tags de desarrollo también filtrados a Azure:
- `pre-sprint-3.0-20260708_190944` → b45dfd5
- `pre-sprint-3.0-post-hf20-20260709_115832` → 58aab74

## Estado de GitHub (github) — respaldo completo

`github/backup-trabajo-local` con los 6 commits verificados
(9531eb3 → 2740786 → b20c6e3 → a526897 → b45dfd5 → 58aab74).

Los 2 tags `pre-sprint-3.0-*` verificados en GitHub, apuntando a los **mismos
hashes** que Azure (513dc86→b45dfd5, de4dcd8→58aab74) — respaldo idéntico y
completo.

## Análisis de riesgo

**Nivel: Bajo.**
- Azure/main NO tocada → producción sin impacto.
- Azure/backup-trabajo-local es branch aislada → no dispara pipelines de deploy.
- Ningún merge request creado desde esa branch hacia main.
- El personal de SQA que ve Azure Repos podría confundirse al ver una branch con
  actividad reciente, pero no hay riesgo funcional.

## Decisión

Fredy autorizó (opción 1 de auditoría):
1. Borrar Azure/backup-trabajo-local.
2. Borrar los 2 tags de Azure.
3. Mantener GitHub intacto (todo el trabajo permanece ahí).
4. Establecer regla permanente: solo push a `github` para desarrollo.

## Ejecución

Ver: `docs/reports/repo/housekeeping-post-hf20-2026-07-09.md` (commit `8a732f5`).
Resultado: Azure quedó con solo `refs/heads/main` + tags de release
(`v1.3.0`, `v3.0.0`, `v3.1.0`); GitHub intacto.

## Regla establecida
Para futuros commits de desarrollo (HFs, sprints, docs):
- Solo `git push github <branch>`.
- NUNCA `git push origin <cualquier-cosa>`.
- Evitar `git push --all` y `git push` sin remote explícito (pueden alcanzar origin).
- Azure DevOps se actualiza solo cuando Fredy autoriza explícitamente promover una
  release estable.
