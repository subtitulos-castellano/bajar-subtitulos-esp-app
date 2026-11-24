"""Actualizaciones: consulta las Releases en GitHub, descarga el instalador, comprueba su SHA-256
y lo ejecuta en silencio. Sin Qt: la ventana lo usa desde hilos aparte (ver vista_actualizacion.py).

- Solo cuentan las Releases publicadas (no borradores ni versiones previas) con una etiqueta vX.Y.Z
  mayor que la versión de la app.
- Cada versión sale para Windows y Linux con el mismo número, pero la app solo avisa si alguna de las
  versiones nuevas trae cambios para su sistema: en las notas (el CHANGELOG), una novedad que empieza
  por «[Windows]» o «[Linux]» es solo de ese sistema; sin marca, de los dos. Se actualiza siempre a la
  última, y las novedades que se muestran son las de su sistema en todas las versiones que se salta.
- Lo que llega de GitHub se trata como datos: solo se aceptan descargas de las Releases de este
  repositorio, con el nombre exacto que genera el workflow, y las notas se muestran como texto plano.
- El instalador solo se ejecuta si su SHA-256 coincide con la huella que publica GitHub (el campo
  `digest` de cada archivo de la Release o, si faltara, SHA256SUMS.txt de la misma Release).
- La actualización solo se instala sola si la app se instaló con el instalador. La versión portable
  solo avisa y abre la página de descarga.
- En Linux: el .deb y el .rpm se instalan con el gestor de paquetes (apt, dnf o zypper) a través de pkexec,
  que pide la contraseña en una ventana del sistema; el AppImage se sustituye a sí mismo (se escribe al
  lado y luego se renombra). El .tar.gz y el código fuente solo avisan.
"""
import hashlib
import json
import os
import re
import shutil
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
from .plataforma import LINUX, SISTEMA, WINDOWS

REPO = 'subtitulos-castellano/bajar-subtitulos-esp-app'
URL_API = f'https://api.github.com/repos/{REPO}/releases?per_page=30'   # las más recientes primero
PREFIJO_PAGINA = f'https://github.com/{REPO}/releases/'
PREFIJO_DESCARGA = f'https://github.com/{REPO}/releases/download/'
APP_ID = '{6F0C2D8E-3B7A-4E51-9C2F-8A1D5E7B4C93}'     # AppId de packaging/windows/instalador.iss
MUTEX_INSTALADOR = 'BajarSubtitulosESP'              # AppMutex del instalador: "la app está abierta"
MUTEX_PROCESO = 'BajarSubtitulosESP-proceso'         # el instalador espera a que desaparezca (actualizar)

INTERVALO = 20 * 3600              # comprobación automática: como mucho una vez al día (con margen)
TIEMPO_CONSULTA = 15               # segundos
TAMANO_MAX = 400 * 1024 * 1024     # ningún instalador se acerca a esto (el de la 1.0 ocupa ~30 MB)
MAX_RESPUESTA = 4 * 1024 * 1024    # la lista de Releases (30 Releases ocupan unos 500 KB)
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


# Novedades solo para un sistema: «- [Windows] …» o «- [Linux] …» (sin marca: para los dos).
_VINETA = re.compile(r'[-*]\s')
_MARCA = re.compile(r'([-*]\s+)\[(windows|linux)\]\s*', re.IGNORECASE)


def notas_del_sistema(texto, sistema=SISTEMA):
    """(notas sin las novedades de otros sistemas ni la marca de las del propio, True si alguna novedad
    es para `sistema`). Una novedad de otro sistema se quita con sus líneas sangradas (sus detalles).
    Unas notas sin lista de novedades cuentan para todos."""
    salida, saltar, hay_lista, propia = [], False, False, False
    for linea in str(texto or '').replace('\r\n', '\n').split('\n'):
        if _VINETA.match(linea):
            hay_lista = True
            m = _MARCA.match(linea)
            saltar = bool(m) and m.group(2).lower() != sistema
            if saltar:
                continue
            propia = True
            if m:
                linea = m.group(1) + linea[m.end():]
        elif saltar:
            if not linea.strip() or linea[0].isspace():
                continue
            saltar = False
        salida.append(linea)
    return '\n'.join(salida), propia or not hay_lista


def limpiar_notas(texto):
    """Notas de la Release (Markdown) como texto plano breve para la ventana."""
    return _recortar(_texto_plano(notas_del_idioma(texto)))


