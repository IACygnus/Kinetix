# Housekeeping post-HF20 — Limpieza Azure + .gitignore

Fecha: 2026-07-09

## Contexto
La auditoría previa de remotes detectó que la branch `backup-trabajo-local` y sus
2 tags fueron pusheados accidentalmente a **Azure DevOps** (`origin`,
`PlataformasSQA/COE`), violando la política interna de "Azure = solo releases
estables". Todo el trabajo estaba respaldado de forma idéntica en **GitHub**
(`github`, `IACygnus/Kinetix`), por lo que el borrado en Azure fue seguro.

## Safety check previo (obligatorio antes de borrar)
Antes de tocar Azure se verificó que GitHub tuviera el respaldo completo:
- `github/backup-trabajo-local` → tip `58aab74` (HF20) + `b45dfd5` + historia completa.
- Ambos tags en GitHub apuntando a los MISMOS hashes que Azure:
  - `pre-sprint-3.0-20260708_190944` → 513dc86 → b45dfd5
  - `pre-sprint-3.0-post-hf20-20260709_115832` → de4dcd8 → 58aab74

## Acciones

### 1. Limpieza Azure DevOps (origin) — solo borrados
- Borrado: branch `refs/heads/backup-trabajo-local` → `[deleted]`
- Borrado: tag `pre-sprint-3.0-20260708_190944` → `[deleted]`
- Borrado: tag `pre-sprint-3.0-post-hf20-20260709_115832` → `[deleted]`
- **Azure/main INTACTA** (no se tocó): tip `2cfe0ea feat: v3.1.0` (2026-04-21).

Estado de Azure (origin) tras la limpieza — `git ls-remote origin`:
- `refs/heads/main` → 2cfe0ea (única branch)
- tags de release conservados: `v1.3.0`, `v3.0.0`, `v3.1.0`
- SIN `backup-trabajo-local`, SIN tags `pre-sprint-3.0-*`

> Nota: `origin/feature/grafana-influxdb-v1.3.0` que figuraba en la auditoría era
> un remote-tracking ref local obsoleto; `ls-remote` confirmó que ya no existe en
> Azure. No fue tocado por esta limpieza.

### 2. Verificación GitHub intacto (post-borrado)
- `github/backup-trabajo-local`: 6 commits verificados (9531eb3 → 2740786 →
  b20c6e3 → a526897 → b45dfd5 → 58aab74).
- Ambos tags `pre-sprint-3.0-*` presentes en GitHub: verificados.
- Todo el trabajo activo sigue respaldado en `github/IACygnus/Kinetix`.

### 3. .gitignore actualizado
- Agregada regla: `backups/`
- Los backups locales (`db_full_*.sql`, `codigo_snapshot_*.tar.gz`) del snapshot
  pre-Sprint 3.0 quedan en disco pero fuera del repo.
- `backups/` nunca estuvo tracked (verificado con `git ls-files backups/` vacío).

## Regla establecida (para futuros commits)
- Trabajo activo (HFs, sprints, docs): push **SOLO a `github`**.
- Azure DevOps (`origin`): reservado para releases estables autorizadas por Fredy.
- **NO ejecutar `git push origin`** en flujos de desarrollo.
- **NO usar `git push --all` ni `git push` sin remote explícito** (pueden alcanzar origin).

## Estado
Azure limpio, GitHub intacto. Listo para arrancar Sprint 3.0.
