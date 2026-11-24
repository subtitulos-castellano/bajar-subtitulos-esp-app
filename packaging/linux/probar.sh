#!/usr/bin/env bash
# Pruebas del programa compilado para Linux, en un contenedor de cada distribución (GitHub Actions, linux.yml).
#
#   probar.sh programa CARPETA ORDEN...   autoprueba sin pantalla y que no falte ninguna librería en CARPETA
#   probar.sh appimage ARCHIVO            lo mismo con el AppImage (sin FUSE: se extrae y se ejecuta)
#   probar.sh x11 ORDEN...                abre la ventana en X11 (Xvfb) y se cierra sola
#   probar.sh wayland ORDEN...            abre la ventana en Wayland (weston sin pantalla) y se cierra sola
#   probar.sh menu ORDEN...               pone el menú contextual (en MENU_DATOS) y lo usa
#   probar.sh menu-appimage ARCHIVO       lo mismo con una copia del AppImage; al borrarla, el menú se limpia
#   probar.sh desinstalado                no queda nada del .deb o del .rpm (y el menú se ha limpiado)
set -euo pipefail

ID=bajar-subtitulos-esp
MENU_DATOS="${MENU_DATOS:-/tmp/menu-contextual-prueba}"     # fuera de $TMP: se comprueba también tras desinstalar
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

# Pone el menú contextual con la orden dada (como el instalador de Windows) en la carpeta de datos $1 y
# comprueba sus archivos y que el lanzador abre el programa.
menu() {
    local datos="$1"; shift
    rm -rf "$datos"
    XDG_DATA_HOME="$datos" QT_QPA_PLATFORM=offscreen timeout 60 "$@" --menu-contextual-instalar \
        --config "$TMP/config-menu.json" || fallo "no se ha podido poner el menú contextual"
    for f in kio/servicemenus/$ID-carpetas.desktop kio/servicemenus/$ID-videos.desktop \
             nemo/actions/$ID-1.nemo_action "nautilus/scripts/Bajar subtítulos" $ID/menu-contextual; do
        [ -f "$datos/$f" ] || fallo "falta $f"
    done
    [ -x "$datos/kio/servicemenus/$ID-carpetas.desktop" ] || fallo "Dolphin necesita el menú ejecutable"
    grep -m1 '^ *exec ' "$datos/$ID/menu-contextual"
    QT_QPA_PLATFORM=offscreen timeout 180 "$datos/$ID/menu-contextual" --autoprueba "$TMP/informe-menu.txt" \
        || fallo "el menú no abre el programa"
    echo "Menú contextual correcto"
}

# Sin el programa, el primer uso del menú lo quita entero.
menu_limpio() {
    local datos="$1"
    [ -x "$datos/$ID/menu-contextual" ] || fallo "no estaba el menú contextual"
    "$datos/$ID/menu-contextual" --menu-carpeta /tmp || fallo "el lanzador ha fallado sin el programa"
    quedan="$(find "$datos" -type f -printf ' %P')"
    [ -z "$quedan" ] || fallo "el menú contextual no se ha limpiado:$quedan"
    echo "Menú contextual limpio sin el programa"
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
    menu)
        menu "$MENU_DATOS" "$@" ;;
    menu-appimage)
        copia="$TMP/Mis programas/BajarSubtitulosESP.AppImage"
        mkdir -p "$(dirname "$copia")"
        cp "$1" "$copia"
        chmod +x "$copia"
        APPIMAGE_EXTRACT_AND_RUN=1 menu "$TMP/datos-appimage" "$copia"
        grep -qF "'$copia'" "$TMP/datos-appimage/$ID/menu-contextual" || fallo "el menú no apunta al AppImage"
        rm "$copia"
        menu_limpio "$TMP/datos-appimage" ;;
    desinstalado)
        if [ -d "$MENU_DATOS" ]; then menu_limpio "$MENU_DATOS"; fi
        quedan=""
        for r in "/opt/$ID" "/usr/bin/$ID" "/usr/share/applications/$ID.desktop"; do
            if [ -e "$r" ] || [ -L "$r" ]; then quedan+=" $r"; fi
        done
        quedan+="$(find /usr/share/icons/hicolor -name "$ID.*" -printf ' %p' 2> /dev/null || true)"
        [ -z "$quedan" ] || fallo "la desinstalación ha dejado:$quedan"
        echo "Desinstalación limpia" ;;
    *)
        sed -n '2,11p' "$0"; exit 1 ;;
esac