def _recortar(texto):
    if len(texto) > MAX_NOTAS:
        texto = texto[:MAX_NOTAS].rsplit('\n', 1)[0] + '\n…'
    return texto


def _texto_plano(texto):
    texto = CONTROL.sub('', texto).replace('\r\n', '\n').strip()
    texto = re.sub(r'\*\*(.+?)\*\*', r'\1', texto)         # negrita
    texto = re.sub(r'`([^`\n]+)`', r'\1', texto)           # código
    texto = re.sub(r'\[([^\[\]\n]+)\]\([^)\n]*\)', r'\1', texto)  # enlaces: solo el texto
    texto = re.sub(r'^(\s*)[-*] ', r'\1• ', texto, flags=re.MULTILINE)
    return re.sub(r'\n{3,}', '\n\n', texto)


# Linux: el archivo de la Release para cada forma de instalar la app.
SUFIJOS_LINUX = {'deb': 'amd64.deb', 'rpm': 'x86_64.rpm', 'appimage': 'x86_64.AppImage'}
_DESCARGABLE = re.compile(r'BajarSubtitulosESP-[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}-'
                          r'(instalador\.exe|amd64\.deb|x86_64\.rpm|x86_64\.AppImage)')


def nombre_instalador(v, sistema=SISTEMA, tipo=None):
    """El archivo de la Release con el que se actualiza la app en este sistema, o None si aquí la app
    no se actualiza sola (solo avisa y abre la página de descarga). En Linux depende de cómo se instaló
    (`tipo`; por defecto, el de esta copia: ver tipo_linux)."""
    if sistema == 'windows':
        return f'BajarSubtitulosESP-{v}-instalador.exe'
    if sistema == 'linux':
        sufijo = SUFIJOS_LINUX.get(tipo or tipo_linux())
        return f'BajarSubtitulosESP-{v}-{sufijo}' if sufijo else None
    return None


def interpretar(datos, actual=__version__, sistema=SISTEMA, tipo=None):
    """Respuesta de /releases (la lista) -> (Novedad o None si no hay nada nuevo para `sistema`, url de
    SHA256SUMS.txt de la última versión)."""
    if not isinstance(datos, list):
        raise ErrorActualizacion(tr('GitHub ha devuelto una respuesta inesperada.'))
    nuevas = []
    for d in datos:
        if not isinstance(d, dict) or d.get('draft') or d.get('prerelease'):
            continue
        v = version(d.get('tag_name'))
        if v is not None and v > version(actual):
            nuevas.append((v, d))
    nuevas.sort(key=lambda x: x[0], reverse=True)
    para_este = []                      # (versión, notas) de las que traen cambios para este sistema
    for v, d in nuevas:
        notas, propia = notas_del_sistema(notas_del_idioma(d.get('body')), sistema)
        if propia:
            para_este.append((v, _texto_plano(notas)))
    if not para_este:
        return None, None
    v, ultima = nuevas[0]               # se actualiza siempre a la última
    texto_v = '.'.join(map(str, v))
    if len(para_este) == 1:
        notas = para_este[0][1]
    else:
        notas = '\n\n'.join(tr('Versión {version}', version=version_corta('.'.join(map(str, x)))) + '\n' + n
                            for x, n in para_este)
    pagina = ultima.get('html_url')
    if not (isinstance(pagina, str) and pagina.startswith(PREFIJO_PAGINA)):
        pagina = PREFIJO_PAGINA + 'latest'
    instalador, sumas = None, None
    for a in ultima.get('assets') or []:
        if not isinstance(a, dict):
            continue
        nombre, url = a.get('name'), a.get('browser_download_url')
        if not (isinstance(nombre, str) and isinstance(url, str) and url.startswith(PREFIJO_DESCARGA)):
            continue                                     # solo archivos de las Releases de este repositorio
        if nombre == 'SHA256SUMS.txt':
            sumas = url
        elif nombre == nombre_instalador(texto_v, sistema, tipo):
            digest = a.get('digest')
            sha = digest[7:].lower() if isinstance(digest, str) and digest.lower().startswith('sha256:') else ''
            tamano = a.get('size') if isinstance(a.get('size'), int) and not isinstance(a.get('size'), bool) else 0
            instalador = Archivo(nombre, url, sha if _HEX64.fullmatch(sha) else '', tamano)
    return Novedad(texto_v, pagina, _recortar(notas), instalador), sumas


