# CONTRATO g360-db-ventas <-> g360-erp-nc-sustentor

Contrato entre el productor (g360-db-ventas) y el consumidor (g360-erp-nc-sustentor).

---

## 1. Contratos actuales vigentes

| Campo | Productor escribe | Consumidor valida |
|---|---|---|
| contracto_version | Entero 4 | ventas_db.CONTRACTO_VERSION == 4 |
| db.sha256 | SHA256 del .db VACUUM INTO | _sha256(db_in) != man[db][sha256] |
| db.filas | Total COUNT(*) ventas | COUNT(*) != man_filas |
| tipo | semilla o trabajo | Define modo reemplazo vs merge |
| dias | Lista ISO con checksums | Superset/merge por dia |
| db.fecha_min / db.fecha_max | Rango real de la DB | Usado para comparación pre-import |
| db.soles_total | SUM(soles) del artefacto | Comparado contra local en preview |

---

## 2. Productor canónico — reglas estrictas

El productor canónico (`g360-db-ventas`) emite **solo cartuchos completos** (`tipo: "semilla"`, `incremental: false`, `espejo_completo: true`). No genera incrementales.

### 2.1 Modo de import siempre es reemplazar

- Cartucho completo → reemplazar. El consumidor compara filas+fecha antes de confirmar y muestra alerta si el cartucho es ≤ a lo local.
- Si el usuario confirma reemplazar aunque tenga menos datos → se ejecuta el replace normal con backup previo.
- El productor debe completar `db.filas`, `db.fecha_min`, `db.fecha_max`, `db.soles_total` en el manifiesto; sin ellos el consumidor no puede mostrar la comparación.

### 2.2 Alertas pre-import (produtor canónico)

| Escenario | Mensaje al usuario | Acción |
|---|---|---|
| DB local vacía | "Primera carga — cargando historial completo" | Reemplazar automático |
| Cartucho con más filas | "El cartucho tiene N filas nuevas. Se reemplazará todo." | Reemplazar |
| Cartucho con menos filas | "⚠ Tu DB local tiene más datos que el cartucho. ¿Reemplazar de todos modos?" | Botón Sí / No |
| Fechas coincidentes (mismas filas y fecha_max) | "Datos idénticos — no hay cambios." | Cancelar import |
| Cartucho más antiguo | "⚠ El cartucho termina en YYYY-MM, tu DB llega a YYYY-MM" | Mostrar y preguntar |

La función `comparar_cartucho_vs_local()` calcula estos escenarios leyendo solo el manifiesto (sin extraer la DB), antes de la validación pesada.

### 2.3 Prohibido al productor canónico

- Generar cartuchos `incremental: true` — eso es exclusividad del cliente (capture_service).
- Filtrar líneas en la semilla — `espejo_completo: true` es invariante.
- Declarar `day_checksums` inconsistentes con `quick_check.filas`.

---

## 3. Bugs detectados en base_canonica_20261118_001412.zip

### 3.1 data_quality.status = unknown con 2,8M de filas
- Causa: export.rs:45 pasa None para stats siempre.
- Correccion: calcular QualityStats desde la DB antes de exportar.

### 3.2 price_unitario_status = needs_recalc contradictorio
- 2472 filas pendientes pero attributes_applied dice precio_unitario_recalculated.
- No es bug de integridad pero es confuso.

### 3.3 retention_days = 1277 vs contenido sin retencion
- hardcode en writer.rs:534 contradice config.json.

### 3.4 Sub-captura de BDI
- 2026-11-16: intranet 590 filas/64 BDI vs cartucho 250 filas/2 BDI.
- Hipotesis: split por rango de articulos pierde BDI en algunos chunks.

---

## 4. Validaciones adicionales para el consumidor (warning+log)

1. data_quality.status != unknown si hay filas > 0
2. price_unitario_status consistente con attributes_applied
3. retention_days y contenido consistentes
4. day_checksums suma igual quick_check.filas
5. db.filas == COUNT(*) real del artefacto (antes de importar)
6. db.fecha_min / db.fecha_max coherentes con el rango de datos

---

## 5. Checklist correccion productor g360-db-ventas

| # | Cambio | Prioridad |
|---|---|---|
| 1 | Calcular QualityStats desde DB y pasarlo a export_canonical_snapshot | Alta |
| 2 | Corregir campo contenido en writer.rs:534 | Media |
| 3 | Renombrar retention_days a supabase_retention_days | Media |
| 4 | Investigar sub-captura BDI en captor.rs | Alta |
| 5 | Logging conteo BDI por chunk | Baja |
| 6 | Consistentizar attributes_applied | Baja |
| 7 | Completar db.filas, db.fecha_min, db.fecha_max, db.soles_total en manifiesto | Alta |

---

*Documento generado: 2026-11-17 · Actualizado: 2026-11-18 (productor canónico replace-only + comparación pre-import)*