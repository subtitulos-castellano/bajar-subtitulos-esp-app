#!/bin/sh
# .deb y .rpm, al instalar y al desinstalar: que el menú de aplicaciones y los iconos se enteren del cambio.
# Si falta alguna de las dos herramientas, el escritorio lo detecta igualmente al poco.
if command -v update-desktop-database > /dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache > /dev/null 2>&1 && [ -d /usr/share/icons/hicolor ]; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