def leer_sumas(texto, nombre):
    """SHA-256 de `nombre` en un SHA256SUMS.txt (formato de sha256sum), o ''."""
    for linea in texto.splitlines():
        partes = linea.strip().split()
        if len(partes) == 2 and partes[1].lstrip('*') == nombre and _HEX64.fullmatch(partes[0].lower()):
            return partes[0].lower()
    return ''


def consultar(actual=__version__, sistema=SISTEMA):
    """La versión nueva publicada en GitHub con cambios para `sistema`, o None si no hay. Lanza
    ErrorActualizacion."""
    try:
        datos = json.loads(_leer(URL_API, MAX_RESPUESTA, 'application/vnd.github+json'))
        novedad, sumas = interpretar(datos, actual, sistema)
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
    """Windows: en la carpeta temporal del usuario. Linux: en su caché (~/.cache), y no en /tmp, que
    comparten todos los usuarios: el paquete ya comprobado no debe poder cambiarlo nadie antes de que lo
    instale el gestor de paquetes como administrador."""
    if LINUX:
        base = os.environ.get('XDG_CACHE_HOME', '')
        base = Path(base) if os.path.isabs(base) else Path.home() / '.cache'
        return base / 'bajar-subtitulos-esp' / 'actualizacion'
    return Path(tempfile.gettempdir()) / 'BajarSubtitulosESP-actualizacion'


def limpiar_descargas(carpeta=None):
    """Borra los instaladores de actualizaciones anteriores (el registro de la última se conserva)."""
    carpeta = Path(carpeta or carpeta_descargas())
    for f in carpeta.glob('*'):
        if f.suffix.lower() in ('.exe', '.deb', '.rpm', '.part'):
            try:
                f.unlink()
            except OSError:
                pass             # en uso (el instalador aún termina): la próxima vez


def _sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, 'rb') as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b''):
            h.update(bloque)
    return h.hexdigest()


def descargar(archivo, carpeta=None, progreso=None, cancelada=None):
    """Descarga `archivo` comprobando su SHA-256 mientras llega. Devuelve la ruta del archivo ya
    verificado; si no coincide, lo borra y lanza ErrorActualizacion. Si ya estaba descargado y comprobado
    (se reintenta tras cancelar la contraseña, por ejemplo), no se vuelve a descargar."""
    if not (archivo.sha256 and _DESCARGABLE.fullmatch(archivo.nombre)):
        raise ErrorActualizacion(tr('La actualización no tiene una huella SHA-256 con la que comprobarla.'))
    if carpeta is None and LINUX and archivo.nombre.endswith('.AppImage'):
        carpeta = _carpeta_appimage()       # junto al AppImage: luego se cambia por él de una vez (os.replace)
    carpeta = Path(carpeta or carpeta_descargas())
    carpeta.mkdir(parents=True, exist_ok=True)
    if LINUX and carpeta == carpeta_descargas():
        os.chmod(carpeta, 0o700)
    destino = carpeta / archivo.nombre
    try:
        if destino.is_file() and _sha256(destino) == archivo.sha256:
            return destino
    except OSError:
        pass
    parcial = destino.with_name('.' + destino.name + '.part')
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


def puede_instalarse():
    """True si esta copia se actualiza sola; si no, solo avisa y abre la página de descarga."""
    if WINDOWS:
        return instalada()
    return LINUX and not motivo_sin_instalar()


def motivo_sin_instalar():
    """Linux: por qué esta copia no puede actualizarse sola ('' si puede)."""
    tipo = tipo_linux()
    if tipo is None:
        return tr('Esta copia no se actualiza sola: descarga la nueva desde su página en GitHub.')
    if tipo == 'appimage':
        from .plataforma import linux
        carpeta = linux.appimage().parent
        if not os.access(carpeta, os.W_OK | os.X_OK):
            return tr('No se puede escribir en la carpeta del AppImage: descarga la nueva desde su página en '
                      'GitHub.')
        return ''
    if _orden_gestor(Path('paquete'), tipo) is None:
        return tr('No se encuentra cómo instalar el paquete (apt, dnf o zypper, y pkexec): descarga la nueva '
                  'desde su página en GitHub.')
    return ''


# ---------- Linux: instalar la actualización ----------

def tipo_linux():
    """Cómo se actualiza esta copia en Linux: 'deb', 'rpm', 'appimage', o None (el .tar.gz y el código
    fuente solo avisan)."""
    if not LINUX:
        return None
    from .plataforma import linux
    instalacion = linux.instalacion()
    if instalacion == 'appimage':
        return 'appimage'
    if instalacion == 'paquete':
        return linux.formato_paquete()
    return None


