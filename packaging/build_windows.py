"""Build reproducible de Windows: bundle Flet + instalador Inno Setup.

Replica exactamente el pipeline manual que ya se verificó en esta máquina
(pasos a-f del relevamiento). No inventa pasos nuevos.

¿Por qué no ejecutamos `flet build windows --release` de punta a punta?
Porque en esta máquina el paso *generate* de CMake falla con ~103 errores
`Cannot open file for write` cuando el build dir vive dentro de `Documents`
(o de `C:\\Users\\<user>`): esos directorios no admiten ciertas escrituras.
Lo que sí hace `flet build` antes de morir es dejar listos los dos staging
dirs que el build nativo necesita (`build\\python-app` y `build\\site-packages`,
salida del comando `package` de serious_python). Entonces:

  a. `flet build windows --release`  -> se TOLERA su fallo, solo para poblar staging
  b. parchear `build\\flutter\\windows\\CMakeLists.txt` con
     `set(CMAKE_DISABLE_FIND_PACKAGE_JNI TRUE)` (jni es Android-only y su
     find_package(JNI) rompe Windows)
  c-d. configurar y compilar CMake apuntando a %TEMP% (fuera de Documents),
     exportando SERIOUS_PYTHON_APP / SERIOUS_PYTHON_SITE_PACKAGES para que el
     CMake de serious_python copie el runtime Python al bundle. Esas variables
     se leen en configure time, por eso van en el entorno del paso (c).
  e. copiar el runner Release generado de vuelta a `build\\windows\\x64\\runner\\Release`
     (es lo que espera `[Files]` de packaging\\g360.iss)
  f. compilar el instalador con ISCC

El script es idempotente y no destructivo: nunca borra `build\\python-app` ni
`build\\site-packages` (son caros de regenerar); solo limpia el build dir
temporal de CMake antes de configurar.
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
EXPECTED_FILE_COUNT = 5956  # verificado en el pipeline manual (paso f)

# La raíz del repo es el padre de packaging/. El usuario corre desde la raíz,
# pero resolvemos por __file__ para no depender del cwd.
REPO_ROOT = Path(__file__).resolve().parent.parent

BUILD_DIR = REPO_ROOT / "build"
DIST_DIR = REPO_ROOT / "dist"
ISS_FILE = REPO_ROOT / "packaging" / "g360.iss"
FLUTTER_DIR = BUILD_DIR / "flutter"
FLUTTER_CMAKE = FLUTTER_DIR / "windows" / "CMakeLists.txt"
PYTHON_APP_DIR = BUILD_DIR / "python-app"
SITE_PACKAGES_DIR = BUILD_DIR / "site-packages"
RUNNER_RELEASE = BUILD_DIR / "windows" / "x64" / "runner" / "Release"

# CMake genera bien solo fuera de Documents; %TEMP%\opencode es la ruta que ya
# se verificó como escribible en esta máquina.
CMAKELISTS = "set(CMAKE_DISABLE_FIND_PACKAGE_JNI TRUE)"
_CMAKELISTS_PRECHECK = "CMAKE_DISABLE_FIND_PACKAGE_JNI"

# Rutas conocidas como fallback. No son la única opción: primero probamos PATH.
CMAKE_FALLBACKS = [
    r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe",
]
ISCC_FALLBACKS = [
    r"C:\Program Files\Inno Setup 7\ISCC.exe",
]
FLUTTER_FALLBACKS = [
    r"C:\Users\ccusi\flutter\3.44.8",
    r"C:\flutter",
    r"C:\src\flutter",
]


class BuildError(RuntimeError):
    """Fallo de un paso del pipeline; el mensaje explica cómo seguir."""


# Firmas del fallo *conocido* del paso generate de CMake cuando el build dir
# vive dentro de Documents. Solo toleramos el fallo del paso (a) si aparece
# alguna de estas en la salida de `flet build`.
_KNOWN_GENERATE_FAILURES = (
    "Cannot open file for write",
    "CMake Generate step failed",
)
_KNOWN_PERMISSION_TANDEM = ("Permission denied", "CMake Error")


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
        # Si el fallback invoca otro ejecutable (`uv`), confirmamos que exista:
        # así el error es un BuildError claro y no un FileNotFoundError crudo.
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

    Capturamos stdout+stderr juntos: el paso (a) necesita inspeccionar la
    salida de `flet` para distinguir el fallo conocido de CMake de cualquier
    otro. Igual la volcamos al log para que el diagnóstico quede disponible.

    Si `tolerate_failure` es False y el RC != 0, aborta con BuildError.
    Devuelve (returncode, salida_combinada).
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


def known_generate_failure(output: str) -> bool:
    """True si `output` contiene la firma del fallo conocido de CMake generate.

    Es la condición (2) de la tolerancia del paso (a): sin esta firma, un
    RC != 0 de `flet build` NO se tolera (pudo fallar por sintaxis en main.py,
    dependencia faltante, error de uv, etc.).
    """
    if any(sig in output for sig in _KNOWN_GENERATE_FAILURES):
        return True
    return all(sig in output for sig in _KNOWN_PERMISSION_TANDEM)


def _newest_mtime(root: Path) -> float | None:
    """mtime más reciente entre los archivos de `root` (None si no hay)."""
    newest: float | None = None
    for p in root.rglob("*"):
        if p.is_file():
            m = p.stat().st_mtime
            if newest is None or m > newest:
                newest = m
    return newest


def validate_tolerated_staging(
    started_at: float, output: str, *, tolerance_s: float = 2.0
) -> None:
    """Valida el fallo tolerado del paso (a). Ver arquitecto: condición (2)+(3).

    Se acepta el fallo de `flet build` SOLO si:
      (2) la salida trae la firma del fallo conocido de CMake generate, y
      (3) el staging es fresco: `main.pyc` y el archivo más nuevo de
          site-packages tienen mtime >= started_at (con tolerancia por
          redondeo de filesystem).
    En cualquier otro caso aborta con un BuildError que distingue la causa:
    fallo distinto al conocido vs. staging de una corrida anterior.
    """
    if not known_generate_failure(output):
        raise BuildError(
            "flet build falló por una razón distinta a la conocida (no aparece "
            "'Cannot open file for write' ni 'CMake Generate step failed' en la "
            "salida). Revisá el log de flet más arriba; el pipeline se detiene acá."
        )

    main_pyc = PYTHON_APP_DIR / "main.pyc"
    if not main_pyc.is_file():
        raise BuildError(
            f"flet build falló con la firma conocida pero no existe {main_pyc}: "
            "el staging no quedó poblado. Abortando."
        )
    if not SITE_PACKAGES_DIR.is_dir():
        raise BuildError(
            f"flet build falló con la firma conocida pero {SITE_PACKAGES_DIR} "
            "no existe. Abortando."
        )

    threshold = started_at - tolerance_s
    main_mtime = main_pyc.stat().st_mtime
    site_newest = _newest_mtime(SITE_PACKAGES_DIR)
    if main_mtime < threshold or site_newest is None or site_newest < threshold:
        raise BuildError(
            "flet build falló con la firma conocida pero el staging es de una "
            f"corrida anterior (mtime main.pyc={main_mtime:.0f}, "
            f"site-packages={site_newest if site_newest is None else round(site_newest)}; "
            f"inicio del paso={started_at:.0f}). Empaquetar esto usaría código "
            "viejo. Corré de nuevo desde una ruta escribible o limpiá el staging."
        )


# --- Descubrimiento de herramientas ------------------------------------------

def discover_flutter() -> str:
    """Ubica el Flutter SDK. No está en PATH: lo leemos del package_config.json
    que flet dejó en build\\flutter\\.dart_tool, con fallback a rutas conocidas.
    """
    if shutil.which("flutter"):
        return shutil.which("flutter")  # type: ignore[return-value]

    pkg_config = FLUTTER_DIR / ".dart_tool" / "package_config.json"
    if pkg_config.is_file():
        try:
            data = json.loads(pkg_config.read_text(encoding="utf-8"))
            root = data.get("flutterRoot")
            if root:
                # flutterRoot viene como file:/// URI.
                path = root.replace("file:///", "").replace("/", os.sep)
                if Path(path).is_dir():
                    return path
        except (json.JSONDecodeError, OSError) as exc:
            log(f"  Aviso: no se pudo leer {pkg_config}: {exc}")

    for candidate in FLUTTER_FALLBACKS:
        if Path(candidate).is_dir():
            return candidate

    raise BuildError(
        "No se encontró el Flutter SDK. Se intentó PATH, "
        f"{pkg_config} (campo flutterRoot) y {FLUTTER_FALLBACKS}. "
        "Corré `flet build` una vez desde una ruta escribible o instalá Flutter."
    )


# --- Pasos del pipeline ------------------------------------------------------

def step_a_stage_python(flet_argv: list[str]) -> None:
    """(a) `flet build windows --release` para poblar los staging dirs.

    Este es el ÚNICO paso tolerado como fallo, y solo porque deja
    `build\\python-app` y `build\\site-packages` listos antes de romper en el
    paso *generate* de CMake. La tolerancia se valida con
    `validate_tolerated_staging`: exige la firma del fallo conocido Y staging
    fresco, para no empaquetar código viejo si `flet` murió por otra razón.
    """
    # started_at ANTES de lanzar flet: es el umbral de frescura del staging.
    started_at = stage("(a) flet build windows --release (poblar staging)")
    # flet_argv viene de find_tool: puede ser ["flet.EXE"] o ["uv","run","flet"].
    cmd = [*flet_argv, "build", "windows", "--release"]
    rc, output = run(cmd, cwd=REPO_ROOT, tolerate_failure=True, label="flet build")
    if rc == 0:
        log("  flet build terminó con RC=0; staging generado en esta corrida.")
        return

    log(f"  flet build terminó con RC={rc}; tolerancia condicionada. Validando...")
    validate_tolerated_staging(started_at, output)
    log(f"  Staging OK: python-app ({count_files(PYTHON_APP_DIR)} archivos), "
        f"site-packages ({count_files(SITE_PACKAGES_DIR)} archivos).")


def step_b_patch_cmakelists() -> None:
    """(b) Neutraliza el plugin jni (Android-only) que rompe el build Windows.

    Idempotente: si `CMAKE_DISABLE_FIND_PACKAGE_JNI` ya está, no lo duplica.
    Se inserta justo después de la línea `project(...)`.
    """
    stage("(b) parchear CMakeLists de Flutter (jni Android-only)")
    if not FLUTTER_CMAKE.is_file():
        raise BuildError(
            f"No existe {FLUTTER_CMAKE}. Corré primero el paso (a) para que "
            "flet genere el proyecto Flutter."
        )

    text = FLUTTER_CMAKE.read_text(encoding="utf-8")
    if _CMAKELISTS_PRECHECK in text:
        log("  Ya estaba parcheado; no se modifica (idempotente).")
        return

    lines = text.splitlines(keepends=True)
    out: list[str] = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted and line.lstrip().startswith("project("):
            out.append("\n# jni es Android-only; su find_package(JNI) rompe el "
                       "build de Windows\n")
            out.append(f"{CMAKELISTS}\n")
            inserted = True
    if not inserted:
        raise BuildError(
            f"No se encontró la línea `project(...)` en {FLUTTER_CMAKE}; "
            "no se puede insertar el parche de forma segura. Revisá el archivo."
        )
    FLUTTER_CMAKE.write_text("".join(out), encoding="utf-8")
    log(f"  Parche insertado en {FLUTTER_CMAKE}.")


def step_c_configure(cmake: str, build_tmp: Path, env: dict) -> None:
    """(c) Configura CMake en %TEMP% (fuera de Documents)."""
    stage("(c) cmake configure en %TEMP%")
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
    """(d) Compila e instala el runner."""
    stage("(d) cmake build --target INSTALL")
    cmd = [cmake, "--build", str(build_tmp), "--config", "Release", "--target", "INSTALL"]
    run(cmd, cwd=REPO_ROOT, env=env)


def step_e_copy_runner(build_tmp: Path) -> None:
    """(e) Copia el runner Release generado al path que espera el .iss.

    El destino debe quedar EXACTAMENTE igual al origen. Por eso lo limpiamos
    antes de copiar: `copytree(dirs_exist_ok=True)` no borra archivos que
    estaban de una corrida previa y ya no se generan, y el `[Files]` del .iss
    usa `recursesubdirs`, así que los empaquetaría como huérfanos.
    RUNNER_RELEASE es regenerable y está en .gitignore.
    """
    stage("(e) copiar runner Release a build\\windows\\x64\\runner\\Release")
    src = build_tmp / "runner" / "Release"
    if not src.is_dir():
        raise BuildError(
            f"El build no produjo {src}. Revisá los pasos (c) y (d): la "
            "configuración o la compilación no completaron."
        )
    if RUNNER_RELEASE.exists():
        log(f"  Limpiando destino {RUNNER_RELEASE} (evita huérfanos).")
        shutil.rmtree(RUNNER_RELEASE)
    RUNNER_RELEASE.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    shutil.copytree(src, RUNNER_RELEASE)

    src_count = count_files(src)
    copied = count_files(RUNNER_RELEASE)
    log(f"  {copied} archivos en {RUNNER_RELEASE} ({time.monotonic() - started:.1f} s)")
    if copied == 0:
        raise BuildError(f"La copia dejó {RUNNER_RELEASE} vacío; abortando.")
    if copied != src_count:
        raise BuildError(
            f"El destino {RUNNER_RELEASE} tiene {copied} archivos pero el origen "
            f"{src} tiene {src_count}. La copia no quedó idéntica; abortando para "
            "no empaquetar un bundle incompleto o con huérfanos."
        )


def step_f_build_installer(iscc: str) -> Path:
    """(f) Compila el instalador con Inno Setup."""
    stage("(f) ISCC (instalador Inno Setup)")
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

    # find_tool devuelve argv (lista). cmake/ISCC siempre resuelven a un único
    # ejecutable de PATH/rutas conocidas: tomamos su argv[0] como ruta.
    cmake = find_tool("cmake", CMAKE_FALLBACKS)[0]
    iscc = find_tool("ISCC", ISCC_FALLBACKS)[0]
    # A2: `flet` puede no estar en PATH; fallback a `uv run flet` (el repo usa
    # uv). Guardamos el argv completo para poder anteponerlo al subcomando.
    flet_argv = find_tool("flet", [], raw_fallback=["uv", "run", "flet"])
    log(f"cmake : {cmake}")
    log(f"ISCC  : {iscc}")
    log(f"flet  : {' '.join(flet_argv)}")

    # (a) Staging Python
    step_a_stage_python(flet_argv)

    # (b) Parche jni
    step_b_patch_cmakelists()

    # (c-d) Configurar y compilar en %TEMP%, exportando las variables que
    # serious_python lee en configure time para copiar el runtime al bundle.
    tmp_root = Path(os.environ.get("TEMP", r"C:\Windows\Temp")) / "opencode"
    build_tmp = tmp_root / "g360build"
    tmp_root.mkdir(parents=True, exist_ok=True)
    if build_tmp.exists():
        # Solo limpiamos el build temporal: es regenerable. Los staging dirs de
        # Python NO se tocan (son caros de regenerar).
        log(f"Limpiando build temporal {build_tmp}")
        shutil.rmtree(build_tmp, ignore_errors=True)

    env = os.environ.copy()
    env["SERIOUS_PYTHON_APP"] = str(PYTHON_APP_DIR)
    env["SERIOUS_PYTHON_SITE_PACKAGES"] = str(SITE_PACKAGES_DIR)
    # C2: el CMake de serious_python/Flutter depende de FLUTTER_ROOT. Si no está
    # en el entorno, `cmake configure` muere con un error genérico. Lo
    # descubrimos y lo exportamos (más su \bin al PATH) para el subproceso.
    flutter_root = discover_flutter()
    env["FLUTTER_ROOT"] = flutter_root
    env["PATH"] = str(Path(flutter_root) / "bin") + os.pathsep + env.get("PATH", "")
    log(f"FLUTTER_ROOT: {flutter_root}")

    step_c_configure(cmake, build_tmp, env)
    step_d_build(cmake, build_tmp, env)

    # (e) Copiar runner al path del .iss
    step_e_copy_runner(build_tmp)

    # (f) Instalador
    setup = step_f_build_installer(iscc)

    # Resumen final
    size_bytes = setup.stat().st_size
    file_count = count_files(RUNNER_RELEASE)
    log("")
    log("=== BUILD COMPLETO ===")
    log(f"Instalador   : {setup}")
    log(f"Tamaño       : {human_mb(size_bytes)}")
    log(f"Archivos     : {file_count} empaquetados (esperado: {EXPECTED_FILE_COUNT})")
    if file_count != EXPECTED_FILE_COUNT:
        log(f"  AVISO: el conteo difiere del esperado ({EXPECTED_FILE_COUNT}). "
            "El instalador se generó, pero revisá si cambió el bundle.")
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
