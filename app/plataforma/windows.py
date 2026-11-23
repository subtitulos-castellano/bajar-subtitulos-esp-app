"""Llamadas a Windows (kernel32, user32, shell32 y el registro). Solo se usa en Windows."""
import ctypes
import subprocess
from ctypes import wintypes

ERROR_ALREADY_EXISTS = 183

# Procesos que siguen aunque la app se cierre (el instalador al actualizar, la app al volver a abrirse).
INDEPENDIENTE = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)


def _kernel32():
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateMutexW.restype = wintypes.HANDLE
    k32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    return k32


def crear_mutex(nombre):
    """(handle, ya_existía). Windows lo suelta solo al terminar el proceso, aunque sea de golpe."""
    h = _kernel32().CreateMutexW(None, False, nombre)
    return h, ctypes.get_last_error() == ERROR_ALREADY_EXISTS


def cerrar(handle):
    if handle:
        _kernel32().CloseHandle(handle)


def id_de_app(id_app):
    """Para que Windows agrupe la app en la barra de tareas con su propio icono."""
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(id_app)


def permitir_primer_plano():
    """Deja a otro proceso (la app ya abierta) ponerse delante: Windows solo deja hacerlo a quien tiene
    el foco, que es este proceso recién lanzado."""
    ASFW_ANY = -1
    ctypes.windll.user32.AllowSetForegroundWindow(ASFW_ANY)


def avisar_explorador():
    """Para que el Explorador vea un cambio en el menú contextual sin reiniciarse."""
    try:
        SHCNE_ASSOCCHANGED, SHCNF_IDLIST = 0x08000000, 0
        ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
    except (AttributeError, OSError):
        pass


def escala_texto():
    """Porcentaje de Configuración › Accesibilidad › Tamaño del texto (100-225). 100 si no se puede leer."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Accessibility') as k:
            valor, _ = winreg.QueryValueEx(k, 'TextScaleFactor')
        return min(225, max(100, int(valor)))
    except (OSError, ValueError, TypeError):
        return 100


def desinstalacion_registrada(app_id):
    """'usuario' o 'todos': dónde registró el instalador (Inno Setup) la desinstalación; None si en
    ninguno."""
    import winreg
    clave = rf'Software\Microsoft\Windows\CurrentVersion\Uninstall\{app_id}_is1'
    for raiz, modo in ((winreg.HKEY_CURRENT_USER, 'usuario'), (winreg.HKEY_LOCAL_MACHINE, 'todos')):
        try:
            winreg.OpenKey(raiz, clave).Close()
            return modo
        except OSError:
            pass
    return None
