"""Cuentas de OpenSubtitles: opensubtitles.org y opensubtitles.com (son cuentas distintas). El usuario va
en config.json y la contraseña en el llavero del sistema (librería keyring), nunca en texto plano: en
Windows, el Administrador de credenciales; en Linux, el Secret Service (KWallet o GNOME Keyring).

Cada cuenta se identifica por el nombre de su proveedor en subliminal, el mismo que usa el
credenciales.json de la skill: 'opensubtitles' (.org) y 'opensubtitlescom' (.com).

En Linux el llavero puede estar bloqueado y pedir su contraseña en otra ventana (o no contestar nunca,
si no hay quien la pida). Para que la app no se quede congelada, cada operación va en un hilo y se
espera como mucho PLAZO segundos: si no ha terminado, sigue en segundo plano y, cuando termina, avisa
(al_terminar) para que la ventana se ponga al día. Lo leído se recuerda durante la sesión.
"""
import json
import threading

from subtitulos.archivos import HOME
from subtitulos.idioma import tr

from .plataforma import WINDOWS

ORG, COM = 'opensubtitles', 'opensubtitlescom'
CUENTAS = (ORG, COM)
SERVICIOS = {ORG: 'BajarSubtitulosESP/opensubtitles', COM: 'BajarSubtitulosESP/opensubtitlescom'}
SERVICIO = SERVICIOS[ORG]


PLAZO = 2.0               # segundos que se espera al llavero (fuera de Windows) antes de seguir sin él
PENDIENTE = 'pendiente'   # guardar_clave: el llavero aún no ha contestado (lo hará en segundo plano)

_lock = threading.Lock()
_leidas = {}              # (cuenta, usuario) -> contraseña ('' si no hay): lo ya leído en esta sesión
_en_curso = {}            # (cuenta, usuario) -> hilo que la está leyendo
_avisos = []              # funciones a las que avisar cuando el llavero contesta tarde


def _keyring():
    try:
        import keyring
        return keyring
    except Exception:  # noqa: BLE001 - sin keyring la app funciona, solo sin OpenSubtitles
        return None


def disponible():
    """False si el sistema no tiene llavero donde guardar contraseñas (en Linux, sin Secret Service)."""
    kr = _keyring()
    if not kr:
        return False
    try:
        from keyring.backends import fail
        return not isinstance(kr.get_keyring(), fail.Keyring)
    except Exception:  # noqa: BLE001
        return False


def olvidar():
    """Olvida lo leído en esta sesión (para las pruebas)."""
    with _lock:
        _leidas.clear()


def al_terminar(funcion):
    """Llama a `funcion()` (desde otro hilo) cuando una operación que tardaba termina."""
    _avisos.append(funcion)


def _avisar():
    for f in list(_avisos):
        try:
            f()
        except Exception:  # noqa: BLE001 - p. ej., una ventana que ya no existe
            pass


def _leer(usuario, cuenta):
    kr = _keyring()
    if not kr:
        return ''
    try:
        return kr.get_password(SERVICIOS[cuenta], usuario) or ''
    except Exception:  # noqa: BLE001
        return ''


def leer_clave(usuario, cuenta=ORG):
    if not usuario:
        return ''
    if WINDOWS:
        return _leer(usuario, cuenta)
    clave = (cuenta, usuario)
    with _lock:
        if clave in _leidas:
            return _leidas[clave]
        hilo = _en_curso.get(clave)
        esperar = hilo is None           # si ya había una lectura en curso, no se vuelve a esperar
        if esperar:
            def leer():
                valor = _leer(usuario, cuenta)
                with _lock:
                    _leidas[clave] = valor
                    _en_curso.pop(clave, None)
                    tarde = getattr(threading.current_thread(), 'tarde', False)
                if tarde:
                    _avisar()
            hilo = threading.Thread(target=leer, name='llavero', daemon=True)
            _en_curso[clave] = hilo
            hilo.start()
    if esperar:
        hilo.join(PLAZO)
    with _lock:
        if clave in _leidas:
            return _leidas[clave]
        hilo.tarde = True                # cuando conteste, que avise
    return ''


def _escribir(usuario, clave, usuario_anterior, cuenta):
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


def guardar_clave(usuario, clave, usuario_anterior='', cuenta=ORG):
    """Guarda la contraseña (o la borra si está vacía). Devuelve True, False si no se pudo o, fuera de
    Windows, PENDIENTE si el llavero aún no ha contestado (al terminar, avisa: ver al_terminar)."""
    if WINDOWS:
        return _escribir(usuario, clave, usuario_anterior, cuenta)
    resultado = []

    def escribir():
        ok = _escribir(usuario, clave, usuario_anterior, cuenta)
        with _lock:
            if ok:
                _leidas[(cuenta, usuario)] = clave if usuario and clave else ''
                if usuario_anterior and usuario_anterior != usuario:
                    _leidas[(cuenta, usuario_anterior)] = ''
            resultado.append(ok)
            tarde = getattr(threading.current_thread(), 'tarde', False)
        if tarde:
            _avisar()
    hilo = threading.Thread(target=escribir, name='llavero', daemon=True)
    hilo.start()
    hilo.join(PLAZO)
    with _lock:
        if resultado:
            return resultado[0]
        hilo.tarde = True
    return PENDIENTE


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
