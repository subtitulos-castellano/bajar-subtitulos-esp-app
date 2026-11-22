"""Actualizaciones: consulta la última Release en GitHub, descarga el instalador, comprueba su SHA-256
y lo ejecuta en silencio. Sin Qt: la ventana lo usa desde hilos aparte (ver vista_actualizacion.py).

- Solo cuentan las Releases publicadas (no borradores ni versiones previas) con una etiqueta vX.Y.Z
  mayor que la versión de la app.
- Lo que llega de GitHub se trata como datos: solo se aceptan descargas de las Releases de este
  repositorio, con el nombre exacto que genera el workflow, y las notas se muestran como texto plano.
- El instalador solo se ejecuta si su SHA-256 coincide con la huella que publica GitHub (el campo
  `digest` de cada archivo de la Release o, si faltara, SHA256SUMS.txt de la misma Release).
- La actualización solo se instala sola si la app se instaló con el instalador. La versión portable
  solo avisa y abre la página de descarga.
"""
import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from subtitulos import idioma
from subtitulos.idioma import tr
from subtitulos.texto import CONTROL

from . import __version__

REPO = 'subtitulos-castellano/bajar-subtitulos-esp-app'
URL_API = f'https://api.github.com/repos/{REPO}/releases/latest'
PREFIJO_PAGINA = f'https://github.com/{REPO}/releases/'
PREFIJO_DESCARGA = f'https://github.com/{REPO}/releases/download/'
APP_ID = '{6F0C2D8E-3B7A-4E51-9C2F-8A1D5E7B4C93}'     # AppId de packaging/instalador.iss
MUTEX_INSTALADOR = 'BajarSubtitulosESP'              # AppMutex del instalador: "la app está abierta"
MUTEX_PROCESO = 'BajarSubtitulosESP-proceso'         # el instalador espera a que desaparezca (actualizar)

INTERVALO = 20 * 3600              # comprobación automática: como mucho una vez al día (con margen)
TIEMPO_CONSULTA = 15               # segundos
TAMANO_MAX = 400 * 1024 * 1024     # ningún instalador se acerca a esto (el de la 1.0 ocupa ~30 MB)
MAX_NOTAS = 3000                   # caracteres de las notas que se muestran

_HEX64 = re.compile(r'[0-9a-f]{64}')


class ErrorActualizacion(Exception):
    """Fallo con un mensaje que se puede mostrar tal cual."""


class Cancelada(Exception):
    pass


def version(texto):
    """'1.2.3' o 'v1.2.3' -> (1, 2, 3). Cualquier otra cosa -> None."""
    if not isinstance(texto, str):
        return None
    m = re.fullmatch(r'v?([0-9]{1,4})\.([0-9]{1,4})\.([0-9]{1,4})', texto.strip())
    return tuple(int(x) for x in m.groups()) if m else None


def version_corta(texto):
    """'1.0.0' -> '1.0', '1.2.3' -> '1.2.3' (como en la barra lateral)."""
    return texto.removesuffix('.0') if texto.count('.') == 2 else texto


@dataclass(frozen=True)
class Archivo:
    nombre: str
    url: str
    sha256: str          # en minúsculas
    tamano: int


@dataclass(frozen=True)
class Novedad:
    version: str                 # '1.0.2'
    pagina: str                  # página de la Release en GitHub
    notas: str                   # texto plano, ya limpio
    instalador: Archivo = None   # None si falta o no tiene huella: entonces solo se ofrece la página


# ---------- Consulta ----------

def _contexto_ssl():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001 - sin certifi, los certificados de Windows
        return ssl.create_default_context()


def _abrir(url, tiempo=TIEMPO_CONSULTA, accept='*/*'):
    # User-Agent genérico: GitHub lo exige y no hace falta decir nada más de quien pregunta.
    peticion = urllib.request.Request(url, headers={'User-Agent': f'BajarSubtitulosESP/{__version__}',
                                                    'Accept': accept})
    return urllib.request.urlopen(peticion, timeout=tiempo, context=_contexto_ssl())


def _leer(url, limite, accept='*/*'):
    with _abrir(url, accept=accept) as r:
        datos = r.read(limite + 1)
    if len(datos) > limite:
        raise ErrorActualizacion(tr('GitHub ha devuelto una respuesta demasiado grande.'))
    return datos


# Las notas de cada Release llevan las novedades en castellano y, tras esta marca, en inglés (las
# escribe el workflow con CHANGELOG.md y CHANGELOG.en.md). Las Releases anteriores solo están en castellano.
MARCA_INGLES = '<!-- en -->'


def notas_del_idioma(texto, codigo=None):
    """La parte de las notas en el idioma de la app (`codigo`; por defecto, el actual). Sin la marca,
    todo el texto."""
    texto = str(texto or '')
    if MARCA_INGLES not in texto:
        return texto
    castellano, ingles = texto.split(MARCA_INGLES, 1)
    if (codigo or idioma.actual()) != 'en':
        return castellano
    # Tras la marca, el título que se ve en GitHub («### English»): en la app sobra.
    return re.sub(r'\A\s*#+[^\n]*\n', '', ingles.lstrip('\r\n'), count=1)


