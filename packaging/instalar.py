"""Instrucciones de instalar y desinstalar de cada Release, en castellano y en inglés, en dos formatos con
el mismo contenido: INSTALAR-<versión>.txt (texto sin formato, para cualquier editor) e
INSTALAR-<versión>.md (Markdown). Lo ejecuta el workflow al publicar:

    python3 -I packaging/instalar.py VERSIÓN CARPETA

Las órdenes de Linux van cada una en su línea, con los nombres de los archivos de esa versión, para
copiarlas y pegarlas en un terminal. tests/test_actualizar.py comprueba que nombran exactamente los
archivos que se publican.
"""
import sys
from pathlib import Path

URL = 'https://github.com/subtitulos-castellano/bajar-subtitulos-esp-app#instalar'


def archivos(v):
    return {k: f'BajarSubtitulosESP-{v}-{s}' for k, s in (
        ('exe', 'windows-instalador.exe'), ('zip', 'windows-portable.zip'), ('deb', 'linux-amd64.deb'),
        ('rpm', 'linux-x86_64.rpm'), ('app', 'linux-x86_64.AppImage'), ('tar', 'linux-x86_64.tar.gz'))}


def ordenes(v):
    f = archivos(v)
    instalar = {
        'A': f'sudo apt install ./{f["deb"]}',
        'B': f'sudo dnf install ./{f["rpm"]}',
        'C': f'sudo zypper install --allow-unsigned-rpm ./{f["rpm"]}',
        'D': f'chmod +x {f["app"]} && ./{f["app"]}',
        'E': f'tar xzf {f["tar"]} && ./bajar-subtitulos-esp/bajar-subtitulos-esp',
    }
    desinstalar = {
        'A': 'sudo apt remove bajar-subtitulos-esp',
        'B': 'sudo dnf remove bajar-subtitulos-esp',
        'C': 'sudo zypper remove bajar-subtitulos-esp',
        # Sirve aunque se haya actualizado solo (su nombre lleva otra versión).
        'D': 'for a in BajarSubtitulosESP-*.AppImage; do "./$a" --desinstalar; rm -f "$a"; done',
        'E': './bajar-subtitulos-esp/bajar-subtitulos-esp --desinstalar; rm -rf bajar-subtitulos-esp',
    }
    return instalar, desinstalar


BORRAR = 'rm -rf ~/.config/BajarSubtitulosEsp ~/.cache/bajar-subtitulos-esp'
SUMAS = 'sha256sum -c --ignore-missing SHA256SUMS.txt'


