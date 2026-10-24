<!-- g360:agents:begin -->
# AGENTS.md — g360-erp-nc-sustentor

Microherramienta avanzada del ecosistema G360 para la automatización de cuadros de sustento — Notas de Crédito (NC), Débito (NDB), Factura Directa —, reportes a

> El bloque entre los markers `g360:agents` lo genera `g360 agents` y se
> regenera sin perder lo que escribas afuera.

## Verificación

Un solo comando deja el repo listo y verifica que todo esté en verde:

```bash
uv sync
uv run pytest
```

- Stack: python (uv)
- Tests: pytest en `tests/`

## Instalación

```bash
uv sync
```


## Estructura

- `src/`
- `tests/`
- `g360/`
- `main.py`

## Variables de entorno

El código lee estas variables: documentá cada una con su default en `.env.example`.

- `G360_DATA_DIR`
- `G360_DB_ORIGEN`
- `G360_LOG_DIR`
- `G360_LOG_LEVEL`
- `G360_PORTABLE_DIR`

## Convenciones

- Tests con `pytest` en `tests/`.
- Dependencias con `uv` (`uv.lock` versionado).
- Comentarios que expliquen el *por qué*, no el *qué*.

## Reglas de este repo

- **Autosuficiente**: `git clone` + el comando de verificación debe dejar la app levantada y los tests en verde, sin red y sin ayuda de una persona.
- **Tests honestos**: nada de `it.skip`, `pytest.mark.skip`, `xfail` ni `assert true` para forzar verde.
- **Entorno declarativo**: toda variable de entorno va en `.env.example` con un default seguro.
- **Sin paths de tu máquina**: nada de rutas absolutas locales ni secretos en el código.
- **Evidencia**: al entregar, reportá el comando que corriste y su salida. Si no pudiste verificar, decilo.
<!-- g360:agents:end -->
