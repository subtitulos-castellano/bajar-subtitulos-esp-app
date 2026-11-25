"""El modelo de traducción inglés → español (para traducir.py): dónde está y cómo se descarga.

No va dentro del programa (ocupa unos 200 MB): se descarga la primera vez que se traduce, de la Release
`MODELO_TAG` de este mismo repositorio, comprobando su SHA-256, y se guarda en
~/.subtitulos-esp/modelos/<NOMBRE>. Lo publica el workflow .github/workflows/modelo.yml a partir del
modelo Opus-MT «opus-mt-tc-big-en-es» (Universidad de Helsinki, licencia CC-BY 4.0), convertido para
CTranslate2 (int8).

Solo usa la biblioteca estándar.
"""
import hashlib
import os
import shutil
import ssl
import urllib.request
import zipfile
from pathlib import Path

from .archivos import HOME
from .idioma import tr

NOMBRE = 'traductor-en-es-1'
MODELO_TAG = 'traductor-en-es-1'
URL = f'https://github.com/subtitulos-castellano/bajar-subtitulos-esp-app/releases/download/{MODELO_TAG}/{NOMBRE}.zip'
SHA256 = 'PENDIENTE'
TAMANO = 0                       # bytes del .zip (para la barra de progreso y el aviso)
TAMANO_MAX = 400 * 1024 * 1024   # nunca se descarga ni se descomprime más que esto
# Lo único que se saca del .zip (nada de rutas: cada uno va directo a la carpeta del modelo).
ARCHIVOS = ('config.json', 'model.bin', 'shared_vocabulary.json', 'source.spm', 'target.spm', 'LICENSE.txt',
            'LEEME.txt')
_COMPLETO = '.completo'          # se escribe al final: sin él, la carpeta está a medias


class ErrorModelo(Exception):
    """No se ha podido descargar o preparar el modelo (el mensaje ya está en el idioma de la app)."""


class Cancelado(Exception):
    pass


def carpeta():
    return HOME / 'modelos' / NOMBRE


def instalado(ruta=None):
    ruta = Path(ruta) if ruta else carpeta()
    return (ruta / _COMPLETO).is_file() and all((ruta / a).is_file() for a in ARCHIVOS)


def tamano_mb():
    return round(TAMANO / 1e6) if TAMANO else 200


def _contexto_ssl():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001 - sin certifi, los certificados del sistema
        return ssl.create_default_context()


def descargar(progreso=None, cancelado=None, url=URL, sha256=SHA256, destino=None):
    """Descarga y prepara el modelo. `progreso(hecho, total)` en bytes; `cancelado()` → True para parar
    (lanza Cancelado). Lanza ErrorModelo si falla. Si ya está, no hace nada."""
    destino = Path(destino) if destino else carpeta()
    if instalado(destino):
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.parent / f'.{destino.name}.zip.part'
    temporal = destino.parent / f'.{destino.name}.tmp'
    h, hecho = hashlib.sha256(), 0
    try:
        try:
            peticion = urllib.request.Request(url, headers={'User-Agent': 'BajarSubtitulosESP'})
            with urllib.request.urlopen(peticion, timeout=60, context=_contexto_ssl()) as r, \
                    open(parcial, 'wb') as f:
                total = TAMANO or int(r.headers.get('Content-Length') or 0)
                while True:
                    if cancelado and cancelado():
                        raise Cancelado()
                    bloque = r.read(256 * 1024)
                    if not bloque:
                        break
                    hecho += len(bloque)
                    if hecho > TAMANO_MAX:
                        raise ErrorModelo(tr('El traductor descargado es demasiado grande: no se ha guardado.'))
                    h.update(bloque)
                    f.write(bloque)
                    if progreso:
                        progreso(hecho, max(total, hecho))
        except (ErrorModelo, Cancelado):
            raise
        except (OSError, ValueError) as e:
            raise ErrorModelo(tr('No se ha podido descargar el traductor. Comprueba la conexión a internet.')) from e
        if h.hexdigest() != sha256:
            raise ErrorModelo(tr('El traductor descargado no coincide con su huella SHA-256: no se ha guardado.'))
        shutil.rmtree(temporal, ignore_errors=True)
        temporal.mkdir()
        try:
            with zipfile.ZipFile(parcial) as z:
                for nombre in ARCHIVOS:
                    info = z.getinfo(nombre)
                    if info.file_size > TAMANO_MAX:
                        raise ErrorModelo(tr('El traductor descargado está dañado.'))
                    with z.open(info) as origen, open(temporal / nombre, 'wb') as salida:
                        shutil.copyfileobj(origen, salida, 1024 * 1024)
        except (KeyError, zipfile.BadZipFile, OSError) as e:
            raise ErrorModelo(tr('El traductor descargado está dañado.')) from e
        (temporal / _COMPLETO).write_text(NOMBRE, encoding='utf-8')
        shutil.rmtree(destino, ignore_errors=True)
        os.replace(temporal, destino)
    except BaseException:
        shutil.rmtree(temporal, ignore_errors=True)
        raise
    finally:
        try:
            parcial.unlink()
        except OSError:
            pass
    return destino


def borrar():
    """Quita el modelo descargado (Configuración: liberar espacio)."""
    shutil.rmtree(carpeta(), ignore_errors=True)


def motor(ruta=None):
    """El traductor listo para usar (traducir.Motor). Lanza ErrorModelo si el modelo no está o no carga."""
    ruta = Path(ruta) if ruta else carpeta()
    if not instalado(ruta):
        raise ErrorModelo(tr('Falta el traductor: se descarga al elegir «Castellano traducido del inglés» '
                             'en Configuración.'))
    from .traducir import Motor
    try:
        return Motor(ruta)
    except Exception as e:  # noqa: BLE001 - bibliotecas que no cargan o modelo dañado
        raise ErrorModelo(tr('No se ha podido cargar el traductor: {error}', error=e)) from e
