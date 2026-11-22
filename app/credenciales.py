"""Cuenta de opensubtitles.org: el usuario va en config.json y la contraseña en el
Administrador de credenciales de Windows (librería keyring), nunca en texto plano.
"""
import json

from subtitulos.archivos import HOME
from subtitulos.idioma import tr

SERVICIO = 'BajarSubtitulosESP/opensubtitles'


def _keyring():
    try:
        import keyring
        return keyring
    except Exception:  # noqa: BLE001 - sin keyring la app funciona, solo sin OpenSubtitles
        return None


def leer_clave(usuario):
    kr = _keyring()
    if not (kr and usuario):
        return ''
    try:
        return kr.get_password(SERVICIO, usuario) or ''
    except Exception:  # noqa: BLE001
        return ''


def guardar_clave(usuario, clave, usuario_anterior=''):
    """Guarda la contraseña (o la borra si está vacía). Devuelve False si no se pudo."""
    kr = _keyring()
    if not kr:
        return False
    try:
        if usuario_anterior and usuario_anterior != usuario:
            borrar_clave(usuario_anterior)
        if usuario and clave:
            kr.set_password(SERVICIO, usuario, clave)
        elif usuario:
            borrar_clave(usuario)
        return True
    except Exception:  # noqa: BLE001
        return False


def borrar_clave(usuario):
    kr = _keyring()
    if kr and usuario:
        try:
            kr.delete_password(SERVICIO, usuario)
        except Exception:  # noqa: BLE001 - no existía
            pass


def credenciales_proveedores(usuario):
    """Configuración para procesar(): {'opensubtitles': {...}} o {} si no hay cuenta completa."""
    clave = leer_clave(usuario)
    if usuario and clave:
        return {'opensubtitles': {'username': usuario, 'password': clave}}
    return {}


def credenciales_skill():
    """(usuario, contraseña) del credenciales.json de la skill, si existe y es válido."""
    try:
        datos = json.loads((HOME / 'credenciales.json').read_text(encoding='utf-8'))
        os_ = datos['opensubtitles']
        if isinstance(os_.get('username'), str) and isinstance(os_.get('password'), str):
            return os_['username'], os_['password']
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    return None


def probar(usuario, clave):
    """Inicia sesión en opensubtitles.org. Devuelve (correcto, mensaje). Usa la red: llamar en un hilo."""
    try:
        from subliminal.providers.opensubtitles import OpenSubtitlesProvider
    except Exception as e:  # noqa: BLE001
        return False, tr('No se pudo cargar el proveedor: {error}', error=e)
    proveedor = OpenSubtitlesProvider(usuario, clave)
    try:
        proveedor.initialize()
    except Exception as e:  # noqa: BLE001
        nombre = type(e).__name__
        if 'Authentication' in nombre or 'Unauthorized' in nombre:
            return False, tr('Usuario o contraseña incorrectos.')
        return False, tr('No se pudo conectar ({error}). Revisa la conexión a internet.', error=nombre)
    try:
        proveedor.terminate()
    except Exception:  # noqa: BLE001 - el servidor ya no tiene el método de cierre de sesión
        pass
    return True, tr('Conexión correcta.')
