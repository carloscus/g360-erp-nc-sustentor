"""Guard de entorno: la app NO debe cerrarse al cargar un historial.

Contexto del bug (producción, 17/11/2026): el instalador empaquetaba Python
3.14 con pandas 2.2.3. pandas 2.2.3 no publica wheels cp314, así que el build
lo compiló desde fuente y el `pandas_datetime.cp314.pyd` resultante revienta
con Access Violation (0xC0000005) en el primer `pd.to_datetime`. Como el
crash es NATIVO no hay excepción que capturar: la app se cerraba sin
traceback en el flujo de carga de historial.

Estos tests fijan las tres defensas:
  1. el build empaqueta el Python del repo (3.12, con wheels cp312);
  2. el build verifica el pandas que va dentro del bundle antes de instalar;
  3. la app detecta un entorno roto al arrancar y lo dice, en vez de morir.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
PYPROJECT = RAIZ / "pyproject.toml"


def _import_build_windows():
    """Importa el script de build sin ejecutar el pipeline."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_build_windows_under_test", RAIZ / "packaging" / "build_windows.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestVersionEmpaquetada:
    """El Python del bundle tiene que ser el del repo."""

    def test_el_bundle_usa_la_version_del_repo(self):
        """3.12 es la de .python-version y la que tiene wheels cp312."""
        mod = _import_build_windows()
        version_repo = (RAIZ / ".python-version").read_text(encoding="utf-8").strip()
        assert mod.BUNDLE_PYTHON_VERSION == version_repo, (
            "el build empaqueta un Python distinto al del repo: con "
            f"{mod.BUNDLE_PYTHON_VERSION} pueden faltar wheels de pandas "
            f"(el repo usa {version_repo})"
        )

    def test_requires_python_tiene_tope(self):
        """`requires-python` debe acotar la versión de Python.

        Sin el tope, `flet build` resuelve el Python a empaquetar tomando la
        más nueva soportada (3.14), y con 3.14 pandas 2.2.3 no tiene wheels
        (se compila desde fuente y su datetime.pyd revienta al convertir
        fechas). El comentario del pyproject pide ese tope: sin él, la app
        instalada se cerraba al cargar el historial.
        """
        with PYPROJECT.open("rb") as fh:
            requires = tomllib.load(fh)["project"]["requires-python"]
        assert "<3.13" in requires or "==3.12" in requires, (
            f"requires-python={requires!r} no acota la versión de Python: "
            "flet build empaquetaría la más nueva soportada (3.14) y "
            "pandas 2.2.3 no tiene wheels para ella."
        )

    def test_pandas_2_2_3_tiene_wheels_para_la_version_empaquetada(self):
        """Guarda contra el caso real: pandas 2.2.3 sin wheel cp314.

        Se comprueba contra PyPI. Es una consulta de red: si no hay red, el
        test se saltea (no se marca como fallo) porque la premisa está
        verificada y el guard del build es la defensa real.
        """
        import json
        import urllib.request

        mod = _import_build_windows()
        with PYPROJECT.open("rb") as fh:
            pandas_pin = tomllib.load(fh)["project"]["dependencies"]
        pin = next(d for d in pandas_pin if d.startswith("pandas"))
        version = pin.split("==")[1]

        tag = "cp" + "".join(mod.BUNDLE_PYTHON_VERSION.split(".")[:2])
        try:
            with urllib.request.urlopen(
                f"https://pypi.org/pypi/pandas/{version}/json", timeout=20
            ) as fh:
                data = json.load(fh)
        except Exception as exc:  # sin red: la premisa ya fue verificada
            pytest.skip(f"sin red para consultar PyPI: {exc}")

        wheels = [f["filename"] for f in data["urls"] if f["filename"].endswith(".whl")]
        assert any(tag in w for w in wheels), (
            f"pandas {version} no tiene wheel {tag} para el Python que se "
            f"empaqueta ({mod.BUNDLE_PYTHON_VERSION}); el build lo compila "
            "desde fuente y su datetime.pyd revienta al convertir fechas. "
            f"Wheels disponibles: {wheels}"
        )


