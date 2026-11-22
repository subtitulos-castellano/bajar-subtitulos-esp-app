"""Cuentas de OpenSubtitles: opensubtitles.org y opensubtitles.com (son cuentas distintas). El usuario va
en config.json y la contraseña en el Administrador de credenciales de Windows (librería keyring), nunca
en texto plano.

Cada cuenta se identifica por el nombre de su proveedor en subliminal, el mismo que usa el
credenciales.json de la skill: 'opensubtitles' (.org) y 'opensubtitlescom' (.com).
"""
import json

from subtitulos.archivos import HOME
from subtitulos.idioma import tr

ORG, COM = 'opensubtitles', 'opensubtitlescom'
CUENTAS = (ORG, COM)
SERVICIOS = {ORG: 'BajarSubtitulosESP/opensubtitles', COM: 'BajarSubtitulosESP/opensubtitlescom'}
SERVICIO = SERVICIOS[ORG]


def _keyring():
    try:
        import keyring
        return keyring
    except Exception:  # noqa: BLE001 - sin keyring la app funciona, solo sin OpenSubtitles
        return None


def leer_clave(usuario, cuenta=ORG):
    kr = _keyring()
    if not (kr and usuario):
        return ''
    try:
        return kr.get_password(SERVICIOS[cuenta], usuario) or ''
    except Exception:  # noqa: BLE001
        return ''


def guardar_clave(usuario, clave, usuario_anterior='', cuenta=ORG):
    """Guarda la contraseña (o la borra si está vacía). Devuelve False si no se pudo."""
    kr = _keyring()
    if not kr:
        return False
    try:
        if usuario_anterior and usuario_anterior != usuario:
            borrar_clave(usuario_anterior, cuenta)
        if usuario and clave:
            kr.set_password(SERVICIOS[cuenta], usuario, clave)
        elif usuario:
            borrar_clave(usuario, cuenta)
        return True
    except Exception:  # noqa: BLE001
        return False


def borrar_clave(usuario, cuenta=ORG):
    kr = _keyring()
    if kr and usuario:
        try:
            kr.delete_password(SERVICIOS[cuenta], usuario)
        except Exception:  # noqa: BLE001 - no existía
            pass


def credenciales_proveedores(usuario, usuario_com=''):
    """Configuración para procesar(): {'opensubtitles': {...}, 'opensubtitlescom': {...}}, solo con las
    cuentas completas (usuario y contraseña guardada)."""
    configs = {}
    for cuenta, u in ((ORG, usuario), (COM, usuario_com)):
        clave = leer_clave(u, cuenta)
        if u and clave:
            configs[cuenta] = {'username': u, 'password': clave}
    return configs


def credenciales_skill(cuenta=ORG):
    """(usuario, contraseña) de esa cuenta en el credenciales.json de la skill, si existe y es válido."""
    try:
        datos = json.loads((HOME / 'credenciales.json').read_text(encoding='utf-8'))
        c = datos[cuenta]
        if isinstance(c.get('username'), str) and isinstance(c.get('password'), str):
            return c['username'], c['password']
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    return None


def probar(usuario, clave, cuenta=ORG):
    """Inicia sesión. Devuelve (correcto, mensaje). Usa la red: llamar en un hilo."""
    try:
        from subtitulos.nucleo import preparar_cache
        preparar_cache()                 # .com guarda ahí la sesión
        if cuenta == COM:
            from subliminal.providers.opensubtitlescom import OpenSubtitlesComProvider as Proveedor
        else:
            from subliminal.providers.opensubtitles import OpenSubtitlesProvider as Proveedor
    except Exception as e:  # noqa: BLE001
        return False, tr('No se pudo cargar el proveedor: {error}', error=e)
    proveedor = Proveedor(usuario, clave)
    try:
        proveedor.initialize()
        if cuenta == COM:
            proveedor.login()            # en .com, initialize() no inicia sesión hasta la primera consulta
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
