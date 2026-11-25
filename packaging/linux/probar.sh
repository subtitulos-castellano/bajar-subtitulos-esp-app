#!/usr/bin/env bash
# Pruebas del programa compilado para Linux, en un contenedor de cada distribución (GitHub Actions, linux.yml).
#
#   probar.sh programa CARPETA ORDEN...   autoprueba sin pantalla y que no falte ninguna librería en CARPETA
#   probar.sh appimage ARCHIVO            lo mismo con el AppImage (sin FUSE: se extrae y se ejecuta)
#   probar.sh targz ARCHIVO               lo mismo con el .tar.gz descomprimido
#   probar.sh x11 ORDEN...                abre la ventana en X11 (Xvfb) y se cierra sola
#   probar.sh wayland ORDEN...            abre la ventana en Wayland (weston sin pantalla) y se cierra sola
#   probar.sh menu ORDEN...               pone el menú contextual (en MENU_DATOS) y lo usa
#   probar.sh menu-appimage ARCHIVO       lo mismo con una copia del AppImage; al borrarla, el menú se limpia
#   probar.sh actualizar-paquete DEB|RPM  actualiza el paquete instalado a la revisión 2 (dist/prueba) como la
#                                         app: la vuelve a abrir y conserva la configuración
#   probar.sh actualizar-appimage ARCHIVO lo mismo con una copia del AppImage, que se sustituye por la «nueva»
#   probar.sh usuario                     crea un usuario con la app en el escritorio, anclada en la barra de
#                                         Plasma y oculta a mano del menú de aplicaciones (como hace KDE)
#   probar.sh usuario-intacto             eso sigue igual (al actualizar no se toca)
#   probar.sh desinstalado                no queda nada del .deb o del .rpm (y lo del usuario de prueba se ha limpiado)
set -euo pipefail

ID=bajar-subtitulos-esp
MENU_DATOS="${MENU_DATOS:-/tmp/menu-contextual-prueba}"     # fuera de $TMP: se comprueba también tras desinstalar
USUARIO=prueba-subtitulos                                   # el de «probar.sh usuario»
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

# Lo que el usuario de prueba tiene de la app: «si» si sigue todo, «no» si no queda nada.
usuario_tiene() {
    local casa esperado="$1" hay=""
    casa="$(getent passwd "$USUARIO" | cut -d: -f6)"
    [ -L "$casa/Escritorio/$ID.desktop" ] && hay+=" escritorio"
    grep -q "<Filename>$ID.desktop</Filename>" "$casa/.config/menus/applications-kmenuedit.menu" && hay+=" oculta-del-menú"
    grep -q "^launchers=.*applications:$ID.desktop" "$casa/.config/plasma-org.kde.plasma.desktop-appletsrc" && hay+=" anclada"
    if [ "$esperado" = si ]; then
        [ "$hay" = " escritorio oculta-del-menú anclada" ] || fallo "al usuario le falta algo (tiene:${hay:- nada})"
        echo "El usuario conserva el acceso del escritorio, el anclado y la app oculta del menú"
    else
        [ -z "$hay" ] || fallo "la desinstalación ha dejado al usuario:$hay"
        grep -q 'org.kde.elisa.desktop' "$casa/.config/menus/applications-kmenuedit.menu" || fallo "se ha tocado el resto del menú"
        grep -q '^launchers=preferred://browser$' "$casa/.config/plasma-org.kde.plasma.desktop-appletsrc" \
            || fallo "se ha tocado el resto de la barra"
        echo "Del usuario se han quitado el acceso del escritorio, el anclado y la nota que la ocultaba del menú"
    fi
}

# Configuración en inglés: la actualización no debe cambiarla.
config_ingles() { printf '{"idioma": "en", "version": "0.0.1"}\n' > "$TMP/config-act.json"; }
config_intacta() {
    grep -q '"idioma": "en"' "$TMP/config-act.json" || { cat "$TMP/config-act.json"; fallo "la actualización ha cambiado el idioma"; }
    echo "Configuración conservada"
}

