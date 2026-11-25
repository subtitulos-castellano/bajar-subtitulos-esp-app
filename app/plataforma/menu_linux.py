"""Menú contextual «Bajar subtítulos» de los gestores de archivos de Linux (lo común está en
app/menu_contextual.py). Solo para este usuario, en ~/.local/share (o $XDG_DATA_HOME), sin permisos de
administrador:

- Dolphin (KDE): dos *service menus* en kio/servicemenus. En una carpeta (o en el fondo de una carpeta),
  «Bajar subtítulos aquí» con «Solo esta carpeta» / «Esta carpeta y sus subcarpetas» (y lo mismo «en
  inglés»); en uno o varios vídeos, «Bajar subtítulos» y «Bajar subtítulos en inglés».
- Nemo (Cinnamon): las mismas opciones, como acciones (nemo/actions).
- Nautilus (GNOME): no deja poner opciones propias en el menú, solo *scripts* (clic derecho › Scripts):
  «Bajar subtítulos» (lo seleccionado, con subcarpetas, o la carpeta abierta si no hay nada seleccionado)
  y «Bajar subtítulos (solo esta carpeta)», y los dos «en inglés».

Todas las opciones ejecutan el mismo lanzador (LANZADOR), que es quien sabe dónde está la app. Si ya no
está (se ha desinstalado el .deb o el .rpm, o se ha borrado el AppImage), el lanzador quita el menú
entero la primera vez que se usa: así no se queda roto. Si el AppImage solo se ha movido, la app lo
rehace al abrirse (menu_contextual.asegurar).

Con varios vídeos seleccionados, el gestor de archivos los pasa todos juntos a una sola apertura.
"""
import os
import shlex
from pathlib import Path

from subtitulos.idioma import tr

from ..menu_contextual import (ARG_ARCHIVOS, ARG_CARPETA, ARG_INGLES, ARG_SUBCARPETAS, SUBMENU, SUBMENU_INGLES,
                               TEXTO_ARCHIVOS, TEXTO_ARCHIVOS_INGLES, TEXTO_CARPETA, TEXTO_SOLO_CARPETA,
                               TEXTO_SOLO_CARPETA_INGLES)

NEMO = 10        # acciones de Nemo: {ID}-1 … {ID}-10

ID = 'bajar-subtitulos-esp'
MARCA = f'# {ID}: menú contextual de Bajar Subtítulos ESP (lo pone y lo quita la app, en Configuración)'

# Tipos de los vídeos que busca la app (sin .ts, que también es TypeScript: ahí el menú estorbaría).
TIPOS_VIDEO = ('video/x-matroska', 'video/mp4', 'video/x-msvideo', 'video/avi', 'video/x-m4v',
               'video/quicktime', 'video/x-ms-wmv')


def carpeta_datos():
    """$XDG_DATA_HOME o ~/.local/share (la especificación solo admite una ruta absoluta)."""
    base = os.environ.get('XDG_DATA_HOME', '')
    return Path(base) if os.path.isabs(base) else Path.home() / '.local' / 'share'


def lanzador():
    return carpeta_datos() / ID / 'menu-contextual'


def _dolphin():
    return carpeta_datos() / 'kio' / 'servicemenus'


def _nemo():
    return carpeta_datos() / 'nemo' / 'actions'


def _nautilus():
    return carpeta_datos() / 'nautilus' / 'scripts'


def _nombre_script(texto):
    """Nombre de archivo de un script de Nautilus (es lo que se ve en el menú): sin barras."""
    return texto.replace('/', '-')


# ---------- Contenido de cada archivo ----------

def _exec(*partes):
    """Una línea Exec de un archivo .desktop: cada parte entre comillas, con los caracteres reservados
    escapados (especificación de freedesktop.org)."""
    def comillas(p):
        p = p.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')
        return '"' + p.replace('%', '%%') + '"'
    return ' '.join(p if p.startswith(('-', '%')) else comillas(p) for p in partes)


def _desktop(grupos):
    """Texto de un archivo .desktop: [(grupo, {clave: valor})]."""
    bloques = []
    for grupo, valores in grupos:
        bloques.append('\n'.join([f'[{grupo}]'] + [f'{k}={v}' for k, v in valores.items()]))
    return MARCA + '\n' + '\n\n'.join(bloques) + '\n'