# pkexec termina con 126 si se cierra la ventana de la contraseña y con 127 si no se autoriza.
PKEXEC_CANCELADO = (126, 127)


def _orden_gestor(ruta, tipo):
    """La orden que instala el paquete `ruta` (con pkexec si no somos administrador), o None si falta algo.
    apt y dnf instalan encima de la versión anterior; zypper necesita que acepte un paquete sin firmar."""
    if tipo == 'deb':
        apt = shutil.which('apt-get')
        orden = [apt, 'install', '-y', str(ruta)] if apt else None
    elif tipo == 'rpm':
        dnf, zypper = shutil.which('dnf'), shutil.which('zypper')
        if dnf:
            orden = [dnf, 'install', '-y', str(ruta)]
        elif zypper:
            orden = [zypper, '--non-interactive', 'install', '--allow-unsigned-rpm', str(ruta)]
        else:
            orden = None
    else:
        orden = None
    if orden is None or os.geteuid() == 0:
        return orden
    pkexec = shutil.which('pkexec')
    return [pkexec] + orden if pkexec else None


def _carpeta_appimage():
    from .plataforma import linux
    appimage = linux.appimage()
    return appimage.parent if appimage else None


def nombre_appimage_nuevo(actual, version_nueva, version_actual=__version__):
    """El AppImage nuevo se llama como el que había, con la versión nueva si el nombre llevaba la suya."""
    actual = Path(actual)
    if version_actual in actual.name:
        return actual.with_name(actual.name.replace(version_actual, version_nueva))
    return actual


def instalar_linux(ruta, version_nueva, tipo=None):
    """Instala la actualización ya descargada y comprobada. Devuelve la orden con la que volver a abrir la
    app. Lanza Cancelada si se cierra la ventana de la contraseña y ErrorActualizacion si falla."""
    from . import menu_contextual
    tipo = tipo or tipo_linux()
    if tipo == 'appimage':
        from .plataforma import linux
        actual = linux.appimage()
        nuevo = nombre_appimage_nuevo(actual, version_nueva)
        try:
            os.chmod(ruta, 0o755)
            os.replace(ruta, nuevo)
            if nuevo != actual:
                actual.unlink(missing_ok=True)
        except OSError as e:
            raise ErrorActualizacion(tr('No se ha podido sustituir el AppImage ({error}).',
                                        error=e.strerror or e)) from e
        return [str(nuevo)]
    orden = _orden_gestor(ruta, tipo)
    if orden is None:
        raise ErrorActualizacion(motivo_sin_instalar())
    try:
        r = subprocess.run(orden, capture_output=True, text=True, errors='replace', timeout=1800,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as e:
        raise ErrorActualizacion(tr('No se ha podido abrir el gestor de paquetes ({error}).', error=e)) from e
    if r.returncode in PKEXEC_CANCELADO and Path(orden[0]).name == 'pkexec':
        raise Cancelada()
    if r.returncode != 0:
        detalle = [l.strip() for l in (r.stderr or r.stdout or '').splitlines() if l.strip()]
        raise ErrorActualizacion(tr('El gestor de paquetes no ha podido instalarla (código {codigo}): {detalle}',
                                    codigo=r.returncode, detalle=(detalle[-1] if detalle else '')[:300]))
    return menu_contextual.programa()


def modo_instalacion():
    """'usuario' o 'todos': dónde registró el instalador la desinstalación."""
    if not WINDOWS:
        return 'usuario'
    from .plataforma import windows
    return windows.desinstalacion_registrada(APP_ID) or 'usuario'


_mutex = {}


def crear_mutex():
    """Al arrancar: uno para que el instalador sepa que la app está abierta (AppMutex) y otro que dura
    hasta que el proceso termina (el instalador lo espera al actualizar)."""
    if not WINDOWS:
        return
    from .plataforma import windows
    for nombre in (MUTEX_INSTALADOR, MUTEX_PROCESO):
        _mutex[nombre] = windows.crear_mutex(nombre)[0]


def _soltar_mutex_instalador():
    """Para que el instalador no se pare con "la app está abierta": se cierra justo después."""
    h = _mutex.pop(MUTEX_INSTALADOR, None)
    if h and WINDOWS:
        from .plataforma import windows
        windows.cerrar(h)


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
    if WINDOWS:
        from .plataforma import windows
        flags = windows.INDEPENDIENTE
    subprocess.Popen(argumentos_instalador(ruta, modo or modo_instalacion(), registro), close_fds=True,
                     creationflags=flags, cwd=str(ruta.parent))
