"""Menú contextual del Explorador de Windows, en el registro (lo común está en app/menu_contextual.py).

- Clic derecho en una carpeta, en una unidad o en el fondo de una carpeta: «Bajar subtítulos aquí»,
  con un submenú «Solo esta carpeta» / «Esta carpeta y sus subcarpetas».
- Clic derecho en uno o varios vídeos: «Bajar subtítulos» y «Bajar subtítulos en inglés».
- Las opciones de las carpetas también están «en inglés».

Se registra en HKCU\\Software\\Classes: solo para este usuario y sin permisos de administrador. Es el
menú clásico: en Windows 11 aparece en «Mostrar más opciones» (el menú nuevo solo admite programas
empaquetados y firmados).

Se puede importar en cualquier sistema (winreg solo se usa al escribir o leer el registro): las pruebas
comprueban las entradas también en Linux.
"""
from pathlib import Path

from subtitulos.archivos import VIDEO_EXT
from subtitulos.idioma import tr

from ..menu_contextual import (ARG_ARCHIVOS, ARG_CARPETA, ARG_SUBCARPETAS, SUBMENU, SUBMENU_INGLES, TEXTO_ARCHIVOS,
                               TEXTO_ARCHIVOS_INGLES, TEXTO_CARPETA, en_ingles)

CLAVE = 'BajarSubtitulosESP'
CLAVE_INGLES = 'BajarSubtitulosESPIngles'     # «Bajar subtítulos en inglés» en los vídeos
RAIZ = r'Software\Classes'           # las pruebas lo cambian por una clave propia

# %V es la carpeta en las tres (en el fondo de una carpeta, %1 no existe).
CARPETAS = (r'Directory\shell', r'Directory\Background\shell', r'Drive\shell')

# Subclaves del submenú de las carpetas (el Explorador las ordena por nombre).
SUBCLAVES = {ARG_CARPETA: '1solo', ARG_SUBCARPETAS: '2todo'}
SUBCLAVES_INGLES = {ARG_CARPETA: '3solo-ingles', ARG_SUBCARPETAS: '4todo-ingles'}

# .ts también es la extensión de TypeScript: ahí el menú estorbaría (la app sí los busca en carpetas).
SIN_MENU = {'.ts'}


def _archivos(todas=False):
    exts = VIDEO_EXT if todas else VIDEO_EXT - SIN_MENU
    return [rf'SystemFileAssociations\{ext}\shell' for ext in sorted(exts)]


def comando(prog, argumento, variable):
    partes = ' '.join(f'"{p}"' if not p.startswith('-') else p for p in prog)
    return f'{partes} {argumento} "{variable}"'


def entradas(prog):
    """{subclave: {valor: dato}} de todo lo que se escribe (las subclaves, relativas a RAIZ)."""
    icono = {'Icon': f'"{prog[0]}",0'} if len(prog) == 1 else {}
    claves = {}
    for base in CARPETAS:
        k = rf'{base}\{CLAVE}'
        claves[k] = {'MUIVerb': tr(TEXTO_CARPETA), 'SubCommands': '', **icono}
        for texto, arg in SUBMENU:
            claves[rf'{k}\shell\{SUBCLAVES[arg]}'] = {'MUIVerb': tr(texto)}
            claves[rf'{k}\shell\{SUBCLAVES[arg]}\command'] = {'': comando(prog, arg, '%V')}
        for texto, arg in SUBMENU_INGLES:
            claves[rf'{k}\shell\{SUBCLAVES_INGLES[arg]}'] = {'MUIVerb': tr(texto)}
            claves[rf'{k}\shell\{SUBCLAVES_INGLES[arg]}\command'] = {'': comando(prog, en_ingles(arg), '%V')}
    for base in _archivos():
        # Player: que aparezca también con más de 15 vídeos seleccionados.
        for clave, texto, arg in ((CLAVE, TEXTO_ARCHIVOS, ARG_ARCHIVOS),
                                  (CLAVE_INGLES, TEXTO_ARCHIVOS_INGLES, en_ingles(ARG_ARCHIVOS))):
            k = rf'{base}\{clave}'
            claves[k] = {'MUIVerb': tr(texto), 'MultiSelectModel': 'Player', **icono}
            claves[rf'{k}\command'] = {'': comando(prog, arg, '%1')}
    return claves


def _raices():
    """Las claves superiores que pertenecen a la app (se borran enteras al quitar el menú)."""
    # Todas las extensiones: así también se borra lo que dejara una versión que las incluía.
    return ([rf'{base}\{CLAVE}' for base in CARPETAS + tuple(_archivos(todas=True))]
            + [rf'{base}\{CLAVE_INGLES}' for base in _archivos(todas=True)])


def registrar(prog):
    """Añade el menú (o lo rehace apuntando a `prog`). Lanza OSError si no se puede."""
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
    import winreg
    for sub in _raices():
        _borrar_arbol(winreg.HKEY_CURRENT_USER, rf'{RAIZ}\{sub}')
    _avisar_explorador()


def comando_registrado(subclave=None):
    """El comando de «Bajar subtítulos aquí › Solo esta carpeta» (u otra opción de ese submenú), o '' si
    el menú no está."""
    import winreg
    sub = rf'{RAIZ}\{CARPETAS[0]}\{CLAVE}\shell\{subclave or SUBCLAVES[ARG_CARPETA]}\command'
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


def al_dia(prog):
    """True si el menú es exactamente el que pondría `prog` (mismo programa y mismos argumentos; el de las
    versiones anteriores a la 3.0.0 no tenía las opciones «en inglés»)."""
    return (comando_registrado() == comando(prog, ARG_CARPETA, '%V') and
            comando_registrado(SUBCLAVES_INGLES[ARG_CARPETA]) == comando(prog, en_ingles(ARG_CARPETA), '%V'))


def misma(a, b):
    """Rutas iguales: en Windows no distinguen mayúsculas."""
    return str(a).casefold() == str(b).casefold()


def texto_registrado():
    """El texto de «Bajar subtítulos aquí» tal como está en el registro, o ''."""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf'{RAIZ}\{CARPETAS[0]}\{CLAVE}') as k:
            return winreg.QueryValueEx(k, 'MUIVerb')[0]
    except OSError:
        return ''


def retitular(prog):
    """Pone los textos del menú en el idioma de la app sin tocar los comandos (apunte a la copia que
    apunte). Solo cambia las claves que ya existen. Lanza OSError si no se puede."""
    import winreg
    for sub, valores in entradas(prog).items():
        if 'MUIVerb' not in valores:
            continue
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf'{RAIZ}\{sub}', 0, winreg.KEY_WRITE) as k:
                winreg.SetValueEx(k, 'MUIVerb', 0, winreg.REG_SZ, valores['MUIVerb'])
        except FileNotFoundError:
            pass
    _avisar_explorador()


def describir(prog):
    """Para la autoprueba."""
    return (f'{len(entradas(prog))} claves · registrado: {registrado()} · '
            f'comando: {comando(prog, ARG_CARPETA, "%V")}')


def _avisar_explorador():
    from .windows import avisar_explorador
    avisar_explorador()

