#!/bin/sh
# .deb y .rpm, antes de quitar los archivos: solo al desinstalar del todo, no al actualizar (rpm pasa 0
# al desinstalar y 1 al actualizar; dpkg, «remove» o «upgrade»).
#
# Para cada usuario del equipo, la app (como root) pasa a ser ese usuario y ejecuta «--desinstalar»: quita
# su menú contextual, sus accesos del escritorio, el anclado en la barra de tareas y la nota que la oculta
# del menú de aplicaciones (si no, al reinstalarla no volvería a «Todas las aplicaciones»). Solo toca lo de
# la app (app/plataforma/accesos_linux.py). No usa runuser: no lo traen todas las distribuciones.
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
    env -i PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 \
        timeout 60 "$PROG" --desinstalar --usuario "$usuario" > /dev/null 2>&1 < /dev/null || true
done
exit 0