def textos(v):
    """Los textos de cada idioma. Entre «» o "", lo que en Markdown va en cursiva o como código."""
    f = archivos(v)
    linux = [f['deb'], f['rpm'], f['rpm'], f['app'], f['tar']]
    es = dict(
        titulo='Bajar Subtítulos ESP: cómo instalar y desinstalar', version=f'Versión {v}',
        otro_idioma='(English below.)',
        intro='Descarga solo el archivo de tu sistema. Windows y Linux tienen el mismo número de versión.',
        cab_win=['Qué es', 'Cómo se instala', 'Archivo'],
        filas_win=[['Instalador (recomendado)', 'Ábrelo con doble clic (no pide administrador)', f['exe']],
                   ['Portable, sin instalar', 'Descomprímelo y abre BajarSubtitulosESP.exe', f['zip']]],
        firma='El programa no está firmado digitalmente. Si sale «Windows protegió su PC», pulsa '
              '«Más información» y luego «Ejecutar de todas formas».',
        linux='Para PC de 64 bits (x86_64) con una distribución de 2022 o posterior.',
        cab_linux=['Orden', 'Si usas...', 'Descarga'],
        distros=['Ubuntu 22.04+, Debian 12+, Linux Mint 21+ y derivadas', 'Fedora, AlmaLinux, Rocky Linux o RHEL 9+',
                 'openSUSE Tumbleweed', 'Cualquier otra (Arch, Manjaro...), o sin instalar nada',
                 'Una carpeta comprimida (no se actualiza sola)'],
        terminal='Abre un terminal en la carpeta donde lo descargaste (en Dolphin, tecla F4; en Nautilus o '
                 'Nemo, clic derecho y «Abrir en un terminal»). Copia la línea de tu orden, pégala en el '
                 'terminal y pulsa Intro. Las de A, B y C piden tu contraseña.',
        inst={'A': 'Ubuntu, Debian, Linux Mint:', 'B': 'Fedora, AlmaLinux, Rocky Linux, RHEL:',
              'C': 'openSUSE Tumbleweed:',
              'D': 'AppImage (la abre; la primera vez pregunta si la añades al menú de aplicaciones):',
              'E': 'Carpeta comprimida (la descomprime ahí mismo y abre la app):'},
        tras=['Con A, B y C, la app queda en el menú de aplicaciones («Bajar Subtítulos ESP»). En Ubuntu, '
              'si al final sale «N: Download is performed unsandboxed as root...», no pasa nada: es un '
              'aviso normal de apt.'],
        h_des='Desinstalar',
        des_win='Windows: «Configuración de Windows > Aplicaciones > Bajar Subtítulos ESP > Desinstalar». '
                'La versión portable se borra sin más.',
        des_linux='Linux: cierra antes la app (también el icono junto al reloj, si lo tiene). Copia la línea '
                  'de la misma letra con la que la instalaste y pégala en un terminal. Además de la app, se '
                  'quitan su menú contextual (Dolphin, Nemo, Nautilus), los accesos que le hayas puesto en el '
                  'escritorio y en la barra de tareas, y si la habías quitado del menú de aplicaciones, al '
                  'volver a instalarla aparecerá otra vez.',
        des={'A': 'Ubuntu, Debian, Linux Mint:', 'B': 'Fedora, AlmaLinux, Rocky Linux, RHEL:',
             'C': 'openSUSE Tumbleweed:',
             'D': 'AppImage, en la carpeta donde lo tengas (sirve aunque se haya actualizado y su nombre '
                  'lleve otra versión; también lo quita del menú de aplicaciones):',
             'E': 'Carpeta comprimida, en la carpeta donde la descomprimiste:'},
        pref='Tus preferencias se conservan por si vuelves a instalarla. Para borrarlas también:',
        llavero='Las contraseñas de OpenSubtitles se guardan en el llavero del escritorio: si quieres '
                'quitarlas, vacía las cuentas en Configuración antes de desinstalar. Las copias de los '
                'subtítulos sustituidos ("~/.subtitulos-esp") no se tocan: las comparte la skill.',
        h_sumas='Comprobar la descarga (opcional)',
        sumas='Descarga también "SHA256SUMS.txt" en la misma carpeta. En Linux (tiene que decir '
              '«La suma coincide» u «OK»):',
        sumas_win='En Windows, en PowerShell, compara el resultado con la línea de ese archivo en '
                  '"SHA256SUMS.txt":',
        mas='Más detalles y preguntas frecuentes:',
    )
    en = dict(
        titulo='Bajar Subtítulos ESP: how to install and uninstall', version=f'Version {v}', otro_idioma='',
        intro='Download only the file for your system. Windows and Linux always share the same version number.',
        cab_win=['What it is', 'How to install it', 'File'],
        filas_win=[['Installer (recommended)', 'Double-click it (no administrator rights)', f['exe']],
                   ['Portable, nothing to install', 'Unzip it and open BajarSubtitulosESP.exe', f['zip']]],
        firma='The program is not digitally signed. If you see «Windows protected your PC», click '
              '«More info» and then «Run anyway».',
        linux='For 64-bit PCs (x86_64) with a 2022 or newer distribution.',
        cab_linux=['Command', 'If you use...', 'Download'],
        distros=['Ubuntu 22.04+, Debian 12+, Linux Mint 21+ and derivatives', 'Fedora, AlmaLinux, Rocky Linux or RHEL 9+',
                 'openSUSE Tumbleweed', 'Any other (Arch, Manjaro...), or nothing to install',
                 'A compressed folder (no automatic updates)'],
        terminal='Open a terminal in the folder where you downloaded it (in Dolphin, press F4; in Nautilus or '
                 'Nemo, right-click and «Open in Terminal»). Copy the line for your command, paste it into '
                 'the terminal and press Enter. A, B and C ask for your password.',
        inst={'A': 'Ubuntu, Debian, Linux Mint:', 'B': 'Fedora, AlmaLinux, Rocky Linux, RHEL:',
              'C': 'openSUSE Tumbleweed:',
              'D': 'AppImage (opens it; the first time it asks whether to add it to the applications menu):',
              'E': 'Compressed folder (unpacks it right there and opens the app):'},
        tras=['With A, B and C, the app appears in the applications menu («Bajar Subtítulos ESP»). On '
              'Ubuntu, if «N: Download is performed unsandboxed as root...» appears at the end, it is fine: '
              'it is a normal apt notice.',
              'The app starts in Spanish; change the language in Settings («Configuración > Idioma»).'],
        h_des='Uninstall',
        des_win='Windows: «Windows Settings > Apps > Bajar Subtítulos ESP > Uninstall». The portable version '
                'is simply deleted.',
        des_linux='Linux: close the app first (including the icon next to the clock, if it has one). Copy the '
                  'line with the same letter you installed it with and paste it into a terminal. Besides the '
                  'app, this removes its context menu (Dolphin, Nemo, Nautilus) and the shortcuts you gave it '
                  'on the desktop and the taskbar, and if you had removed it from the applications menu, it '
                  'will appear again when you reinstall it.',
        des={'A': 'Ubuntu, Debian, Linux Mint:', 'B': 'Fedora, AlmaLinux, Rocky Linux, RHEL:',
             'C': 'openSUSE Tumbleweed:',
             'D': 'AppImage, in the folder where you keep it (it works even if it has updated itself and its '
                  'name has another version; it also removes it from the applications menu):',
             'E': 'Compressed folder, in the folder where you unpacked it:'},
        pref='Your settings are kept in case you install it again. To delete them too:',
        llavero='OpenSubtitles passwords are stored in the desktop keyring: to remove them, clear the '
                'accounts in Configuración (Settings) before uninstalling. Backups of replaced subtitles '
                '("~/.subtitulos-esp") are left alone: they are shared with the skill.',
        h_sumas='Check the download (optional)',
        sumas='Also download "SHA256SUMS.txt" into the same folder. On Linux (it must say «OK»):',
        sumas_win='On Windows, in PowerShell, compare the result with that file\'s line in "SHA256SUMS.txt":',
        mas='More details and FAQ:',
    )
    for t in (es, en):
        t['filas_linux'] = [[k, d, a] for k, d, a in zip('ABCDE', t['distros'], linux)]
    return es, en