def _texto_lanzador(prog, a_borrar):
    """El script al que llaman todas las opciones: abre la app, o quita el menú si ya no está."""
    existe = ' && '.join(f'[ -e {shlex.quote(p)} ]' for p in prog if p.startswith('/')) or 'true'
    borrar = ' '.join(shlex.quote(str(p)) for p in a_borrar)
    return (f'#!/bin/sh\n{MARCA}\n'
            '# Si la app ya no está (se desinstaló o se borró el AppImage), quita el menú.\n'
            f'if {existe}; then\n'
            f'    exec {" ".join(shlex.quote(p) for p in prog)} "$@"\n'
            'fi\n'
            f'rm -f {borrar} "$0"\n'
            f'rmdir {shlex.quote(str(lanzador().parent))} 2> /dev/null\n'
            'exit 0\n')


def _texto_script(*argumentos):
    """Script de Nautilus: lo seleccionado (rutas relativas a la carpeta abierta), o la carpeta abierta."""
    return (f'#!/bin/sh\n{MARCA}\n'
            'if [ "$#" -eq 0 ]; then set -- "$PWD"; fi\n'
            f'exec {shlex.quote(str(lanzador()))} {" ".join(argumentos)} "$@"\n')


def archivos(prog):
    """{ruta: (texto, ejecutable)} de todo lo que se escribe."""
    lz = str(lanzador())
    icono = str(lanzador().with_name('icono.svg'))
    carpetas = _desktop(
        [('Desktop Entry', {'Type': 'Service', 'MimeType': 'inode/directory;',
                            'Actions': 'solo;todo;solo_ingles;todo_ingles;',
                            'X-KDE-Submenu': tr(TEXTO_CARPETA), 'X-KDE-Priority': 'TopLevel', 'Icon': icono})]
        + [(f'Desktop Action {nombre}', {'Name': tr(texto), 'Icon': icono, 'Exec': _exec(lz, arg, '%F')})
           for nombre, (texto, arg) in zip(('solo', 'todo'), SUBMENU)]
        + [(f'Desktop Action {nombre}', {'Name': tr(texto), 'Icon': icono, 'Exec': _exec(lz, ARG_INGLES, arg, '%F')})
           for nombre, (texto, arg) in zip(('solo_ingles', 'todo_ingles'), SUBMENU_INGLES)])
    videos = _desktop(
        [('Desktop Entry', {'Type': 'Service', 'MimeType': ';'.join(TIPOS_VIDEO) + ';',
                            'Actions': 'bajar;bajar_ingles;', 'X-KDE-Priority': 'TopLevel'}),
         ('Desktop Action bajar', {'Name': tr(TEXTO_ARCHIVOS), 'Icon': icono,
                                   'Exec': _exec(lz, ARG_ARCHIVOS, '%F')}),
         ('Desktop Action bajar_ingles', {'Name': tr(TEXTO_ARCHIVOS_INGLES), 'Icon': icono,
                                          'Exec': _exec(lz, ARG_INGLES, ARG_ARCHIVOS, '%F')})])
    res = {
        _dolphin() / f'{ID}-carpetas.desktop': (carpetas, True),     # Dolphin exige que sean ejecutables
        _dolphin() / f'{ID}-videos.desktop': (videos, True),
    }
    # Nemo: en carpetas seleccionadas (%F) y en el fondo de una carpeta (%P, la carpeta abierta).
    nemo = [('1', ARG_CARPETA, 'notnone', 'Extensions=dir;', '%F'),
            ('2', ARG_SUBCARPETAS, 'notnone', 'Extensions=dir;', '%F'),
            ('3', ARG_CARPETA, 'none', 'Extensions=any;', '%P'),
            ('4', ARG_SUBCARPETAS, 'none', 'Extensions=any;', '%P')]
    for submenu, primero, extra in ((SUBMENU, 0, ()), (SUBMENU_INGLES, 5, (ARG_INGLES,))):
        titulos = dict((arg, texto) for texto, arg in submenu)
        for n, arg, seleccion, tipos, variable in nemo:
            clave, valor = tipos.split('=')
            res[_nemo() / f'{ID}-{int(n) + primero}.nemo_action'] = (_desktop([('Nemo Action', {
                'Name': f'{tr(TEXTO_CARPETA)}: {tr(titulos[arg]).lower()}',
                'Exec': _exec(lz, *extra, arg, variable), 'Selection': seleccion, clave: valor})]), False)
    for n, texto, extra in (('5', TEXTO_ARCHIVOS, ()), ('10', TEXTO_ARCHIVOS_INGLES, (ARG_INGLES,))):
        res[_nemo() / f'{ID}-{n}.nemo_action'] = (_desktop([('Nemo Action', {
            'Name': tr(texto), 'Exec': _exec(lz, *extra, ARG_ARCHIVOS, '%F'),
            'Selection': 'notnone', 'Mimetypes': ';'.join(TIPOS_VIDEO) + ';'})]), False)
    res[_nautilus() / _nombre_script(tr(TEXTO_ARCHIVOS))] = (_texto_script(ARG_SUBCARPETAS), True)
    res[_nautilus() / _nombre_script(tr(TEXTO_SOLO_CARPETA))] = (_texto_script(ARG_CARPETA), True)
    res[_nautilus() / _nombre_script(tr(TEXTO_ARCHIVOS_INGLES))] = (_texto_script(ARG_INGLES, ARG_SUBCARPETAS), True)
    res[_nautilus() / _nombre_script(tr(TEXTO_SOLO_CARPETA_INGLES))] = (_texto_script(ARG_INGLES, ARG_CARPETA),
                                                                         True)
    from ..iconos import ICONO_APP
    res[Path(icono)] = (ICONO_APP, False)
    res[lanzador()] = (_texto_lanzador(prog, list(res)), True)
    return res


