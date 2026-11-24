"""Linux: la entrada del AppImage en el menú de aplicaciones (los .deb y .rpm ya la ponen al instalarse).

Solo para este usuario, en ~/.local/share (o $XDG_DATA_HOME): applications/bajar-subtitulos-esp.desktop y
su icono. El .desktop es el mismo que lleva dentro el AppImage (en $APPDIR), apuntando al archivo AppImage.

- La primera vez que se abre el AppImage, la app ofrece añadirla; después, en Configuración.
- Si el AppImage se mueve de carpeta, se corrige al abrirlo desde la nueva (asegurar).
- Si se borra, la entrada deja de verse sola: su TryExec apunta a un archivo que ya no existe.
"""
import os
import shutil
import subprocess
from pathlib import Path

from .linux import ID_ESCRITORIO
from .menu_linux import _exec, carpeta_datos

MARCA = 'X-BajarSubtitulosESP-AppImage=true'


def _desktop():
    return carpeta_datos() / 'applications' / f'{ID_ESCRITORIO}.desktop'


def _icono():
    return carpeta_datos() / 'icons' / 'hicolor' / 'scalable' / 'apps' / f'{ID_ESCRITORIO}.svg'


def _plantilla():
    """El .desktop que lleva dentro el AppImage."""
    appdir = os.environ.get('APPDIR', '')
    if os.path.isabs(appdir):
        try:
            return (Path(appdir) / f'{ID_ESCRITORIO}.desktop').read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            pass
    return None


def contenido(appimage, plantilla):
    """El .desktop de `plantilla` apuntando al AppImage `appimage`."""
    lineas = []
    for linea in plantilla.splitlines():
        if linea.startswith(('Exec=', 'TryExec=')):
            continue
        lineas.append(linea)
        if linea.strip() == '[Desktop Entry]':
            lineas += [f'Exec={_exec(str(appimage), "%F")}', f'TryExec={appimage}', MARCA]
    return '\n'.join(lineas) + '\n'


def anadida():
    """True si la entrada del AppImage está (otra entrada con el mismo nombre no cuenta)."""
    try:
        return MARCA in _desktop().read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return False


def appimage_anadido():
    """El AppImage al que apunta la entrada, o None."""
    try:
        for linea in _desktop().read_text(encoding='utf-8').splitlines():
            if linea.startswith('TryExec='):
                return Path(linea.split('=', 1)[1])
    except (OSError, UnicodeDecodeError):
        pass
    return None


def anadir(appimage, plantilla=None):
    """Añade la entrada (o la rehace apuntando a `appimage`). Lanza OSError si no se puede."""
    plantilla = plantilla or _plantilla()
    if plantilla is None:
        raise OSError('no se encuentra el .desktop dentro del AppImage')
    from ..iconos import ICONO_APP
    for ruta, texto in ((_icono(), ICONO_APP), (_desktop(), contenido(appimage, plantilla))):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_name(f'.{ruta.name}.tmp')
        temporal.write_text(texto, encoding='utf-8')
        os.chmod(temporal, 0o644)
        os.replace(temporal, ruta)
    _avisar()


def quitar():
    """Quita la entrada, solo si es la del AppImage. Lanza OSError si no se puede."""
    if anadida():
        _desktop().unlink(missing_ok=True)
        _icono().unlink(missing_ok=True)
        _avisar()


def asegurar(config, appimage, plantilla=None):
    """Al abrir el AppImage: si está activada y falta o apunta a otro sitio (se ha movido), se rehace.
    Devuelve True si ha cambiado algo. Nunca lanza."""
    if not config.menu_aplicaciones:
        return False
    try:
        if anadida() and appimage_anadido() == Path(appimage) and _icono().exists():
            return False
        anadir(appimage, plantilla)
        return True
    except OSError:
        return False


def _avisar():
    """Que el escritorio vuelva a leer las aplicaciones y sus tipos de archivo («Abrir con»)."""
    programa = shutil.which('update-desktop-database')
    if programa:
        try:
            subprocess.run([programa, '-q', str(_desktop().parent)], timeout=20, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            pass
