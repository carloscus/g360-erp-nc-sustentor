"""Build reproducible de Windows: bundle Flet + instalador Inno Setup.

Pipeline primario (vía nativa de flet, ya verificado que produce el bundle
completo):
  a. `flet build windows` (SIN --release: flet lo rechaza). Deja el bundle
     completo en build/flutter/build/windows/x64/runner/Release.
  b. Copia ese bundle a build/windows/x64/runner/Release (la ruta que lee
     [Files] de packaging/g360.iss), con rmtree del destino y verificación
     de que el conteo de archivos coincida.
  c. ISCC compila el instalador en dist.

Respaldo (solo si el paso a no produjo un bundle fresco):
  el camino manual por %TEMP%: configure + cmake build en
  %TEMP%\\opencode\\g360build y copia del runner al path canónico.
  Las variables SERIOUS_PYTHON_APP, SERIOUS_PYTHON_SITE_PACKAGES y
  FLUTTER_ROOT aplican SOLO a ese camino de respaldo.

¿Por qué el parche de jni (CMAKE_DISABLE_FIND_PACKAGE_JNI) ya no está?
  flet regenera build/flutter/windows/CMakeLists.txt en cada corrida, así que
  el parche se pierde tras cada build (E4). Además, en la corrida de E2 el
  plugin jni estuvo presente y el build salió bien. Dejamos de parchear; el
  camino primario no lo necesita.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# --- Constantes del proyecto -------------------------------------------------

ARTIFACT = "g360-nc-sustentor"
SETUP_NAME = "G360-NC-Sustentor-1.2.2-Setup.exe"
# Umbral generoso para detectar un bundle vacío o truncado: el conteo exacto
# depende de las dependencias instaladas, así que no usamos un número fijo.
BUNDLE_FILE_MIN = 1000

# La raíz del repo es el padre de packaging/. El usuario corre desde la raíz,
# pero resolvemos por __file__ para no depender del cwd.
REPO_ROOT = Path(__file__).resolve().parent.parent

BUILD_DIR = REPO_ROOT / "build"
DIST_DIR = REPO_ROOT / "dist"
ISS_FILE = REPO_ROOT / "packaging" / "g360.iss"
FLUTTER_DIR = BUILD_DIR / "flutter"
PYTHON_APP_DIR = BUILD_DIR / "python-app"
SITE_PACKAGES_DIR = BUILD_DIR / "site-packages"
RUNNER_RELEASE = BUILD_DIR / "windows" / "x64" / "runner" / "Release"

# Donde flet deja el bundle de Windows (E1/E2).
FLUTTER_BUILD_RELEASE = (
    FLUTTER_DIR / "build" / "windows" / "x64" / "runner" / "Release"
)

# CMake genera bien solo fuera de Documents; %TEMP%\opencode es la ruta que ya
# se verificó como escribible en esta máquina.
CMAKE_FALLBACKS = [
    r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe",
]
ISCC_FALLBACKS = [
    r"C:\Program Files\Inno Setup 7\ISCC.exe",
]
# Solo rutas GENÉRICAS de instalación. Un path de una máquina concreta (p. ej.
# C:\Users\<user>\flutter\...) viola la regla de AGENTS.md "sin paths de tu
# máquina". Para una instalación fuera de estas rutas usá G360_FLUTTER_ROOT.
FLUTTER_FALLBACKS = [
    r"C:\flutter",
    r"C:\src\flutter",
]


class BuildError(RuntimeError):
    """Fallo de un paso del pipeline; el mensaje explica cómo seguir."""


# --- Utilidades --------------------------------------------------------------

def log(msg: str) -> None:
    print(msg, flush=True)


def stage(title: str) -> float:
    log("")
    log(f"=== {title} ===")
    return time.monotonic()


def report(cmd: str, rc: int, started: float) -> None:
    elapsed = time.monotonic() - started
    log(f"CMD: {cmd}")
    log(f"RC : {rc}  ({elapsed:.1f} s)")


def find_tool(
    name: str,
    fallbacks: list[str],
    *,
    verify: callable | None = None,
    raw_fallback: list[str] | None = None,
) -> list[str]:
    """Descubre una herramienta y la devuelve como **argv** (lista), nunca como
    un string con espacios: un string con espacios no es ejecutable y
    `subprocess.run` lanzaría `FileNotFoundError`.

    `verify` recibe la ruta y devuelve True si la ruta es usable (para el
    caso de flutter, que es un directorio y no un ejecutable).
    `raw_fallback` es un argv alternativo que no podemos verificar en el PATH
    (p. ej. `["uv", "run", "flet"]`): si todo lo demás falla, se devuelve tal
    cual, ya tokenizado.
    """
    exe = shutil.which(name)
    if exe:
        return [exe]
    for candidate in fallbacks:
        if Path(candidate).exists() and (verify is None or verify(candidate)):
            return [candidate]
    if raw_fallback:
        launcher = raw_fallback[0]
        if shutil.which(launcher) is None:
            raise BuildError(
                f"No se encontró `{name}` ni `{launcher}` (fallback "
                f"`{' '.join(raw_fallback)}`). Instalá {name} o {launcher} y "
                "agregalo al PATH, o usá el entorno del repo (uv)."
            )
        return list(raw_fallback)
    raise BuildError(
        f"No se encontró `{name}` ni en PATH ni en las rutas conocidas "
        f"({', '.join(fallbacks)}). Instalalo o agregalo al PATH y reintentá."
    )


def run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None,
        tolerate_failure: bool = False, label: str = "") -> tuple[int, str]:
    """Ejecuta un comando, loguea CMD/RC/duración y opcionalmente tolera fallo.

    Capturamos stdout+stderr juntos para inspeccionar la salida de flet y
    distinguir un bundle fresco de un fallo real. Igual la volcamos al log.
    """
    printable = " ".join(cmd)
    if label:
        log(f"[{label}]")
    started = time.monotonic()
    result = subprocess.run(
        cmd, cwd=cwd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, errors="replace",
    )
    report(printable, result.returncode, started)
    output = result.stdout or ""
    if output:
        log(output.rstrip())
    if result.returncode != 0 and not tolerate_failure:
        raise BuildError(
            f"Falló `{printable}` (RC={result.returncode}). "
            "Revisá la salida anterior; el pipeline se detiene acá."
        )
    return result.returncode, output


def count_files(root: Path) -> int:
    return sum(1 for p in root.rglob("*") if p.is_file())


def human_mb(num_bytes: int) -> str:
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def _newest_mtime(root: Path) -> float | None:
    """mtime más reciente entre los archivos de `root` (None si no hay)."""
    newest: float | None = None
    for p in root.rglob("*"):
        if p.is_file():
            m = p.stat().st_mtime
            if newest is None or m > newest:
                newest = m
    return newest


def _guard_epoch(started_at: float) -> None:
    """started_at debe venir en epoch (time.time()), no en monotonic.

    Se compara contra stat().st_mtime, que es epoch. Con una base
    incompatible el chequeo de frescura quedaría muerto y se empaquetaría
    código viejo. BuildError (no assert) porque `python -O` los desactiva.
    """
    if started_at < 1e9:
        raise BuildError(
            f"started_at={started_at} no está en epoch (parece monotonic). El "
            "chequeo de frescura compara contra st_mtime, que es epoch; con una "
            "base incompatible el guard queda muerto y se empaqueta staging "
            "viejo. Bug interno: pasá time.time(), no time.monotonic()."
        )


def _bundle_is_fresh(bundle: Path, started_at: float, *,
                     tolerance_s: float = 2.0) -> bool:
    """True si `bundle` existe y contiene un bundle de flet FRESCO.

    Condiciones de éxito del paso (a) (Q2):
      - existe build/flutter/build/windows/x64/runner/Release
      - dentro están g360-nc-sustentor.exe, app/main.pyc y el directorio
        site-packages/
      - esos archivos son frescos: mtime >= started_at (tolerancia de 2 s)
    """
    _guard_epoch(started_at)
    if not bundle.is_dir():
        return False
    required_files = [bundle / "g360-nc-sustentor.exe",
                      bundle / "app" / "main.pyc"]
    required_dirs = [bundle / "site-packages"]
    for f in required_files:
        if not f.is_file():
            return False
    for d in required_dirs:
        if not d.is_dir():
            return False
    threshold = started_at - tolerance_s
    for f in required_files:
        if f.stat().st_mtime < threshold:
            return False
    # El bundle debe tener al menos un archivo reciente (no un esqueleto viejo).
    newest = _newest_mtime(bundle)
    if newest is None or newest < threshold:
        return False
    return True


# --- Descubrimiento de herramientas ------------------------------------------

def _is_flutter_root(path: str | Path) -> bool:
    """True si `path` es la RAÍZ de un SDK Flutter (contiene bin/flutter[.bat])."""
    try:
        base = Path(path)
    except TypeError:
        return False
    if not base.is_dir():
        return False
    return any(
        (base / "bin" / exe).is_file()
        for exe in ("flutter", "flutter.bat", "flutter.exe")
    )


def discover_flutter() -> str:
    """Ubica la RAÍZ del Flutter SDK (la carpeta que contiene `bin/`), en este
    orden: (1) `G360_FLUTTER_ROOT` si está definida y es una raíz válida,
    (2) `flutter` en PATH, (3) el `flutterRoot` que flet dejó en el
    package_config.json de build\\flutter\\.dart_tool, (4) FLUTTER_FALLBACKS.

    `shutil.which("flutter")` devuelve el EJECUTABLE (p. ej. ...\\bin\\flutter.bat),
    no la raíz: convertimos el exe a su raíz y la validamos; si no valida,
    seguimos con las fuentes siguientes en vez de devolver basura. Nunca
    devolvemos el ejecutable como raíz.
    """
    # (1) Override explícito: permite instalaciones fuera de las rutas genéricas
    # sin volver a hardcodear el path de una máquina en el código.
    override = os.environ.get("G360_FLUTTER_ROOT")
    if override and _is_flutter_root(override):
        return override

    # (2) PATH: which() da el exe (<raíz>\\bin\\flutter[.bat]); el padre del
    # padre es la raíz del SDK.
    which = shutil.which("flutter")
    if which:
        root = Path(which).resolve().parent.parent
        if _is_flutter_root(root):
            return str(root)

    pkg_config = FLUTTER_DIR / ".dart_tool" / "package_config.json"
    if pkg_config.is_file():
        try:
            data = json.loads(pkg_config.read_text(encoding="utf-8"))
            root = data.get("flutterRoot")
            if root:
                # flutterRoot viene como file:/// URI.
                path = root.replace("file:///", "").replace("/", os.sep)
                # Validamos que sea realmente una raíz de SDK Flutter, no solo
                # un directorio que existe: un flutterRoot genérico no es un SDK.
                if _is_flutter_root(path):
                    return path
        except (json.JSONDecodeError, OSError) as exc:
            log(f"  Aviso: no se pudo leer {pkg_config}: {exc}")

    for candidate in FLUTTER_FALLBACKS:
        if _is_flutter_root(candidate):
            return candidate

    raise BuildError(
        "No se encontró el Flutter SDK. Se intentó G360_FLUTTER_ROOT, flutter "
        f"en PATH, {pkg_config} (campo flutterRoot) y {FLUTTER_FALLBACKS}. "
        "Instalá Flutter, agregalo al PATH, o definí G360_FLUTTER_ROOT "
        "apuntando a la carpeta que contiene bin/, y reintentá."
    )


# --- Pasos del pipeline ------------------------------------------------------

def step_a_flet_build(flet_argv: list[str]) -> str:
    """(a) `flet build windows` (vía nativa). Devuelve la ruta del bundle.

    Invoca `flet build windows` SIN --release (flet lo rechaza: E1) y con los
    --exclude/--include de E2. Si flet termina con RC != 0 se tolera SOLO cuando
    dejó un bundle FRESCO (ver _bundle_is_fresh): el fallo real de flet es el
    PermissionError de copy_build_output, que ocurre tras construir el bundle
    (E3). Si no hay bundle fresco, aborta con BuildError distinguiendo "no
    produjo bundle" de "bundle viejo", e incluye las últimas líneas de la
    salida de flet para diagnóstico.

    Sin --yes: si falta el SDK de Flutter, preferimos fallar rápido a que flet
    descargue ~1 GB.
    """
    stage("(a) flet build windows (bundle nativo)")
    # started_at en EPOCH (time.time()), no monotonic: se compara contra
    # stat().st_mtime, que es epoch. Tomado ANTES de lanzar flet.
    started_at = time.time()
    cmd = [*flet_argv, "build", "windows",
           "--exclude", ".venv", ".git", "build", "build_old", "dist", "tests",
           "_e2e_output", "portable",
           "--include", "catalog"]
    rc, output = run(cmd, cwd=REPO_ROOT, tolerate_failure=True, label="flet build")

    bundle = FLUTTER_BUILD_RELEASE
    if _bundle_is_fresh(bundle, started_at):
        if rc != 0:
            log("  flet terminó con RC != 0 pero dejó un bundle fresco; se "
                "tolerá (el fallo real de flet es el PermissionError de "
                "copy_build_output, tras construir el bundle).")
        else:
            log("  flet build terminó con RC=0; bundle generado en esta corrida.")
        return str(bundle)

    # No hay bundle fresco: distinguir causa y dar diagnóstico.
    tail = "\n".join(output.splitlines()[-15:]) if output else "(sin salida)"
    if not bundle.is_dir():
        raise BuildError(
            "flet build no produjo el bundle esperado en "
            f"{bundle}. Revisá la salida de flet más abajo.\n"
            f"Últimas líneas de flet:\n{tail}"
        )
    raise BuildError(
        f"El bundle en {bundle} existe pero no es fresco (falta "
        "g360-nc-sustentor.exe, app/main.pyc o site-packages/, o su mtime es "
        "de una corrida anterior). No se empaquetaría código viejo.\n"
        f"Últimas líneas de flet:\n{tail}"
    )


def step_b_copy_bundle(src: Path) -> None:
    """(b) Copia el bundle Release de flet al path canónico que lee g360.iss.

    El destino se limpia con rmtree antes de copiar (evita huérfanos de una
    corrida previa que [Files] con recursesubdirs empaquetaría). Luego se
    verifica que count_files(origen) == count_files(destino); si difieren,
    aborta para no empaquetar un bundle incompleto.

    Usamos copytree(..., dirs_exist_ok=True) y eliminamos el mkdir previo:
    copytree crea el destino y, con dirs_exist_ok=True, no falla si el path
    ya existe (flet a veces deja RUNNER_RELEASE preexistente/vacío).
    """
    stage("(b) copiar bundle Release a build\\windows\\x64\\runner\\Release")
    if not src.is_dir():
        raise BuildError(
            f"El bundle no existe en {src}. No hay nada que copiar al path "
            "canónico del .iss."
        )
    if RUNNER_RELEASE.exists():
        log(f"  Limpiando destino {RUNNER_RELEASE} (evita huérfanos).")
        try:
            shutil.rmtree(RUNNER_RELEASE)
        except (OSError, shutil.Error) as exc:
            raise BuildError(
                f"No se pudo limpiar el destino {RUNNER_RELEASE}: {exc}. Es "
                "probable que un archivo esté en uso (el .exe abierto u otro "
                "proceso bloqueando la carpeta). Cerrá la app y reintentá."
            ) from exc
    started = time.monotonic()
    try:
        shutil.copytree(src, RUNNER_RELEASE, dirs_exist_ok=True)
    except (OSError, shutil.Error) as exc:
        raise BuildError(
            f"No se pudo copiar el bundle a {RUNNER_RELEASE}: {exc}. Es probable "
            "que un archivo esté en uso (el .exe abierto): cerrá la app y "
            "reintentá."
        ) from exc

    src_count = count_files(src)
    copied = count_files(RUNNER_RELEASE)
    log(f"  {copied} archivos en {RUNNER_RELEASE} "
        f"({time.monotonic() - started:.1f} s)")
    if copied == 0:
        raise BuildError(f"La copia dejó {RUNNER_RELEASE} vacío; abortando.")
    if copied < BUNDLE_FILE_MIN:
        raise BuildError(
            f"El destino {RUNNER_RELEASE} tiene solo {copied} archivos, por "
            f"debajo del umbral mínimo {BUNDLE_FILE_MIN}. El bundle puede estar "
            "vacío o truncado; abortando para no empaquetar un instalador roto."
        )
    if copied != src_count:
        raise BuildError(
            f"El destino {RUNNER_RELEASE} tiene {copied} archivos pero el origen "
            f"{src} tiene {src_count}. La copia no quedó idéntica; abortando para "
            "no empaquetar un bundle incompleto o con huérfanos."
        )


def step_c_configure(cmake: str, build_tmp: Path, env: dict) -> None:
    """Configura CMake en %TEMP% (fuera de Documents) — camino de respaldo."""
    stage("(respaldo) cmake configure en %TEMP%")
    cmd = [
        cmake,
        "-S", str(FLUTTER_DIR / "windows"),
        "-B", str(build_tmp),
        "-G", "Visual Studio 17 2022",
        "-A", "x64",
        "-DFLUTTER_TARGET_PLATFORM=windows-x64",
    ]
    run(cmd, cwd=REPO_ROOT, env=env)


def step_d_build(cmake: str, build_tmp: Path, env: dict) -> None:
    """Compila e instala el runner — camino de respaldo."""
    stage("(respaldo) cmake build --target INSTALL")
    cmd = [cmake, "--build", str(build_tmp), "--config", "Release",
           "--target", "INSTALL"]
    run(cmd, cwd=REPO_ROOT, env=env)


def _manual_fallback(cmake: str, flutter_root: str) -> str:
    """Camino manual de respaldo por %TEMP%.

    Se invoca SOLO cuando el camino nativo de flet no dejó un bundle fresco.
    Devuelve la ruta al runner Release generado.
    """
    stage("(respaldo) camino manual por %TEMP%\\opencode\\g360build")
    tmp_root = Path(os.environ.get("TEMP", r"C:\Windows\Temp")) / "opencode"
    build_tmp = tmp_root / "g360build"
    tmp_root.mkdir(parents=True, exist_ok=True)
    if build_tmp.exists():
        # Solo limpiamos el build temporal: es regenerable.
        log(f"Limpiando build temporal {build_tmp}")
        try:
            shutil.rmtree(build_tmp, ignore_errors=False)
        except (OSError, shutil.Error) as exc:
            raise BuildError(
                f"No se pudo limpiar el build temporal {build_tmp}: {exc}. Es "
                "probable que un archivo esté en uso: cerrá la app y reintentá."
            ) from exc

    env = os.environ.copy()
    # Estas variables aplican SOLO al camino manual de respaldo.
    env["SERIOUS_PYTHON_APP"] = str(PYTHON_APP_DIR)
    env["SERIOUS_PYTHON_SITE_PACKAGES"] = str(SITE_PACKAGES_DIR)
    env["FLUTTER_ROOT"] = flutter_root
    env["PATH"] = str(Path(flutter_root) / "bin") + os.pathsep + env.get("PATH", "")
    log(f"FLUTTER_ROOT: {flutter_root}")

    step_c_configure(cmake, build_tmp, env)
    step_d_build(cmake, build_tmp, env)

    runner_release = build_tmp / "runner" / "Release"
    if not runner_release.is_dir():
        raise BuildError(
            f"El camino manual no produjo {runner_release}. Revisá los pasos "
            "de configure y build del respaldo."
        )
    return str(runner_release)


def step_d_build_installer(iscc: str) -> Path:
    """(c) Compila el instalador con Inno Setup."""
    stage("(c) ISCC (instalador Inno Setup)")
    if not ISS_FILE.is_file():
        raise BuildError(f"No existe {ISS_FILE}; no hay script de instalador.")
    cmd = [iscc, "/O" + str(DIST_DIR), str(ISS_FILE)]
    run(cmd, cwd=REPO_ROOT)

    setup = DIST_DIR / SETUP_NAME
    if not setup.is_file():
        raise BuildError(
            f"ISCC terminó pero no aparece {setup}. Revisá OutputDir/OutputBaseFilename "
            "en packaging\\g360.iss."
        )
    return setup


# --- Orquestación ------------------------------------------------------------

def main() -> int:
    log("G360 NC Sustentor — build de Windows (bundle + instalador)")
    log(f"Repo: {REPO_ROOT}")

    cmake = find_tool("cmake", CMAKE_FALLBACKS)[0]
    iscc = find_tool("ISCC", ISCC_FALLBACKS)[0]
    flet_argv = find_tool("flet", [], raw_fallback=["uv", "run", "flet"])
    log(f"cmake : {cmake}")
    log(f"ISCC  : {iscc}")
    log(f"flet  : {' '.join(flet_argv)}")

    # Asegurar Flutter SDK (se necesita tanto para flet build como para el
    # respaldo manual). Si falta, falla rápido con un mensaje claro.
    flutter_root = discover_flutter()
    log(f"FLUTTER_ROOT: {flutter_root}")

    # (a) flet build nativo. Si no dejó bundle fresco, usamos el respaldo manual.
    bundle: str | None = None
    try:
        bundle = step_a_flet_build(flet_argv)
    except BuildError as exc:
        log(f"  El camino nativo de flet no dejó bundle fresco: {exc}")
        log("  Invocando camino manual de respaldo (%TEMP%\\opencode\\g360build)...")
        bundle = _manual_fallback(cmake, flutter_root)

    # (b) Copiar el bundle (flet o respaldo) al path canónico del .iss.
    step_b_copy_bundle(Path(bundle))

    # (c) Instalador.
    setup = step_d_build_installer(iscc)

    # Resumen final
    size_bytes = setup.stat().st_size
    file_count = count_files(RUNNER_RELEASE)
    log("")
    log("=== BUILD COMPLETO ===")
    log(f"Instalador   : {setup}")
    log(f"Tamaño       : {human_mb(size_bytes)}")
    log(f"Archivos     : {file_count} empaquetados (umbral mínimo: {BUNDLE_FILE_MIN})")
    if file_count < BUNDLE_FILE_MIN:
        log(f"  AVISO: el bundle tiene solo {file_count} archivos (mínimo esperado: "
            f"{BUNDLE_FILE_MIN}); puede estar vacío o truncado.")
    if size_bytes < 50 * 1024 * 1024:
        log("  AVISO: el instalador pesa menos de 50 MB; verificá que el bundle "
            "esté completo.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BuildError as exc:
        log("")
        log(f"ERROR: {exc}")
        sys.exit(1)
    except KeyboardInterrupt:
        log("Interrumpido por el usuario.")
        sys.exit(130)