# ---------- Leer lo que hay ----------

def _es_nuestro(ruta):
    try:
        with open(ruta, encoding='utf-8') as f:
            return MARCA in f.read(4096)
    except (OSError, UnicodeDecodeError):
        return False


def _nuestros_scripts():
    """Los scripts de Nautilus de la app que hay ahora (sus nombres dependen del idioma)."""
    try:
        return sorted(p for p in _nautilus().iterdir() if p.is_file() and _es_nuestro(p))
    except OSError:
        return []


def _existentes():
    candidatos = [_dolphin() / f'{ID}-carpetas.desktop', _dolphin() / f'{ID}-videos.desktop',
                  lanzador(), lanzador().with_name('icono.svg')]
    candidatos += [_nemo() / f'{ID}-{n}.nemo_action' for n in range(1, NEMO + 1)]
    return [p for p in candidatos if p.exists()] + _nuestros_scripts()


def _programa_del_lanzador():
    """La orden que ejecuta el lanzador (lista), o None."""
    try:
        texto = lanzador().read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return None
    for linea in texto.splitlines():
        linea = linea.strip()
        if linea.startswith('exec '):
            partes = shlex.split(linea[5:])
            return partes[:-1] if partes and partes[-1] == '$@' else partes
    return None


# ---------- Lo que pide menu_contextual ----------

def registrar(prog):
    """Escribe el menú (o lo rehace apuntando a `prog`). Lanza OSError si no se puede."""
    quitar()
    for ruta, (texto, ejecutable) in archivos(prog).items():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_name(f'.{ruta.name}.tmp')
        temporal.write_text(texto, encoding='utf-8')
        os.chmod(temporal, 0o755 if ejecutable else 0o644)
        os.replace(temporal, ruta)


def quitar():
    """Quita el menú (solo los archivos de la app). Lanza OSError si no se puede."""
    for ruta in _existentes():
        if ruta.name == 'icono.svg' or _es_nuestro(ruta):
            ruta.unlink(missing_ok=True)
    try:
        lanzador().parent.rmdir()            # solo si ha quedado vacía
    except OSError:
        pass


def registrado():
    return _programa_del_lanzador() is not None


def programa_registrado():
    prog = _programa_del_lanzador()
    return Path(prog[0]) if prog else None


def al_dia(prog):
    """True si todo está exactamente como lo pondría `prog` (mismo programa, mismos textos)."""
    esperado = archivos(prog)
    if set(_existentes()) != set(esperado):
        return False
    try:
        return all(r.read_text(encoding='utf-8') == texto for r, (texto, _) in esperado.items())
    except (OSError, UnicodeDecodeError):
        return False


def misma(a, b):
    return str(a) == str(b)


def texto_registrado():
    """El texto de «Bajar subtítulos aquí» tal como está en el menú de Dolphin, o ''."""
    try:
        for linea in (_dolphin() / f'{ID}-carpetas.desktop').read_text(encoding='utf-8').splitlines():
            if linea.startswith('X-KDE-Submenu='):
                return linea.split('=', 1)[1]
    except (OSError, UnicodeDecodeError):
        pass
    return ''


def retitular(prog):
    """Pone los textos en el idioma de la app, apuntando al mismo programa que ya tenía. Lanza OSError."""
    registrar(_programa_del_lanzador() or prog)


def describir(prog):
    """Para la autoprueba."""
    return f'{len(archivos(prog))} archivos en {carpeta_datos()} · registrado: {registrado()} · orden: {prog}'
