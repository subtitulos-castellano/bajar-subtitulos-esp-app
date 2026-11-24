#!/usr/bin/env bash
# Desarrollo en Linux: la app desde el código, con un entorno virtual en .venv/.
#
#   scripts/linux.sh entorno            crea .venv e instala las dependencias (requirements-app.txt)
#   scripts/linux.sh app [args...]      abre la app (p. ej. --idioma en, --tema oscuro, --demo)
#   scripts/linux.sh pruebas            pasa las pruebas automáticas (sin ventanas)
#   scripts/linux.sh python [args...]   ejecuta el Python de .venv
#   scripts/linux.sh info               sistema, escritorio, Python, Qt y llavero (para informar de fallos)
#
# Variable: PYTHON (el Python con el que crear .venv; por defecto, el más nuevo entre 3.10 y 3.14).
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$RAIZ/.venv"
PY_VENV="$VENV/bin/python"

elegir_python() {
    if [ -n "${PYTHON:-}" ]; then echo "$PYTHON"; return; fi
    for v in 3.14 3.13 3.12 3.11 3.10; do
        if command -v "python$v" > /dev/null; then echo "python$v"; return; fi
    done
    echo python3
}

comprobar_entorno() {
    if [ ! -x "$PY_VENV" ]; then
        echo "Falta el entorno: ejecuta primero  scripts/linux.sh entorno" >&2
        exit 1
    fi
}

orden="${1:-}"; shift || true
case "$orden" in
    entorno)
        PY="$(elegir_python)"
        if ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2> /dev/null; then
            echo "Hace falta Python 3.10 o posterior (encontrado: $("$PY" --version 2>&1 || echo ninguno))." >&2
            exit 1
        fi
        if [ ! -x "$PY_VENV" ]; then
            "$PY" -m venv "$VENV" || {
                echo "No se ha podido crear el entorno. En Ubuntu/Debian: sudo apt install python3-venv" >&2
                exit 1
            }
        fi
        "$PY_VENV" -m pip install --upgrade pip -q
        "$PY_VENV" -m pip install -r "$RAIZ/requirements-app.txt" -q
        "$PY_VENV" -c "import PySide6, subliminal; print('Listo: PySide6', PySide6.__version__, '| subliminal', subliminal.__version__)" ;;
    app)
        comprobar_entorno
        cd "$RAIZ" && exec "$PY_VENV" -I app/main.py "$@" ;;
    pruebas)
        comprobar_entorno
        cd "$RAIZ" && QT_QPA_PLATFORM=offscreen exec "$PY_VENV" -I -m unittest discover -s tests ;;
    python)
        comprobar_entorno
        cd "$RAIZ" && exec "$PY_VENV" "$@" ;;
    info)
        comprobar_entorno
        echo "Sistema:    $(. /etc/os-release 2> /dev/null && echo "$PRETTY_NAME") · $(uname -r)"
        echo "Escritorio: ${XDG_CURRENT_DESKTOP:-?} · sesión ${XDG_SESSION_TYPE:-?}"
        cd "$RAIZ" && "$PY_VENV" -I -c "
import sys; sys.path.insert(0, '.')
import PySide6, keyring
from app import __version__
print(f'App:        {__version__} · Python {sys.version.split()[0]} · PySide6 {PySide6.__version__}')
print(f'Llavero:    {type(keyring.get_keyring()).__module__}')
from PySide6.QtGui import QGuiApplication
qt = QGuiApplication([])
pantallas = ', '.join(f'{p.name()} {p.size().width()}x{p.size().height()} al {round(p.devicePixelRatio() * 100)} %'
                      for p in qt.screens())
print(f'Pantalla:   Qt {qt.platformName()} · {pantallas}')
" ;;
    *)
        sed -n '2,10p' "$0"; exit 1 ;;
esac