# ---------- Texto sin formato ----------

def _parrafo(texto, ancho=96, sangria=''):
    import textwrap
    return textwrap.fill(texto, ancho, subsequent_indent=sangria, break_long_words=False, break_on_hyphens=False)


def _tabla_txt(cab, filas):
    anchos = [max(len(x) for x in col) for col in zip(cab, *filas)][:-1]

    def linea(cols):
        return '  ' + '   '.join(c.ljust(a) for c, a in zip(cols[:-1], anchos)) + '   ' + cols[-1]
    ultima = max(len(f[-1]) for f in filas)
    return '\n'.join([linea(cab), linea(['-' * a for a in anchos] + ['-' * ultima])] + [linea(f) for f in filas])


def _txt(t, v):
    instalar, desinstalar = ordenes(v)

    def titulo(s, c):
        return f'{s}\n{c * len(s)}'

    def bloque(titulos, cmds):
        return '\n\n'.join(f'{_parrafo(f"{k}. {titulos[k]}", sangria="   ")}\n\n    {cmds[k]}' for k in 'ABCDE')
    p = [titulo(t['titulo'].upper(), '='), t['version']]
    if t['otro_idioma']:
        p += ['', t['otro_idioma']]
    p += ['', _parrafo(t['intro']), '', '', titulo('WINDOWS', '-'), '', _tabla_txt(t['cab_win'], t['filas_win']), '',
          _parrafo(t['firma']), '', '', titulo('LINUX', '-'), '', _parrafo(t['linux']), '',
          _tabla_txt(t['cab_linux'], t['filas_linux']), '', _parrafo(t['terminal']), '',
          bloque(t['inst'], instalar), '']
    for parrafo in t['tras']:
        p += [_parrafo(parrafo), '']
    p += ['', titulo(t['h_des'].upper(), '-'), '', _parrafo(t['des_win']), '', _parrafo(t['des_linux']), '',
          bloque(t['des'], desinstalar), '', _parrafo(t['pref']), '', f'    {BORRAR}', '', _parrafo(t['llavero']),
          '', '', titulo(t['h_sumas'].upper(), '-'), '', _parrafo(t['sumas']), '', f'    {SUMAS}', '',
          _parrafo(t['sumas_win']), '', f'    Get-FileHash .\\{archivos(v)["exe"]}', '', '', t['mas'], URL]
    return '\n'.join(p) + '\n'


