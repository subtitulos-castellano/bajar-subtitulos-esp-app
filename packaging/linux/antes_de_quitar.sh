#!/bin/sh
# .deb y .rpm, antes de quitar los archivos: solo al desinstalar del todo, no al actualizar (rpm pasa 0
# al desinstalar y 1 al actualizar; dpkg, «remove» o «upgrade»).
#
# La app ejecuta «--desinstalar» como cada usuario del equipo: quita su menú contextual, sus accesos del
# escritorio, el anclado en la barra de tareas y la nota que la oculta del menú de aplicaciones (si no, al
# reinstalarla no volvería a «Todas las aplicaciones»). Solo toca lo de la app (app/plataforma/accesos_linux.py).
# Nunca hace fallar la desinstalación.
case "$1" in
    0|remove) ;;
    *) exit 0 ;;
esac
PROG=/opt/bajar-subtitulos-esp/bajar-subtitulos-esp
[ -x "$PROG" ] || exit 0

uid_min=$(awk '$1 == "UID_MIN" { print $2 }' /etc/login.defs 2> /dev/null)
case "$uid_min" in ''|*[!0-9]*) uid_min=1000 ;; esac

getent passwd | while IFS=: read -r usuario _ uid _ _ casa _; do
    case "$uid" in ''|*[!0-9]*) continue ;; esac
    [ "$uid" -ge "$uid_min" ] && [ "$uid" -lt 60000 ] && [ -d "$casa" ] || continue
    # Con su sesión abierta, su D-Bus (para pedirle a Plasma que quite el anclado).
    run=""
    [ -S "/run/user/$uid/bus" ] && run="/run/user/$uid"
    set -- env -i PATH=/usr/local/bin:/usr/bin:/bin "HOME=$casa" "USER=$usuario" "LOGNAME=$usuario" LANG=C.UTF-8 \
        "XDG_RUNTIME_DIR=$run" "DBUS_SESSION_BUS_ADDRESS=${run:+unix:path=$run/bus}" \
        timeout 60 "$PROG" --desinstalar
    if command -v runuser > /dev/null 2>&1; then
        runuser -u "$usuario" -- "$@" > /dev/null 2>&1 < /dev/null || true
    elif command -v setpriv > /dev/null 2>&1; then
        setpriv --reuid="$uid" --regid="$(id -g "$usuario")" --init-groups "$@" > /dev/null 2>&1 < /dev/null || true
    fi
done
exit 0
