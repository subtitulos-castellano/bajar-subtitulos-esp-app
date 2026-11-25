"""Menú contextual «Bajar subtítulos» del explorador de archivos: qué hay que hacer y cuándo.

Cómo se pone en cada sistema está en app/plataforma (en Windows, menu_windows.py: el registro; en Linux,
menu_linux.py: Dolphin, Nautilus y Nemo).

- En una carpeta: «Bajar subtítulos aquí», con un submenú «Solo esta carpeta» / «Esta carpeta y sus
  subcarpetas», y lo mismo «en inglés».
- En uno o varios vídeos: «Bajar subtítulos» y «Bajar subtítulos en inglés».

Las opciones «en inglés» buscan solo inglés (como «Solo inglés» en Configuración) sin cambiar la
configuración: añaden ARG_INGLES delante del argumento de siempre.

Con varios vídeos seleccionados, el Explorador de Windows abre la app una vez por vídeo: la primera recoge
los de las demás y lo busca todo junto (ver instancia.py). Los gestores de archivos de Linux los pasan
todos a una sola apertura.
"""
import os
import sys
from pathlib import Path

from subtitulos.idioma import N_, tr

from .plataforma import LINUX, WINDOWS

# Argumentos que reciben la app desde el menú.
ARG_CARPETA = '--menu-carpeta'              # solo los vídeos de la propia carpeta
ARG_SUBCARPETAS = '--menu-subcarpetas'      # la carpeta y sus subcarpetas
ARG_ARCHIVOS = '--menu-archivos'            # vídeos (en Windows, uno por proceso si se seleccionan varios)
ARG_INGLES = '--menu-ingles'                # delante de uno de los anteriores: solo inglés

# Textos del menú, en el idioma de la app (si cambia, asegurar() los rehace al abrirla).
TEXTO_CARPETA = N_('Bajar subtítulos aquí')
TEXTO_ARCHIVOS = N_('Bajar subtítulos')
SUBMENU = ((N_('Solo esta carpeta'), ARG_CARPETA),
           (N_('Esta carpeta y sus subcarpetas'), ARG_SUBCARPETAS))
TEXTO_SOLO_CARPETA = N_('Bajar subtítulos (solo esta carpeta)')     # Nautilus (sin submenús)
TEXTO_ARCHIVOS_INGLES = N_('Bajar subtítulos en inglés')
SUBMENU_INGLES = ((N_('Solo esta carpeta, en inglés'), ARG_CARPETA),
                  (N_('Esta carpeta y sus subcarpetas, en inglés'), ARG_SUBCARPETAS))
TEXTO_SOLO_CARPETA_INGLES = N_('Bajar subtítulos en inglés (solo esta carpeta)')   # Nautilus


def en_ingles(argumento):
    """El argumento de una opción «en inglés»: '--menu-ingles --menu-carpeta'."""
    return f'{ARG_INGLES} {argumento}'


def _sistema():
    """El módulo que pone el menú en este sistema, o None si aquí no hay menú."""
    if WINDOWS:
        from .plataforma import menu_windows
        return menu_windows
    if LINUX:
        from .plataforma import menu_linux
        return menu_linux
    return None


def disponible():
    return _sistema() is not None


def programa():
    """Lo que hay que ejecutar: el programa empaquetado (el AppImage, no lo que tiene dentro, que solo
    existe mientras está abierto); desde el código fuente, Python (pythonw.exe en Windows: sin consola) con
    app/main.py."""
    if LINUX:
        from .plataforma import linux
        if linux.appimage():
            return [str(linux.appimage())]
    if getattr(sys, 'frozen', False):
        return [str(Path(sys.executable))]
    python = Path(sys.executable)
    pythonw = python.with_name('pythonw.exe')
    return [str(pythonw if pythonw.is_file() else python), '-I',
            str(Path(__file__).resolve().parent / 'main.py')]


def instalada_con_paquete():
    """Linux: True si es la del .deb o el .rpm (como la instalada en Windows, pone el menú sin preguntar)."""
    if not LINUX:
        return False
    from .plataforma import linux
    return linux.instalacion() == 'paquete'


def registrar(prog=None):
    """Añade el menú (o lo rehace apuntando a este programa). Lanza OSError si no se puede."""
    _sistema().registrar(prog or programa())


def quitar():
    """Quita el menú. Lanza OSError si no se puede."""
    if disponible():
        _sistema().quitar()


def registrado():
    return disponible() and _sistema().registrado()


def programa_registrado():
    """Ruta del programa al que apunta el menú, o None."""
    return _sistema().programa_registrado() if disponible() else None


def texto_registrado():
    """El texto de «Bajar subtítulos aquí» tal como está puesto, o ''."""
    return _sistema().texto_registrado() if disponible() else ''


def retitular(prog=None):
    """Pone los textos del menú en el idioma de la app sin cambiar a qué programa apunta. Lanza OSError
    si no se puede."""
    _sistema().retitular(prog or programa())


def describir(prog=None):
    """Para la autoprueba."""
    return _sistema().describir(prog or programa()) if disponible() else 'no disponible en este sistema'


def es_de(prog=None):
    """True si el menú apunta a este programa."""
    actual = programa_registrado()
    return actual is not None and _sistema().misma(actual, Path((prog or programa())[0]))


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
            elif es_de(prog) and not _sistema().al_dia(prog or programa()):
                registrar(prog)
                return True
        if actual is not None and texto_registrado() != tr(TEXTO_CARPETA):
            retitular(prog)
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


def ruta_de_argumento(texto):
    """La ruta que pasa el explorador. En Windows, en la raíz de una unidad llega «D:"» en vez de «D:\\»:
    la barra final de "%V" escapa la comilla de cierre. En Linux, los scripts de Nautilus reciben las rutas
    relativas a la carpeta abierta (que es la carpeta de trabajo)."""
    if not WINDOWS:
        return Path(os.path.abspath(texto)) if texto else Path(texto)
    texto = texto.strip().strip('"')
    if len(texto) == 2 and texto[1] == ':':
        texto += '\\'
    return Path(texto)