def txt(v):
    es, en = textos(v)
    return _txt(es, v) + '\n\n' + '#' * 96 + '\n\n\n' + _txt(en, v)


# ---------- Markdown ----------

def _md_en_linea(texto):
    """«…» en cursiva y "…" como código."""
    import re
    texto = re.sub(r'«([^»]*)»', r'*\1*', texto)
    return re.sub(r'"([^"]*)"', r'`\1`', texto)


def _tabla_md(cab, filas):
    def linea(cols):
        return '| ' + ' | '.join(cols[:-1] + [f'`{cols[-1]}`']) + ' |'
    return '\n'.join(['| ' + ' | '.join(cab) + ' |', '|' + '---|' * len(cab)] + [linea(f) for f in filas])


def _md(t, v):
    instalar, desinstalar = ordenes(v)

    def bloque(titulos, cmds):
        return '\n\n'.join(f'**{k}.** {_md_en_linea(titulos[k])}\n\n```bash\n{cmds[k]}\n```' for k in 'ABCDE')
    p = [f'# {t["titulo"]}', '', f'**{t["version"]}**']
    if t['otro_idioma']:
        p += ['', f'*{t["otro_idioma"].strip("()")}*']
    p += ['', t['intro'], '', '## Windows', '', _tabla_md(t['cab_win'], t['filas_win']), '',
          _md_en_linea(t['firma']), '', '## Linux', '', t['linux'], '', _tabla_md(t['cab_linux'], t['filas_linux']),
          '', _md_en_linea(t['terminal']), '', bloque(t['inst'], instalar), '']
    for parrafo in t['tras']:
        p += [_md_en_linea(parrafo), '']
    p += [f'## {t["h_des"]}', '', _md_en_linea(t['des_win']), '', _md_en_linea(t['des_linux']), '',
          bloque(t['des'], desinstalar), '', t['pref'], '', f'```bash\n{BORRAR}\n```', '', _md_en_linea(t['llavero']),
          '', f'## {t["h_sumas"]}', '', _md_en_linea(t['sumas']), '', f'```bash\n{SUMAS}\n```', '',
          _md_en_linea(t['sumas_win']), '', f'```powershell\nGet-FileHash .\\{archivos(v)["exe"]}\n```', '',
          f'{t["mas"]} <{URL}>']
    return '\n'.join(p) + '\n'


def md(v):
    es, en = textos(v)
    return _md(es, v) + '\n---\n\n' + _md(en, v)


def main(argv):
    version, carpeta = argv
    carpeta = Path(carpeta)
    for extension, generar in (('txt', txt), ('md', md)):
        archivo = carpeta / f'INSTALAR-{version}.{extension}'
        archivo.write_text(generar(version), encoding='utf-8', newline='\n')
        print(archivo)


if __name__ == '__main__':
    main(sys.argv[1:])
