# Entry point del build de Windows. La lógica vive en build_windows.py y no acá
# PORQUE esta máquina corre PowerShell en ConstrainedLanguage: ese modo bloquea
# Remove-Item y [System.IO.File]::*, justo lo que un script de build necesita.
# Python corre sin esas restricciones, así que el .ps1 es solo un wrapper.
# Uso: packaging\build_windows.ps1   (desde la raíz del repo)
uv run python packaging\build_windows.py @args
