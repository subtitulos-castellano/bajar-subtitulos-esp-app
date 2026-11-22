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
from subtitulos.idioma import N_, tr

CLAVE = 'BajarSubtitulosESP'
RAIZ = r'Software\Classes'           # las pruebas lo cambian por una clave propia

# Argumentos que reciben la app desde el menú.
ARG_CARPETA = '--menu-carpeta'              # solo los vídeos de la propia carpeta
ARG_SUBCARPETAS = '--menu-subcarpetas'      # la carpeta y sus subcarpetas
ARG_ARCHIVOS = '--menu-archivos'            # un vídeo (uno por proceso si se seleccionan varios)

# Textos del menú, en el idioma de la app (si cambia, asegurar() los rehace al abrirla).
TEXTO_CARPETA = N_('Bajar subtítulos aquí')
TEXTO_ARCHIVOS = N_('Bajar subtítulos')
SUBMENU = (('1solo', N_('Solo esta carpeta'), ARG_CARPETA),
           ('2todo', N_('Esta carpeta y sus subcarpetas'), ARG_SUBCARPETAS))

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
        claves[k] = {'MUIVerb': tr(TEXTO_CARPETA), 'SubCommands': '', **icono}
        for nombre, texto, arg in SUBMENU:
            claves[rf'{k}\shell\{nombre}'] = {'MUIVerb': tr(texto)}
            claves[rf'{k}\shell\{nombre}\command'] = {'': comando(arg, '%V', prog)}
    for base in _archivos():
        k = rf'{base}\{CLAVE}'
        # Player: que aparezca también con más de 15 vídeos seleccionados.
        claves[k] = {'MUIVerb': tr(TEXTO_ARCHIVOS), 'MultiSelectModel': 'Player', **icono}
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


def texto_registrado():
    """El texto de «Bajar subtítulos aquí» tal como está en el registro, o ''."""
    if not disponible():
        return ''
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf'{RAIZ}\{CARPETAS[0]}\{CLAVE}') as k:
            return winreg.QueryValueEx(k, 'MUIVerb')[0]
    except OSError:
        return ''


def retitular():
    """Pone los textos del menú en el idioma de la app sin tocar los comandos (apunte a la copia que
    apunte). Solo cambia las claves que ya existen. Lanza OSError si no se puede."""
    import winreg
    for sub, valores in entradas().items():
        if 'MUIVerb' not in valores:
            continue
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf'{RAIZ}\{sub}', 0, winreg.KEY_WRITE) as k:
                winreg.SetValueEx(k, 'MUIVerb', 0, winreg.REG_SZ, valores['MUIVerb'])
        except FileNotFoundError:
            pass
    _avisar_explorador()


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
    """Al abrir la app: deja el menú como dice la configuración. La versión instalada manda; la
    portable solo lo añade con el interruptor de Configuración.

    - Si apunta a un programa que ya no existe (se borró o se movió esa copia): con el menú activado,
      se rehace apuntando a este; si no, se quita.
    - Sin decidir (None): la instalada lo añade; la portable no.
    - Activado: si falta, la instalada lo añade (la portable no). Si apunta a otra copia que sí
      existe, se respeta; si apunta a esta con otro comando, se rehace.
    - Desactivado: no se añade.
    - Si está, con los textos en otro idioma (se ha cambiado en Configuración): se traducen.
    Devuelve True si ha cambiado algo. Nunca lanza: el menú no debe impedir abrir la app."""
    if not disponible():
        return False
    try:
        actual = programa_registrado()
        if actual is not None and not actual.exists():
            if config.menu_contextual:
                registrar(prog)
            else:
                quitar()
            return True
        if config.menu_contextual is None:
            if not instalada:
                return False
            registrar(prog)
            config.menu_contextual = True
            config.guardar()
            return True
        if config.menu_contextual:
            if actual is None:
                if instalada:
                    registrar(prog)
                    return True
            elif es_de(prog) and comando_registrado() != comando(ARG_CARPETA, '%V', prog):
                registrar(prog)
                return True
        if actual is not None and texto_registrado() != tr(TEXTO_CARPETA):
            retitular()
            return True
    except OSError:
        pass
    return False


def al_instalar(config, prog=None):
    """El instalador (también al actualizar) se queda con el menú, aunque apunte a una portable,
    salvo que se haya desactivado en Configuración. Lanza OSError si no se puede."""
    if not disponible() or config.menu_contextual is False:
        return False
    registrar(prog)
    if config.menu_contextual is not True:
        config.menu_contextual = True
        config.guardar()
    return True


def al_desinstalar(config):
    """El desinstalador quita el menú, apunte a la copia que apunte, y lo deja sin decidir: así una
    portable no lo vuelve a añadir sola, y si se vuelve a instalar, el instalador lo añade.
    (Si se había desactivado en Configuración, sigue desactivado.) Lanza OSError si no se puede."""
    if not disponible():
        return
    quitar()
    if config.menu_contextual:
        config.menu_contextual = None
        config.guardar()


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