def limpiar_notas(texto):
    """Notas de la Release (Markdown) como texto plano breve para la ventana."""
    texto = CONTROL.sub('', notas_del_idioma(texto)).replace('\r\n', '\n').strip()
    texto = re.sub(r'\*\*(.+?)\*\*', r'\1', texto)         # negrita
    texto = re.sub(r'`([^`\n]+)`', r'\1', texto)           # código
    texto = re.sub(r'\[([^\[\]\n]+)\]\([^)\n]*\)', r'\1', texto)  # enlaces: solo el texto
    texto = re.sub(r'^(\s*)[-*] ', r'\1• ', texto, flags=re.MULTILINE)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    if len(texto) > MAX_NOTAS:
        texto = texto[:MAX_NOTAS].rsplit('\n', 1)[0] + '\n…'
    return texto


def nombre_instalador(v):
    return f'BajarSubtitulosESP-{v}-instalador.exe'


def interpretar(datos, actual=__version__):
    """Respuesta de /releases/latest -> (Novedad o None si no hay nada más nuevo, url de SHA256SUMS.txt)."""
    if not isinstance(datos, dict):
        raise ErrorActualizacion(tr('GitHub ha devuelto una respuesta inesperada.'))
    if datos.get('draft') or datos.get('prerelease'):
        return None, None
    v = version(datos.get('tag_name'))
    if v is None:
        raise ErrorActualizacion(tr('La última versión publicada no tiene un número de versión válido.'))
    if v <= version(actual):
        return None, None
    texto_v = '.'.join(map(str, v))
    pagina = datos.get('html_url')
    if not (isinstance(pagina, str) and pagina.startswith(PREFIJO_PAGINA)):
        pagina = PREFIJO_PAGINA + 'latest'
    instalador, sumas = None, None
    for a in datos.get('assets') or []:
        if not isinstance(a, dict):
            continue
        nombre, url = a.get('name'), a.get('browser_download_url')
        if not (isinstance(nombre, str) and isinstance(url, str) and url.startswith(PREFIJO_DESCARGA)):
            continue                                     # solo archivos de las Releases de este repositorio
        if nombre == 'SHA256SUMS.txt':
            sumas = url
        elif nombre == nombre_instalador(texto_v):
            digest = a.get('digest')
            sha = digest[7:].lower() if isinstance(digest, str) and digest.lower().startswith('sha256:') else ''
            tamano = a.get('size') if isinstance(a.get('size'), int) and not isinstance(a.get('size'), bool) else 0
            instalador = Archivo(nombre, url, sha if _HEX64.fullmatch(sha) else '', tamano)
    return Novedad(texto_v, pagina, limpiar_notas(datos.get('body')), instalador), sumas


def leer_sumas(texto, nombre):
    """SHA-256 de `nombre` en un SHA256SUMS.txt (formato de sha256sum), o ''."""
    for linea in texto.splitlines():
        partes = linea.strip().split()
        if len(partes) == 2 and partes[1].lstrip('*') == nombre and _HEX64.fullmatch(partes[0].lower()):
            return partes[0].lower()
    return ''


def consultar(actual=__version__):
    """La versión nueva publicada en GitHub, o None si la app está al día. Lanza ErrorActualizacion."""
    try:
        datos = json.loads(_leer(URL_API, 1024 * 1024, 'application/vnd.github+json'))
        novedad, sumas = interpretar(datos, actual)
        if novedad and novedad.instalador and not novedad.instalador.sha256 and sumas:
            sha = leer_sumas(_leer(sumas, 64 * 1024).decode('utf-8', 'replace'), novedad.instalador.nombre)
            novedad = Novedad(novedad.version, novedad.pagina, novedad.notas,
                              Archivo(novedad.instalador.nombre, novedad.instalador.url, sha,
                                      novedad.instalador.tamano))
    except ErrorActualizacion:
        raise
    except urllib.error.HTTPError as e:
        if e.code == 404:              # todavía no hay ninguna Release publicada
            return None
        raise ErrorActualizacion(tr('GitHub ha respondido con el error {codigo}.', codigo=e.code)) from e
    except (OSError, ValueError) as e:
        raise ErrorActualizacion(tr('No se ha podido conectar con GitHub. Comprueba la conexión a internet.')) from e
    if novedad and novedad.instalador and not novedad.instalador.sha256:
        novedad = Novedad(novedad.version, novedad.pagina, novedad.notas, None)   # sin huella no se instala solo
    return novedad


# ---------- Descarga ----------

def carpeta_descargas():
    return Path(tempfile.gettempdir()) / 'BajarSubtitulosESP-actualizacion'


