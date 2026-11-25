# Bajar Subtítulos ESP @VERSION@: cómo instalar y desinstalar

*English below.*

Descarga solo el archivo de tu sistema. Windows y Linux tienen el mismo número de versión.

## Windows

| Archivo | Qué es | Cómo se instala |
|---|---|---|
| BajarSubtitulosESP-@VERSION@-instalador.exe | Instalador (recomendado) | Ábrelo con doble clic. No pide permisos de administrador. |
| BajarSubtitulosESP-@VERSION@-portable.zip | Portable, sin instalar | Descomprímelo donde quieras y abre BajarSubtitulosESP.exe. |

El programa no está firmado digitalmente. Si sale «Windows protegió su PC», pulsa *Más información ›
Ejecutar de todas formas*.

## Linux

Para PC de 64 bits (x86_64) con una distribución de 2022 o posterior.

| Si usas… | Descarga | Orden |
|---|---|---|
| Ubuntu 22.04+, Debian 12+, Linux Mint 21+ y derivadas | BajarSubtitulosESP-@VERSION@-amd64.deb | A |
| Fedora, AlmaLinux, Rocky Linux o RHEL 9+ | BajarSubtitulosESP-@VERSION@-x86_64.rpm | B |
| openSUSE Tumbleweed | BajarSubtitulosESP-@VERSION@-x86_64.rpm | C |
| Cualquier otra (Arch, Manjaro…), o sin instalar nada | BajarSubtitulosESP-@VERSION@-x86_64.AppImage | D |
| Prefieres una carpeta comprimida (no se actualiza sola) | BajarSubtitulosESP-@VERSION@-linux-x86_64.tar.gz | E |

Abre un terminal en la carpeta donde lo descargaste (en Dolphin, tecla F4; en Nautilus o Nemo, clic
derecho › *Abrir en un terminal*). Copia la línea de tu orden, pégala en el terminal y pulsa Intro.
Las de A, B y C piden tu contraseña.

A. Ubuntu, Debian, Linux Mint:

    sudo apt install ./BajarSubtitulosESP-@VERSION@-amd64.deb

B. Fedora, AlmaLinux, Rocky Linux, RHEL:

    sudo dnf install ./BajarSubtitulosESP-@VERSION@-x86_64.rpm

C. openSUSE Tumbleweed:

    sudo zypper install --allow-unsigned-rpm ./BajarSubtitulosESP-@VERSION@-x86_64.rpm

D. AppImage (la abre; la primera vez pregunta si la añades al menú de aplicaciones):

    chmod +x BajarSubtitulosESP-@VERSION@-x86_64.AppImage && ./BajarSubtitulosESP-@VERSION@-x86_64.AppImage

E. Carpeta comprimida (la descomprime ahí mismo y abre la app):

    tar xzf BajarSubtitulosESP-@VERSION@-linux-x86_64.tar.gz && ./bajar-subtitulos-esp/bajar-subtitulos-esp

Con A, B y C, la app queda en el menú de aplicaciones (*Bajar Subtítulos ESP*). En Ubuntu, si al final
sale «N: Download is performed unsandboxed as root…», no pasa nada: es un aviso normal de apt.

## Desinstalar

**Windows:** *Configuración de Windows › Aplicaciones › Bajar Subtítulos ESP › Desinstalar*. La versión
portable se borra sin más.

**Linux:** cierra antes la app (también el icono junto al reloj, si lo tiene). Copia la línea de la
misma letra con la que la instalaste y pégala en un terminal. Cada línea quita primero el menú
contextual (Dolphin, Nemo, Nautilus) y después la app.

A. Ubuntu, Debian, Linux Mint:

    bajar-subtitulos-esp --menu-contextual-quitar; sudo apt remove bajar-subtitulos-esp

B. Fedora, AlmaLinux, Rocky Linux, RHEL:

    bajar-subtitulos-esp --menu-contextual-quitar; sudo dnf remove bajar-subtitulos-esp

C. openSUSE Tumbleweed:

    bajar-subtitulos-esp --menu-contextual-quitar; sudo zypper remove bajar-subtitulos-esp

D. AppImage, en la carpeta donde lo tengas (sirve aunque se haya actualizado y su nombre lleve otra
versión; también lo quita del menú de aplicaciones):

    for a in BajarSubtitulosESP-*-x86_64.AppImage; do "./$a" --menu-contextual-quitar; rm -f "$a"; done; rm -f ~/.local/share/applications/bajar-subtitulos-esp.desktop ~/.local/share/icons/hicolor/scalable/apps/bajar-subtitulos-esp.svg

E. Carpeta comprimida, en la carpeta donde la descomprimiste:

    ./bajar-subtitulos-esp/bajar-subtitulos-esp --menu-contextual-quitar; rm -rf bajar-subtitulos-esp

Tus preferencias se conservan por si vuelves a instalarla. Para borrarlas también:

    rm -rf ~/.config/BajarSubtitulosEsp ~/.cache/bajar-subtitulos-esp

Las contraseñas de OpenSubtitles se guardan en el llavero del escritorio: si quieres quitarlas, vacía
las cuentas en *Configuración* antes de desinstalar. Las copias de los subtítulos sustituidos
(~/.subtitulos-esp) no se tocan: las comparte la skill.

## Comprobar la descarga (opcional)

Descarga también SHA256SUMS.txt en la misma carpeta. En Linux:

    sha256sum -c --ignore-missing SHA256SUMS.txt

