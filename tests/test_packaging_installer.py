"""La versión vive en un solo lugar: pyproject.toml.

El instalador Inno Setup (`packaging/g360.iss`) repite la versión en dos
directivas (AppVersion y el nombre del OutputBaseFilename). Antes divergían
en silencio: se subía pyproject y el .exe seguía saliendo con la versión
vieja. Este test convierte esa divergencia en un fallo ruidoso.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PYPROJECT = RAIZ / "pyproject.toml"
ISS = RAIZ / "packaging" / "g360.iss"


def _version_pyproject() -> str:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def _version_iss() -> tuple[str, str]:
    """Devuelve (AppVersion, sufijo de OutputBaseFilename)."""
    texto = ISS.read_text(encoding="utf-8")
    m_app = re.search(r"^AppVersion=(.+)$", texto, re.MULTILINE)
    m_out = re.search(r"^OutputBaseFilename=(.+)$", texto, re.MULTILINE)
    assert m_app, "packaging/g360.iss no declara AppVersion"
    assert m_out, "packaging/g360.iss no declara OutputBaseFilename"
    return m_app.group(1).strip(), m_out.group(1).strip()


def test_appversion_coincide_con_pyproject() -> None:
    esperada = _version_pyproject()
    app_version, _ = _version_iss()
    assert app_version == esperada, (
        f"g360.iss AppVersion={app_version!r} != pyproject {esperada!r}. "
        "Actualizá packaging/g360.iss al subir la versión."
    )


def test_output_base_filename_incluye_la_version() -> None:
    esperada = _version_pyproject()
    _, output = _version_iss()
    assert esperada in output, (
        f"OutputBaseFilename={output!r} no contiene la versión {esperada!r}. "
        "El instalador saldría con un nombre desactualizado."
    )