def limpiar_descargas(carpeta=None):
    """Borra los instaladores de actualizaciones anteriores (el registro de la última se conserva)."""
    carpeta = Path(carpeta or carpeta_descargas())
    for f in carpeta.glob('*'):
        if f.suffix.lower() in ('.exe', '.part'):
            try:
                f.unlink()
            except OSError:
                pass             # en uso (el instalador aún termina): la próxima vez


def descargar(archivo, carpeta=None, progreso=None, cancelada=None):
    """Descarga `archivo` comprobando su SHA-256 mientras llega. Devuelve la ruta del archivo ya
    verificado; si no coincide, lo borra y lanza ErrorActualizacion."""
    if not (archivo.sha256 and re.fullmatch(r'BajarSubtitulosESP-[0-9.]+-instalador\.exe', archivo.nombre)):
        raise ErrorActualizacion(tr('La actualización no tiene una huella SHA-256 con la que comprobarla.'))
    carpeta = Path(carpeta or carpeta_descargas())
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / archivo.nombre
    parcial = destino.with_name(destino.name + '.part')
    h, hecho = hashlib.sha256(), 0
    try:
        try:
            with _abrir(archivo.url, tiempo=60) as r, open(parcial, 'wb') as f:
                total = archivo.tamano or int(r.headers.get('Content-Length') or 0)
                if total > TAMANO_MAX:
                    raise ErrorActualizacion(tr('La actualización es demasiado grande: no se ha descargado.'))
                while True:
                    if cancelada and cancelada():
                        raise Cancelada()
                    bloque = r.read(256 * 1024)
                    if not bloque:
                        break
                    hecho += len(bloque)
                    if hecho > TAMANO_MAX:
                        raise ErrorActualizacion(tr('La actualización es demasiado grande: no se ha descargado.'))
                    h.update(bloque)
                    f.write(bloque)
                    if progreso:
                        progreso(hecho, max(total, hecho))
        except (ErrorActualizacion, Cancelada):
            raise
        except (OSError, ValueError) as e:
            raise ErrorActualizacion(tr('La descarga se ha interrumpido. Comprueba la conexión a internet.')) from e
        if h.hexdigest() != archivo.sha256:
            raise ErrorActualizacion(tr('La descarga no coincide con la huella SHA-256 publicada en GitHub: '
                                        'no se ha instalado nada.'))
        os.replace(parcial, destino)
    except BaseException:
        try:
            parcial.unlink()
        except OSError:
            pass
        raise
    return destino


# ---------- Instalación ----------

def instalada(exe=None):
    """True si la app se instaló con el instalador (no es la versión portable ni el código fuente)."""
    if exe is None and not getattr(sys, 'frozen', False):
        return False
    return (Path(exe or sys.executable).parent / 'unins000.exe').is_file()


def modo_instalacion():
    """'usuario' o 'todos': dónde registró el instalador la desinstalación."""
    if sys.platform != 'win32':
        return 'usuario'
    import winreg
    clave = rf'Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}_is1'
    for raiz, modo in ((winreg.HKEY_CURRENT_USER, 'usuario'), (winreg.HKEY_LOCAL_MACHINE, 'todos')):
        try:
            winreg.OpenKey(raiz, clave).Close()
            return modo
        except OSError:
            pass
    return 'usuario'


_mutex = {}


def crear_mutex():
    """Al arrancar: uno para que el instalador sepa que la app está abierta (AppMutex) y otro que dura
    hasta que el proceso termina (el instalador lo espera al actualizar)."""
    if sys.platform != 'win32':
        return
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = wintypes.HANDLE
    k32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    for nombre in (MUTEX_INSTALADOR, MUTEX_PROCESO):
        _mutex[nombre] = k32.CreateMutexW(None, False, nombre)


def _soltar_mutex_instalador():
    """Para que el instalador no se pare con "la app está abierta": se cierra justo después."""
    h = _mutex.pop(MUTEX_INSTALADOR, None)
    if h and sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        ctypes.windll.kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        ctypes.windll.kernel32.CloseHandle(h)


def argumentos_instalador(ruta, modo, registro):
    return [str(ruta), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CLOSEAPPLICATIONS',
            '/ALLUSERS' if modo == 'todos' else '/CURRENTUSER',
            '/REABRIR=1',                     # el instalador espera a que la app se cierre y la vuelve a abrir
            f'/LOG={registro}']


def lanzar_instalador(ruta, modo=None):
    """Ejecuta el instalador ya verificado, independiente de la app (que debe cerrarse a continuación).
    Si la app se instaló para todos los usuarios, Windows pedirá permiso de administrador."""
    ruta = Path(ruta)
    registro = ruta.parent / 'instalacion.log'
    _soltar_mutex_instalador()
    flags = 0
    if sys.platform == 'win32':
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(argumentos_instalador(ruta, modo or modo_instalacion(), registro), close_fds=True,
                     creationflags=flags, cwd=str(ruta.parent))
