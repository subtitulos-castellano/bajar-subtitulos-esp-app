#!/usr/bin/env bash
# Pruebas del programa compilado para Linux, en un contenedor de cada distribución (GitHub Actions, linux.yml).
#
#   probar.sh programa CARPETA ORDEN...   autoprueba sin pantalla y que no falte ninguna librería en CARPETA
#   probar.sh appimage ARCHIVO            lo mismo con el AppImage (sin FUSE: se extrae y se ejecuta)
#   probar.sh x11 ORDEN...                abre la ventana en X11 (Xvfb) y se cierra sola
#   probar.sh wayland ORDEN...            abre la ventana en Wayland (weston sin pantalla) y se cierra sola
#   probar.sh desinstalado                no queda nada del .deb o del .rpm
set -euo pipefail

ID=bajar-subtitulos-esp
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fallo() { echo "FALLO: $*" >&2; exit 1; }

autoprueba() {
    QT_QPA_PLATFORM=offscreen timeout 180 "$@" --autoprueba "$TMP/informe.txt" || {
        cat "$TMP/informe.txt" 2> /dev/null; fallo "autoprueba de $*"; }
    cat "$TMP/informe.txt"
}

# Cada archivo ELF de la carpeta, con sus librerías resueltas como al ejecutarse (el programa arranca con
# LD_LIBRARY_PATH en su carpeta _internal): las del sistema las pone la distribución (dependencias del paquete).
librerias() {
    local carpeta="$1" faltan=""
    while IFS= read -r -d '' f; do
        [ "$(head -c 4 "$f" | od -An -c | tr -d ' ')" = '177ELF' ] || continue
        local r
        r="$(LD_LIBRARY_PATH="$carpeta/_internal" ldd "$f" 2> /dev/null | grep 'not found' || true)"
        [ -z "$r" ] || faltan+="${f#"$carpeta"/}:"$'\n'"$r"$'\n'
    done < <(find "$carpeta" -type f -print0)
    [ -z "$faltan" ] || { echo "$faltan"; fallo "faltan librerías del sistema"; }
    echo "Librerías: no falta ninguna"
}

ventana() {      # $1: descripción; luego, la orden (con DISPLAY o WAYLAND_DISPLAY ya puestos)
    local que="$1"; shift
    local salida
    salida="$(timeout 90 "$@" --medir-arranque --config "$TMP/config.json" 2>&1)" || true
    echo "$salida"
    grep -q 'ventana visible' <<< "$salida" || fallo "no se ha abierto la ventana ($que)"
    echo "Ventana correcta ($que)"
}

orden="$1"; shift
case "$orden" in
    programa)
        carpeta="$1"; shift
        autoprueba "$@"
        librerias "$carpeta" ;;
    appimage)
        archivo="$(readlink -f "$1")"
        chmod +x "$archivo"
        APPIMAGE_EXTRACT_AND_RUN=1 autoprueba "$archivo"
        (cd "$TMP" && "$archivo" --appimage-extract > /dev/null)
        librerias "$TMP/squashfs-root/usr/lib/$ID" ;;
    x11)
        Xvfb :99 -screen 0 1280x800x24 -nolisten tcp > "$TMP/xvfb.log" 2>&1 &
        servidor=$!
        sleep 3
        DISPLAY=:99 QT_QPA_PLATFORM=xcb ventana X11 "$@"
        kill "$servidor" ;;
    wayland)
        export XDG_RUNTIME_DIR="$TMP/run"
        mkdir -m 700 "$XDG_RUNTIME_DIR"
        weston --backend=headless --socket=wayland-prueba --idle-time=0 > "$TMP/weston.log" 2>&1 &
        servidor=$!
        for _ in $(seq 30); do [ -S "$XDG_RUNTIME_DIR/wayland-prueba" ] && break; sleep 1; done
        [ -S "$XDG_RUNTIME_DIR/wayland-prueba" ] || { cat "$TMP/weston.log"; fallo "weston no ha arrancado"; }
        WAYLAND_DISPLAY=wayland-prueba QT_QPA_PLATFORM=wayland ventana Wayland "$@"
        kill "$servidor" ;;
    desinstalado)
        quedan=""
        for r in "/opt/$ID" "/usr/bin/$ID" "/usr/share/applications/$ID.desktop"; do
            if [ -e "$r" ] || [ -L "$r" ]; then quedan+=" $r"; fi
        done
        quedan+="$(find /usr/share/icons/hicolor -name "$ID.*" -printf ' %p' 2> /dev/null || true)"
        [ -z "$quedan" ] || fallo "la desinstalación ha dejado:$quedan"
        echo "Desinstalación limpia" ;;
    *)
        sed -n '2,9p' "$0"; exit 1 ;;
esac
