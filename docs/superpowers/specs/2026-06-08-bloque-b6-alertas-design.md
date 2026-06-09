# Bloque B6 — Alertas sobrias (diseño)

Fecha: 2026-06-08
Estado: aprobado para escribir plan de implementación

## Contexto

Sexto y último sub-proyecto del Motor de Cobertura del Consejo. B1–B5 ya están en producción.
El brief (§9) pide **alertas sobrias y factuales, NO gamificadas**:
- ✅ "Auditoría: 1 de 4 revisiones realizadas — Atrasado."
- ❌ "¡Estás más cerca de lograr tus objetivos!"

Todas las alertas son **señales derivadas** de datos que ya existen — sin modelo nuevo:
- Tareas (acuerdos): `ActionTask` con `due_date`, `status`.
- Cobertura: `coverage_rows` (B4, `app/services/governance/coverage_board.py`) → `estado`
  ∈ `en_tiempo|riesgo|atrasado|critico`.
- KPIs: el cierre de mes (E) guarda `MonthlyPlan.review["signals"]["kpis"]` (lista de
  `{label, value, target, unit, on_track}`). Las desviaciones salen del último mes `done`.

## Alcance de B6

Un endpoint que computa la lista de alertas + un panel sobrio que las muestra arriba del plan.

**Fuera de alcance de B6**: email/push, alertas en tiempo real, temas emergentes, KPIs
continuos (solo del último cierre de mes).

## Backend

### Servicio puro `app/services/governance/alerts.py`
```
def compute_alerts(tasks, coverage_rows, kpi_signals, today, horizon_days: int = 7) -> list[dict]
```
- `tasks`: objetos con `.status` y `.due_date` (date|None).
- `coverage_rows`: la salida de `coverage_board.coverage_rows` (dicts con `label, esperadas,
  realizadas, estado`).
- `kpi_signals`: lista de dicts `{label, value, target, unit, on_track}`.
- Devuelve `list[dict]`, cada uno `{level: "critical"|"warning"|"info", category, message}`.

Reglas (todas factuales):
1. **Acuerdos vencidos** (`critical`, category `acuerdo`): tareas con `status != "completada"`
   y `due_date is not None` y `due_date < today`. Si hay N>0 → un alert
   "N acuerdo(s) vencido(s) sin validar." (singular/plural correcto).
2. **Acuerdos por vencer** (`warning`, category `acuerdo`): `status != "completada"` y
   `today <= due_date <= today + horizon_days`. Si N>0 → "N acuerdo(s) vence(n) en los
   próximos {horizon_days} días."
3. **Temas atrasados/críticos** (category `cobertura`): por cada row con
   `estado == "critico"` → `critical` "{label}: {realizadas} de {esperadas} revisiones —
   Crítico."; con `estado == "atrasado"` → `warning` "… — Atrasado." (los `en_tiempo`/`riesgo`
   no generan alerta).
4. **Desviación de KPI** (`warning`, category `kpi`): por cada `k` en `kpi_signals` con
   `k.get("on_track") is False` → "{label}: {value}{unit} (meta {target}{unit}) — fuera de
   objetivo." (omite `unit`/`target` si son `None`).

Orden de salida: críticos primero, luego warnings, luego info (estable dentro de cada nivel).

### Esquema `app/schemas/alerts.py`
```python
class AlertItem(BaseModel):
    level: str
    category: str
    message: str
```

### Endpoint `GET /annual-plan/alertas`
- Resuelve el plan (`_current_plan`); 404 si no hay.
- Carga meses (con `selectinload(MonthlyPlan.objectives)`) → reúne `obj_ids` → tareas vía
  `_tasks_by_objective`.
- Carga temas (`active`) → `coverage_rows(themes, months, compute_active_month_index(...))`.
- `kpi_signals`: del **último mes con `status == "done"` y `review`** →
  `(review.get("signals") or {}).get("kpis") or []`. Si no hay mes cerrado → `[]`.
- `alerts = compute_alerts(tasks, rows, kpi_signals, date.today())`.
- Devuelve `[AlertItem(**a) for a in alerts]`.

## Frontend

- `frontend/src/lib/alerts.ts`: tipo `AlertItem` (level, category, message) + `getAlertas()`.
- `frontend/src/components/plan/AlertsPanel.tsx`: lista sobria; cada alerta una fila con
  **borde izquierdo de color por nivel** (critical=rojo, warning=ámbar, info=gris) + el texto
  factual. Si no hay alertas → no renderiza nada (`return null`).
- Montado **al inicio de la vista activa** de `/dashboard/plan` (encima del toggle
  Meses/Tablero/Cobertura), para que sea lo primero que se vea. Fetch en mount.

## Pruebas

Backend (pytest):
- `compute_alerts` unit: cada categoría dispara (acuerdo vencido, por vencer, tema atrasado,
  tema crítico, KPI off-track) y el caso sin alertas (lista vacía). Verifica niveles y orden
  (críticos primero).
- Endpoint `alertas`: 200 con la lista (db mockeada con el patrón existente).
- Suite completa verde, sin regresiones.

Frontend: `tsc --noEmit` + `npm run build` verdes; lint limpio en archivos nuevos.

## Criterio de "hecho" para B6

- `GET /annual-plan/alertas` devuelve alertas factuales derivadas (acuerdos vencidos/por
  vencer, temas atrasados/críticos, KPIs off-track del último cierre).
- El panel de Alertas aparece arriba del plan con tono sobrio.
- Suite backend verde; build frontend verde.

## Riesgos / decisiones abiertas

- Sin migración (no toca DB).
- KPIs: solo del último mes cerrado (no continuo). Si no se ha cerrado ningún mes, no hay
  alertas de KPI.
- Tono: factual, sin gamificación (decisión firme del proyecto).
