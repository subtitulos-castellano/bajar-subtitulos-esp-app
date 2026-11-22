"""Menú contextual del Explorador de Windows.

- Clic derecho en una carpeta, en una unidad o en el fondo de una carpeta: «Bajar subtítulos aquí»,
  con un submenú «Solo esta carpeta» / «Esta carpeta y sus subcarpetas».
- Clic derecho en uno o varios vídeos: «Bajar subtítulos».

Se registra en HKCU\\Software\\Classes: solo para este usuario y sin permisos de administrador. Es el
menú clásico: en Windows 11 aparece en «Mostrar más opciones» (el menú nuevo solo admite programas
empaquetados y firmados).

Con varios vídeos seleccionados, el Explorador abre la app una vez por vídeo: la primera recoge los de
las demás y lo busca todo junto (ver instancia.py).
"""
import sys
from pathlib import Path

from subtitulos.archivos import VIDEO_EXT

CLAVE = 'BajarSubtitulosESP'
RAIZ = r'Software\Classes'           # las pruebas lo cambian por una clave propia

# Argumentos que reciben la app desde el menú.
ARG_CARPETA = '--menu-carpeta'              # solo los vídeos de la propia carpeta
ARG_SUBCARPETAS = '--menu-subcarpetas'      # la carpeta y sus subcarpetas
ARG_ARCHIVOS = '--menu-archivos'            # un vídeo (uno por proceso si se seleccionan varios)

TEXTO_CARPETA = 'Bajar subtítulos aquí'
TEXTO_ARCHIVOS = 'Bajar subtítulos'
SUBMENU = (('1solo', 'Solo esta carpeta', ARG_CARPETA),
           ('2todo', 'Esta carpeta y sus subcarpetas', ARG_SUBCARPETAS))

# %V es la carpeta en las tres (en el fondo de una carpeta, %1 no existe).
CARPETAS = (r'Directory\shell', r'Directory\Background\shell', r'Drive\shell')


# .ts también es la extensión de TypeScript: ahí el menú estorbaría (la app sí los busca en carpetas).
SIN_MENU = {'.ts'}


def _archivos(todas=False):
    exts = VIDEO_EXT if todas else VIDEO_EXT - SIN_MENU
    return [rf'SystemFileAssociations\{ext}\shell' for ext in sorted(exts)]


def disponible():
    return sys.platform == 'win32'


def programa():
    """Lo que hay que ejecutar: el .exe; desde el código fuente, pythonw.exe con app/main.py."""
    if getattr(sys, 'frozen', False):
        return [str(Path(sys.executable))]
    python = Path(sys.executable)
    pythonw = python.with_name('pythonw.exe')
    return [str(pythonw if pythonw.is_file() else python), '-I',
            str(Path(__file__).resolve().parent / 'main.py')]


def comando(argumento, variable, prog=None):
    partes = ' '.join(f'"{p}"' if not p.startswith('-') else p for p in (prog or programa()))
    return f'{partes} {argumento} "{variable}"'


def entradas(prog=None):
    """{subclave: {valor: dato}} de todo lo que se escribe (las subclaves, relativas a RAIZ)."""
    prog = prog or programa()
    icono = {'Icon': f'"{prog[0]}",0'} if len(prog) == 1 else {}
    claves = {}
    for base in CARPETAS:
        k = rf'{base}\{CLAVE}'
        claves[k] = {'MUIVerb': TEXTO_CARPETA, 'SubCommands': '', **icono}
        for nombre, texto, arg in SUBMENU:
            claves[rf'{k}\shell\{nombre}'] = {'MUIVerb': texto}
            claves[rf'{k}\shell\{nombre}\command'] = {'': comando(arg, '%V', prog)}
    for base in _archivos():
        k = rf'{base}\{CLAVE}'
        # Player: que aparezca también con más de 15 vídeos seleccionados.
        claves[k] = {'MUIVerb': TEXTO_ARCHIVOS, 'MultiSelectModel': 'Player', **icono}
        claves[rf'{k}\command'] = {'': comando(ARG_ARCHIVOS, '%1', prog)}
    return claves


