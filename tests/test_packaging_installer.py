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


def test_borrado_datos_condicionado_a_silent_y_purge_data() -> None:
    """El desinstalador no debe borrar datos en modo silencioso sin /PURGE_DATA=1.

    CurUninstallStepChanged debe:
      - salir temprano (sin DelTree) cuando UninstallSilent y no /PURGE_DATA=1;
      - permitir el borrado solo si interactivo, o silencioso + /PURGE_DATA=1;
      - mantener MsgBox con MB_YESNO or MB_DEFBUTTON2 (No por defecto).
    """
    texto = ISS.read_text(encoding="utf-8")

    # Guardia de silencio: si UninstallSilent y no PURGE_DATA → no borra.
    assert "UninstallSilent" in texto, (
        "Falta la guardia UninstallSilent en CurUninstallStepChanged."
    )
    assert "Purge := ExpandConstant('{param:PURGE_DATA|0}') = '1'" in texto, (
        "Falta la lectura del parámetro {param:PURGE_DATA|0} en la variable Purge."
    )
    assert "UninstallSilent and not Purge then" in texto, (
        "Falta la condición UninstallSilent and not Purge que evita borrar en silencioso."
    )

    # La rama silenciosa + /PURGE_DATA=1 debe borrar SIN llamar a MsgBox:
    # MsgBox no es suprimible en Inno Setup 7, así que la rama de purge no la usa.
    assert "if UninstallSilent and Purge then" in texto, (
        "Falta la rama UninstallSilent and Purge que borra sin MsgBox."
    )
    # La rama de purge aparece antes del MsgBox y no lo contiene.
    idx_purge = texto.find("if UninstallSilent and Purge then")
    idx_msgbox = texto.find("MsgBox(")
    assert idx_purge != -1 and idx_msgbox != -1 and idx_purge < idx_msgbox, (
        "La rama UninstallSilent and Purge debe preceder al MsgBox y no invocarlo."
    )

    # El borrado solo ocurre con consentimiento explícito (idYes) o purge forzado.
    assert "idYes" in texto, "Falta la comprobación de idYes antes de DelTree."
    assert "DelTree(" in texto, "Falta la llamada a DelTree del directorio de datos."

    # El MsgBox conserva MB_DEFBUTTON2 (No por defecto) y advierte que se conservan.
    assert "MB_YESNO or MB_DEFBUTTON2" in texto, (
        "El MsgBox debe usar MB_DEFBUTTON2 como default."
    )
    assert "los datos se conservan" in texto, (
        "El texto del MsgBox debe indicar que los datos se conservan por defecto."
    )

    # Lectura del parámetro explícito con valor por defecto '0'.
    assert "{param:PURGE_DATA|0}" in texto, (
        "Falta la lectura del parámetro {param:PURGE_DATA|0}."
    )
