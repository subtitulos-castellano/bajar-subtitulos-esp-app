"""Lo propio de Linux (escritorios freedesktop: KDE, GNOME, Cinnamon, XFCE…, con Wayland o X11)."""
import os
import platform
import re
import sys
import tempfile
from pathlib import Path

# Nombre del archivo .desktop de la app (sin «.desktop»): con él, el escritorio le pone su icono en la
# barra de tareas (en Wayland, es el app_id de la ventana).
ID_ESCRITORIO = 'bajar-subtitulos-esp'


def en_wsl():
    """True en WSL (Linux dentro de Windows, con las ventanas en WSLg). Ahí no se puede arrastrar desde el
    Explorador de Windows a la app."""
    return bool(os.environ.get('WSL_DISTRO_NAME')) or 'microsoft' in platform.release().lower()


CARPETA_PAQUETE = Path('/opt') / ID_ESCRITORIO      # donde la ponen el .deb y el .rpm


def appimage():
    """Ruta del AppImage si la app se ejecuta desde uno (su runtime pone APPIMAGE y APPDIR, la carpeta
    donde lo monta); si no, None. Se comprueba que el programa esté dentro de APPDIR: esas variables pasan
    también a los programas que se abran desde un AppImage."""
    ruta, montado = os.environ.get('APPIMAGE', ''), os.environ.get('APPDIR', '')
    if not (getattr(sys, 'frozen', False) and os.path.isabs(ruta) and os.path.isabs(montado)):
        return None
    try:
        Path(sys.executable).resolve().relative_to(Path(montado).resolve())
    except ValueError:
        return None
    return Path(ruta)


def instalacion():
    """'paquete' (.deb o .rpm), 'appimage', 'carpeta' (el .tar.gz descomprimido) o 'codigo' (desde el código)."""
    if not getattr(sys, 'frozen', False):
        return 'codigo'
    if appimage():
        return 'appimage'
    if Path(sys.executable).resolve().parent == CARPETA_PAQUETE:
        return 'paquete'
    return 'carpeta'


def formato_paquete():
    """'deb' o 'rpm': con qué gestor de paquetes se instaló la app (en /opt); None si no se sabe."""
    if Path('/var/lib/dpkg/info', f'{ID_ESCRITORIO}.list').exists():
        return 'deb'
    import shutil
    import subprocess
    rpm = shutil.which('rpm')
    if rpm:
        try:
            if subprocess.run([rpm, '-q', '--quiet', ID_ESCRITORIO], timeout=20, stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                return 'rpm'
        except (OSError, subprocess.SubprocessError):
            pass
    return None


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


def entorno_para_otros_programas():
    """El programa compilado (PyInstaller) arranca con LD_LIBRARY_PATH apuntando a sus propias librerías. Los
    programas que abra (xdg-open, el gestor de paquetes…) deben usar las del sistema: se deja como estaba
    antes de arrancar. A la app no le afecta, porque el sistema ya lo leyó al cargarla."""
    if not getattr(sys, 'frozen', False):
        return
    antes = os.environ.pop('LD_LIBRARY_PATH_ORIG', None)
    if antes is None:
        os.environ.pop('LD_LIBRARY_PATH', None)
    else:
        os.environ['LD_LIBRARY_PATH'] = antes


# Certificados de confianza de cada familia de distribuciones (los mismos que usan su navegador y sus
# programas). El OpenSSL que lleva dentro el programa compilado viene de AlmaLinux y solo los busca donde
# los pone ella (/etc/pki/tls); en Debian, Ubuntu, Arch, openSUSE… no los encontraría y cualquier conexión
# segura que no lleve los suyos propios (p. ej. la cuenta de OpenSubtitles.org) fallaría.
CERTIFICADOS = (
    '/etc/ssl/certs/ca-certificates.crt',     # Debian, Ubuntu, Mint, Arch, Gentoo
    '/etc/pki/tls/certs/ca-bundle.crt',       # Fedora, RHEL, AlmaLinux, Rocky
    '/etc/ssl/ca-bundle.pem',                 # openSUSE
    '/etc/ssl/cert.pem',                      # Alpine, Void y otras
)


def certificados():
    """En el programa compilado, que OpenSSL use los certificados del sistema (SSL_CERT_FILE). Si el usuario
    ya ha elegido otros, o están donde OpenSSL los busca, no se toca nada; si el sistema no tiene ninguno,
    los de certifi, que van dentro. Devuelve el archivo que se usa (None si no se ha cambiado)."""
    if not getattr(sys, 'frozen', False) or os.environ.get('SSL_CERT_FILE') or os.environ.get('SSL_CERT_DIR'):
        return None
    import ssl
    if os.path.isfile(ssl.get_default_verify_paths().openssl_cafile):
        return None
    for ruta in CERTIFICADOS:
        if os.path.isfile(ruta):
            os.environ['SSL_CERT_FILE'] = ruta
            return ruta
    try:
        import certifi
        os.environ['SSL_CERT_FILE'] = certifi.where()
        return os.environ['SSL_CERT_FILE']
    except Exception:  # noqa: BLE001
        return None