# La app, tras instalar, se vuelve a abrir (con --medir-arranque: dice «ventana visible» y se cierra).
reabierta() {
    echo "$1"
    grep -q 'ventana visible' <<< "$1" || fallo "la app no se ha vuelto a abrir tras actualizarse"
    echo "La app se ha vuelto a abrir tras actualizarse"
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
    targz)
        tar xzf "$1" -C "$TMP"
        [ -x "$TMP/$ID/$ID" ] || fallo "el .tar.gz no trae $ID/$ID"
        autoprueba "$TMP/$ID/$ID"
        librerias "$TMP/$ID" ;;
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
    actualizar-paquete)
        tipo="$1"
        if [ "$tipo" = deb ]; then nuevo="$(readlink -f dist/prueba/*.deb)"; else nuevo="$(readlink -f dist/prueba/*.rpm)"; fi
        config_ingles
        salida="$(QT_QPA_PLATFORM=offscreen timeout 600 $ID --probar-actualizacion "$nuevo" \
                  --config "$TMP/config-act.json" 2>&1)" || { echo "$salida"; fallo "no se ha podido actualizar"; }
        reabierta "$salida"
        if [ "$tipo" = deb ]; then revision="$(dpkg-query -W -f='${Version}' $ID)"; revision="${revision##*-}"
        else revision="$(rpm -q --qf '%{RELEASE}' $ID)"; fi
        [ "$revision" = 2 ] || fallo "sigue instalada la revisión $revision"
        echo "Paquete actualizado a la revisión 2"
        config_intacta ;;
    actualizar-appimage)
        version="$(basename "$1" | sed -E 's/^BajarSubtitulosESP-([0-9.]+)-linux-x86_64\.AppImage$/\1/')"
        mkdir -p "$TMP/apps"
        viejo="$TMP/apps/BajarSubtitulosESP-$version-linux-x86_64.AppImage"
        nuevo="$TMP/apps/BajarSubtitulosESP-99.0.0-linux-x86_64.AppImage"    # como lo deja la descarga, al lado
        cp "$1" "$viejo"; cp "$1" "$nuevo"
        chmod +x "$viejo"; chmod -x "$nuevo"
        config_ingles
        salida="$(APPIMAGE_EXTRACT_AND_RUN=1 QT_QPA_PLATFORM=offscreen timeout 600 "$viejo" \
                  --probar-actualizacion "$nuevo" --config "$TMP/config-act.json" 2>&1)" \
            || { echo "$salida"; fallo "no se ha podido actualizar el AppImage"; }
        reabierta "$salida"
        [ ! -e "$viejo" ] || fallo "queda el AppImage viejo"
        [ -x "$nuevo" ] || fallo "el AppImage nuevo no es ejecutable"
        echo "AppImage sustituido por el nuevo"
        config_intacta ;;
    usuario)
        if ! getent passwd "$USUARIO" > /dev/null; then
            if command -v useradd > /dev/null; then useradd -m -u 1500 "$USUARIO"
            else echo "$USUARIO:x:1500:1500::/home/$USUARIO:/bin/sh" >> /etc/passwd
                 echo "$USUARIO:x:1500:" >> /etc/group; fi
        fi
        casa="$(getent passwd "$USUARIO" | cut -d: -f6)"
        mkdir -p "$casa/.config/menus" "$casa/Escritorio"
        echo 'XDG_DESKTOP_DIR="$HOME/Escritorio"' > "$casa/.config/user-dirs.dirs"
        ln -sfn "/usr/share/applications/$ID.desktop" "$casa/Escritorio/$ID.desktop"
        printf 'launchers=applications:%s.desktop,preferred://browser\n' "$ID" \
            > "$casa/.config/plasma-org.kde.plasma.desktop-appletsrc"
        cat > "$casa/.config/menus/applications-kmenuedit.menu" << FIN
<Menu>
 <Menu>
  <Name>Multimedia</Name>
  <Layout>
   <Filename>org.kde.elisa.desktop</Filename>
  </Layout>
  <Exclude>
   <Filename>$ID.desktop</Filename>
  </Exclude>
 </Menu>
 <Menu>
  <Name>.hidden</Name>
  <Include>
   <Filename>$ID.desktop</Filename>
  </Include>
 </Menu>
</Menu>
FIN
        chown -R "$(id -u "$USUARIO"):$(id -g "$USUARIO")" "$casa"
        usuario_tiene si ;;
    usuario-intacto)
        usuario_tiene si ;;
    desinstalado)
        if [ -d "$MENU_DATOS" ]; then menu_limpio "$MENU_DATOS"; fi
        if getent passwd "$USUARIO" > /dev/null; then usuario_tiene no; fi
        quedan=""
        for r in "/opt/$ID" "/usr/bin/$ID" "/usr/share/applications/$ID.desktop"; do
            if [ -e "$r" ] || [ -L "$r" ]; then quedan+=" $r"; fi
        done
        quedan+="$(find /usr/share/icons/hicolor -name "$ID.*" -printf ' %p' 2> /dev/null || true)"
        [ -z "$quedan" ] || fallo "la desinstalación ha dejado:$quedan"
        echo "Desinstalación limpia" ;;
    *)
        sed -n '2,15p' "$0"; exit 1 ;;
esac
