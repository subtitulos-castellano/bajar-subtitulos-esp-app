#!/usr/bin/env bash
# Desarrollo desde WSL: copia el código a una carpeta de Windows y lo ejecuta con el Python
# de Windows (la app es de Windows y PyInstaller no compila para Windows desde Linux).
#
#   scripts/windows.sh entorno            crea el venv de Windows e instala las dependencias
#   scripts/windows.sh app [args...]      abre la app
#   scripts/windows.sh python [args...]   ejecuta el Python del venv de Windows
#   scripts/windows.sh sync               solo copia el código
#
# Variables: WIN_DEV (carpeta de Windows, por defecto C:\Users\<usuario>\dev\bajar-subtitulos-esp-app)
#            WIN_PYTHON (Python de Windows para crear el venv, por defecto py.exe -3.14)
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USUARIO_WIN="$(cmd.exe /c 'echo %USERNAME%' 2>/dev/null | tr -d '\r')"
WIN_DEV="${WIN_DEV:-C:\\Users\\$USUARIO_WIN\\dev\\bajar-subtitulos-esp-app}"
DEST="$(wslpath -u "$WIN_DEV")"
PY_VENV="$DEST/.venv/Scripts/python.exe"

sync() {
    mkdir -p "$DEST"
    rsync -a --delete --exclude .git --exclude .venv --exclude __pycache__ \
        --exclude build --exclude dist "$RAIZ/" "$DEST/"
}

orden="${1:-}"; shift || true
case "$orden" in
    sync)
        sync ;;
    entorno)
        sync
        if [ ! -x "$PY_VENV" ]; then
            ${WIN_PYTHON:-py.exe -3.14} -m venv "$WIN_DEV\\.venv"
        fi
        (cd "$DEST" && "$PY_VENV" -m pip install --upgrade pip -q && "$PY_VENV" -m pip install -r requirements-app.txt -q)
        "$PY_VENV" -c "import PySide6, subliminal; print('PySide6', PySide6.__version__, '| subliminal', subliminal.__version__)" ;;
    app)
        sync
        (cd "$DEST" && "$PY_VENV" -I app/main.py "$@") ;;
    python)
        sync
        (cd "$DEST" && "$PY_VENV" "$@") ;;
    *)
        sed -n '2,12p' "$0"; exit 1 ;;
esac