def _raices():
    """Las claves superiores que pertenecen a la app (se borran enteras al quitar el menú)."""
    # Todas las extensiones: así también se borra lo que dejara una versión que las incluía.
    return [rf'{base}\{CLAVE}' for base in CARPETAS + tuple(_archivos(todas=True))]


def registrar(prog=None):
    """Añade el menú (o lo rehace apuntando a este programa). Lanza OSError si no se puede."""
    import winreg
    quitar()
    for sub, valores in entradas(prog).items():
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, rf'{RAIZ}\{sub}', 0, winreg.KEY_WRITE) as k:
            for nombre, dato in valores.items():
                winreg.SetValueEx(k, nombre, 0, winreg.REG_SZ, dato)
    _avisar_explorador()


def _borrar_arbol(raiz, sub):
    import winreg
    try:
        with winreg.OpenKey(raiz, sub, 0, winreg.KEY_READ | winreg.KEY_WRITE) as k:
            while True:
                try:
                    hija = winreg.EnumKey(k, 0)
                except OSError:
                    break
                _borrar_arbol(raiz, rf'{sub}\{hija}')
        winreg.DeleteKey(raiz, sub)
    except FileNotFoundError:
        pass


def quitar():
    """Quita el menú. Lanza OSError si no se puede."""
    if not disponible():
        return
    import winreg
    for sub in _raices():
        _borrar_arbol(winreg.HKEY_CURRENT_USER, rf'{RAIZ}\{sub}')
    _avisar_explorador()


def comando_registrado():
    """El comando de «Bajar subtítulos aquí › Solo esta carpeta», o '' si el menú no está."""
    if not disponible():
        return ''
    import winreg
    sub = rf'{RAIZ}\{CARPETAS[0]}\{CLAVE}\shell\{SUBMENU[0][0]}\command'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub) as k:
            return winreg.QueryValueEx(k, '')[0]
    except OSError:
        return ''


def registrado():
    return bool(comando_registrado())


def programa_registrado():
    """Ruta del programa al que apunta el menú (el primer elemento entre comillas), o None."""
    c = comando_registrado()
    if not c.startswith('"'):
        return None
    return Path(c[1:].split('"', 1)[0])


def es_de(prog=None):
    """True si el menú apunta a este programa."""
    actual = programa_registrado()
    return actual is not None and _misma(actual, Path((prog or programa())[0]))


def _misma(a, b):
    return str(a).casefold() == str(b).casefold()


def asegurar(config, instalada, prog=None):
    """Al abrir la app (y al instalarla): deja el menú como dice la configuración.

    - Sin decidir (None): la versión instalada lo añade; la portable no (se activa en Configuración).
    - Activado: si apunta a otro programa que ya no existe (se movió la portable o se reinstaló en otra
      carpeta), se rehace apuntando a este. Si apunta a otro que sí existe, se respeta.
    - Desactivado: no se toca.
    Devuelve True si ha cambiado algo. Nunca lanza: el menú no debe impedir abrir la app."""
    if not disponible():
        return False
    try:
        if config.menu_contextual is None:
            if not instalada:
                return False
            registrar(prog)
            config.menu_contextual = True
            config.guardar()
            return True
        if config.menu_contextual:
            actual = programa_registrado()
            if (actual is None or not actual.exists()
                    or (es_de(prog) and comando_registrado() != comando(ARG_CARPETA, '%V', prog))):
                registrar(prog)
                return True
    except OSError:
        pass
    return False


def _avisar_explorador():
    """Para que el Explorador vea el cambio sin reiniciarse."""
    try:
        import ctypes
        SHCNE_ASSOCCHANGED, SHCNF_IDLIST = 0x08000000, 0
        ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
    except (AttributeError, OSError):
        pass


def ruta_de_argumento(texto):
    """La ruta que pasa el Explorador. En la raíz de una unidad llega «D:"» en vez de «D:\\»: la barra
    final de "%V" escapa la comilla de cierre."""
    texto = texto.strip().strip('"')
    if len(texto) == 2 and texto[1] == ':':
        texto += '\\'
    return Path(texto)
