"""Lo propio de Linux (escritorios freedesktop: KDE, GNOME, Cinnamon, XFCE…, con Wayland o X11)."""
import os
import re
import tempfile
from pathlib import Path

# Nombre del archivo .desktop de la app (sin «.desktop»): con él, el escritorio le pone su icono en la
# barra de tareas (en Wayland, es el app_id de la ventana).
ID_ESCRITORIO = 'bajar-subtitulos-esp'


def carpeta_config():
    """$XDG_CONFIG_HOME o ~/.config (la especificación solo admite una ruta absoluta)."""
    base = os.environ.get('XDG_CONFIG_HOME', '')
    return Path(base) if os.path.isabs(base) else Path.home() / '.config'


def carpeta_ejecucion():
    """$XDG_RUNTIME_DIR: solo de este usuario (permisos 0700) y se vacía al cerrar la sesión. Si no lo
    hay (algunos contenedores), la carpeta temporal."""
    base = os.environ.get('XDG_RUNTIME_DIR', '')
    if os.path.isabs(base) and os.path.isdir(base):
        return Path(base)
    return Path(tempfile.gettempdir())


def bloquear(ruta):
    """Toma el bloqueo del archivo `ruta` (solo un proceso a la vez). Devuelve el descriptor, que hay que
    mantener abierto mientras dure (el sistema lo suelta solo al terminar el proceso, aunque sea de
    golpe); None si ya lo tiene otro proceso; False si no se ha podido comprobar."""
    import fcntl
    try:
        fd = os.open(ruta, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    except OSError:
        os.close(fd)
        return False
    return fd


def soltar(fd):
    if fd:
        try:
            os.close(fd)
        except OSError:
            pass


# Wayland no deja a una app ponerse delante por su cuenta: hace falta el «token de activación» que el
# escritorio da al programa que se acaba de abrir (en XDG_ACTIVATION_TOKEN). La apertura nueva se lo
# pasa a la que ya estaba abierta, que lo usa al traer su ventana al frente (Qt lo lee de ahí).
_TOKEN = re.compile(r'[\x21-\x7e]{1,256}')


def token_activacion():
    token = os.environ.get('XDG_ACTIVATION_TOKEN', '')
    return token if _TOKEN.fullmatch(token) else ''


def usar_token_activacion(token):
    if isinstance(token, str) and _TOKEN.fullmatch(token):
        os.environ['XDG_ACTIVATION_TOKEN'] = token