Tiene que decir «La suma coincide» u «OK». En Windows, en PowerShell, compara el resultado con la
línea de ese archivo en SHA256SUMS.txt:

    Get-FileHash .\BajarSubtitulosESP-@VERSION@-instalador.exe

Más detalles y preguntas frecuentes:
https://github.com/subtitulos-castellano/bajar-subtitulos-esp-app#instalar

---

# Bajar Subtítulos ESP @VERSION@: how to install and uninstall

Download only the file for your system. Windows and Linux always share the same version number.

## Windows

| File | What it is | How to install it |
|---|---|---|
| BajarSubtitulosESP-@VERSION@-instalador.exe | Installer (recommended) | Double-click it. It does not ask for administrator rights. |
| BajarSubtitulosESP-@VERSION@-portable.zip | Portable, nothing to install | Unzip it anywhere and open BajarSubtitulosESP.exe. |

The program is not digitally signed. If you see "Windows protected your PC", click *More info › Run
anyway*.

## Linux

For 64-bit PCs (x86_64) with a 2022 or newer distribution.

| If you use… | Download | Command |
|---|---|---|
| Ubuntu 22.04+, Debian 12+, Linux Mint 21+ and derivatives | BajarSubtitulosESP-@VERSION@-amd64.deb | A |
| Fedora, AlmaLinux, Rocky Linux or RHEL 9+ | BajarSubtitulosESP-@VERSION@-x86_64.rpm | B |
| openSUSE Tumbleweed | BajarSubtitulosESP-@VERSION@-x86_64.rpm | C |
| Any other (Arch, Manjaro…), or nothing to install | BajarSubtitulosESP-@VERSION@-x86_64.AppImage | D |
| You prefer a compressed folder (no automatic updates) | BajarSubtitulosESP-@VERSION@-linux-x86_64.tar.gz | E |

Open a terminal in the folder where you downloaded it (in Dolphin, press F4; in Nautilus or Nemo,
right-click › *Open in Terminal*). Copy the line for your command, paste it into the terminal and press
Enter. A, B and C ask for your password.

A. Ubuntu, Debian, Linux Mint:

    sudo apt install ./BajarSubtitulosESP-@VERSION@-amd64.deb

B. Fedora, AlmaLinux, Rocky Linux, RHEL:

    sudo dnf install ./BajarSubtitulosESP-@VERSION@-x86_64.rpm

C. openSUSE Tumbleweed:

    sudo zypper install --allow-unsigned-rpm ./BajarSubtitulosESP-@VERSION@-x86_64.rpm

D. AppImage (opens it; the first time it asks whether to add it to the applications menu):

    chmod +x BajarSubtitulosESP-@VERSION@-x86_64.AppImage && ./BajarSubtitulosESP-@VERSION@-x86_64.AppImage

E. Compressed folder (unpacks it right there and opens the app):

    tar xzf BajarSubtitulosESP-@VERSION@-linux-x86_64.tar.gz && ./bajar-subtitulos-esp/bajar-subtitulos-esp

With A, B and C, the app appears in the applications menu (*Bajar Subtítulos ESP*). On Ubuntu, if
"N: Download is performed unsandboxed as root…" appears at the end, it is fine: it is a normal apt
notice.

The app starts in Spanish; change the language in Settings (*Configuración › Idioma*).

## Uninstall

**Windows:** *Windows Settings › Apps › Bajar Subtítulos ESP › Uninstall*. The portable version is
simply deleted.

**Linux:** close the app first (including the icon next to the clock, if it has one). Copy the line with
the same letter you installed it with and paste it into a terminal. Each line first removes the context
menu (Dolphin, Nemo, Nautilus) and then the app.

A. Ubuntu, Debian, Linux Mint:

    bajar-subtitulos-esp --menu-contextual-quitar; sudo apt remove bajar-subtitulos-esp

B. Fedora, AlmaLinux, Rocky Linux, RHEL:

    bajar-subtitulos-esp --menu-contextual-quitar; sudo dnf remove bajar-subtitulos-esp

C. openSUSE Tumbleweed:

    bajar-subtitulos-esp --menu-contextual-quitar; sudo zypper remove bajar-subtitulos-esp

D. AppImage, in the folder where you keep it (it works even if it has updated itself and its name has
another version; it also removes it from the applications menu):

    for a in BajarSubtitulosESP-*-x86_64.AppImage; do "./$a" --menu-contextual-quitar; rm -f "$a"; done; rm -f ~/.local/share/applications/bajar-subtitulos-esp.desktop ~/.local/share/icons/hicolor/scalable/apps/bajar-subtitulos-esp.svg

E. Compressed folder, in the folder where you unpacked it:

    ./bajar-subtitulos-esp/bajar-subtitulos-esp --menu-contextual-quitar; rm -rf bajar-subtitulos-esp

Your settings are kept in case you install it again. To delete them too:

    rm -rf ~/.config/BajarSubtitulosEsp ~/.cache/bajar-subtitulos-esp

OpenSubtitles passwords are stored in the desktop keyring: to remove them, clear the accounts in
*Configuración* (Settings) before uninstalling. Backups of replaced subtitles (~/.subtitulos-esp) are
left alone: they are shared with the skill.

## Check the download (optional)

Also download SHA256SUMS.txt into the same folder. On Linux:

    sha256sum -c --ignore-missing SHA256SUMS.txt

It must say "OK". On Windows, in PowerShell, compare the result with that file's line in
SHA256SUMS.txt:

    Get-FileHash .\BajarSubtitulosESP-@VERSION@-instalador.exe

More details and FAQ:
https://github.com/subtitulos-castellano/bajar-subtitulos-esp-app#instalar