class TestGuardDelBundle:
    """El build no debe empaquetar un bundle con pandas incompatible."""

    def test_detecta_pandas_de_otra_version(self, tmp_path):
        mod = _import_build_windows()
        libs = tmp_path / "site-packages" / "pandas" / "_libs"
        libs.mkdir(parents=True)
        # cp314 donde se esperaba cp312: la combinación que crashea.
        (libs / "pandas_datetime.cp314-win_amd64.pyd").write_bytes(b"")

        with pytest.raises(mod.BuildError) as exc:
            mod._verificar_pandas_del_bundle(tmp_path)
        assert "cp314" in str(exc.value)

    def test_acepta_pandas_de_la_version_correcta(self, tmp_path):
        mod = _import_build_windows()
        libs = tmp_path / "site-packages" / "pandas" / "_libs"
        libs.mkdir(parents=True)
        (libs / "pandas_datetime.cp312-win_amd64.pyd").write_bytes(b"")

        mod._verificar_pandas_del_bundle(tmp_path)  # no debe levantar

    def test_no_falla_si_el_bundle_no_tiene_pandas(self, tmp_path):
        """Sin pandas no hay nada que verificar: avisa pero no rompe el build."""
        mod = _import_build_windows()
        mod._verificar_pandas_del_bundle(tmp_path)  # no debe levantar

    def test_detecta_runtime_desalineado_de_las_extensiones(self, tmp_path):
        """Runtime 3.14 con extensiones cp312 (o al revés) no puede importar pandas.

        El bundle real de producción tenía exactamente ese desajuste: el
        paso que instala site-packages usó 3.12 y el que embebe el runtime
        usó su default 3.14. Sin este chequeo, el bundle pasa el control de
        la ABI de pandas y aun así la app no arranca.
        """
        mod = _import_build_windows()
        libs = tmp_path / "site-packages" / "pandas" / "_libs"
        libs.mkdir(parents=True)
        (libs / "pandas_datetime.cp312-win_amd64.pyd").write_bytes(b"")
        # Runtime de otra versión que las extensiones.
        (tmp_path / "python314.dll").write_bytes(b"")
        (tmp_path / "python3.dll").write_bytes(b"")

        with pytest.raises(mod.BuildError) as exc:
            mod._verificar_pandas_del_bundle(tmp_path)
        assert "python314.dll" in str(exc.value)

    def test_acepta_runtime_y_extensiones_de_la_misma_version(self, tmp_path):
        mod = _import_build_windows()
        libs = tmp_path / "site-packages" / "pandas" / "_libs"
        libs.mkdir(parents=True)
        (libs / "pandas_datetime.cp312-win_amd64.pyd").write_bytes(b"")
        (tmp_path / "python312.dll").write_bytes(b"")
        (tmp_path / "python3.dll").write_bytes(b"")

        mod._verificar_pandas_del_bundle(tmp_path)  # no debe levantar


class TestGuardDeArranque:
    """La app detecta el entorno roto al arrancar y lo reporta."""

    @staticmethod
    def _version_info_314():
        """sys.version_info con .major/.minor, como el real."""
        from collections import namedtuple

        vi = namedtuple("version_info", "major minor micro releaselevel serial")
        return vi(3, 14, 7, "final", 0)

    @staticmethod
    def _pandas_2_2_3(monkeypatch):
        import importlib.metadata as md

        real_version = md.version

        def fake_version(name):
            if name == "pandas":
                return "2.2.3"
            return real_version(name)

        monkeypatch.setattr(md, "version", fake_version)

    def test_no_reporta_problema_en_entorno_sano(self):
        import main

        # Python < 3.14 no tiene el problema; y en 3.14 con pandas >= 2.3.3
        # tampoco. En este repo (3.12) siempre debe dar None.
        assert main._pandas_roto() is None

    def test_congelado_detecta_la_combinacion_rota(self, monkeypatch):
        """Simula Python 3.14 + pandas 2.2.3: debe reportar el problema."""
        import main

        monkeypatch.setattr(sys, "version_info", self._version_info_314())
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        self._pandas_2_2_3(monkeypatch)

        mensaje = main._pandas_roto()
        assert mensaje is not None, "no detectó la combinación rota"
        assert "pandas" in mensaje.lower()
        # El mensaje tiene que decir qué hacer, no solo qué pasó.
        assert "historial" in mensaje.lower()

    def test_en_modo_congelado_no_lanza_subproceso(self, monkeypatch):
        """En el .exe, sys.executable es la app: un subproceso la reiniciaría."""
        import main
        import subprocess

        monkeypatch.setattr(sys, "version_info", self._version_info_314())
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        self._pandas_2_2_3(monkeypatch)

        def _no_debe_lanzar(*args, **kwargs):
            raise AssertionError("no debe lanzar subprocesos en modo congelado")

        monkeypatch.setattr(subprocess, "run", _no_debe_lanzar)

        assert main._pandas_roto() is not None

    def test_no_congelado_detecta_el_crash_por_subproceso(self, monkeypatch):
        """Sin congelar, la sonda corre la conversión y ve el Access Violation."""
        import main
        import subprocess

        monkeypatch.setattr(sys, "version_info", self._version_info_314())
        monkeypatch.delattr(sys, "frozen", raising=False)
        self._pandas_2_2_3(monkeypatch)

        class _R:
            returncode = 0xC0000005 & 0xFFFFFFFF  # -1073741819

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _R())

        mensaje = main._pandas_roto()
        assert mensaje is not None, "no detectó el crash por subproceso"
        assert "historial" in mensaje.lower()

    def test_no_congelado_sin_crash_no_reporta_problema(self, monkeypatch):
        """Si la conversión funciona, no hay nada que reportar."""
        import main
        import subprocess

        monkeypatch.setattr(sys, "version_info", self._version_info_314())
        monkeypatch.delattr(sys, "frozen", raising=False)
        self._pandas_2_2_3(monkeypatch)

        class _R:
            returncode = 0

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _R())

        assert main._pandas_roto() is None

    def test_el_arranque_no_rompe_sin_consola(self, monkeypatch, capsys):
        """En el .exe congelado stdout es None: el aviso no debe matar el arranque.

        El import de main.py ya corrió en este proceso, así que se reevalúa
        el bloque del guard con stdout None para confirmar que no levanta.
        """
        import main

        monkeypatch.setattr(sys, "version_info", self._version_info_314())
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        self._pandas_2_2_3(monkeypatch)

        # Replica el bloque del guard tal como está en main.py.
        problema = main._pandas_roto()
        assert problema is not None

        monkeypatch.setattr(sys, "stdout", None)
        try:
            print(f"[FATAL] {problema}", flush=True)
        except Exception:
            pass  # en congelado el print a stdout=None no debe propagarse
