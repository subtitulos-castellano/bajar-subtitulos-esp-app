# Receta de PyInstaller para Linux: la orden bajar-subtitulos-esp y su carpeta _internal con Python, Qt y
# las librerías. Uso: packaging/linux/compilar.py (genera antes los recursos y después comprueba el resultado).
#
# Qué librerías del sistema van dentro y cuáles no (SISTEMA, más abajo): las que tiene cualquier escritorio
# Linux (glibc, OpenGL, X11, Wayland, fontconfig, glib, D-Bus…) se usan las del sistema, que deben ir a juego
# con su servidor gráfico, sus controladores y su configuración; los paquetes .deb y .rpm las declaran como
# dependencias. Las demás van dentro, por ejemplo libxcb-cursor, que Qt necesita y muchos sistemas no traen.
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

RAIZ = Path(SPECPATH).parent.parent
RECURSOS = RAIZ / 'packaging' / 'build'
sys.path.insert(0, str(Path(SPECPATH)))
from bibliotecas import del_sistema, podar  # noqa: E402

datas, binaries, hiddenimports = [], [], []
for paquete in ('subliminal', 'guessit', 'rebulk', 'babelfish', 'knowit', 'trakit', 'enzyme', 'pymediainfo',
                'keyring', 'secretstorage', 'jeepney', 'dogpile', 'srt', 'pysrt', 'pysubs2'):
    try:
        d, b, h = collect_all(paquete)
    except Exception:          # no instalada: no hace falta
        continue
    datas += d
    binaries += b
    hiddenimports += h

# Traductor (subtitulos/traducir.py): solo lo que hace falta para traducir. Sus conversores (torch,
# transformers) y numpy no: el modelo ya viene convertido. En Windows, sus DLL van junto al paquete.
binaries += collect_dynamic_libs('ctranslate2')
hiddenimports += ['ctranslate2', 'sentencepiece', 'subtitulos.traducir', 'subtitulos.modelo']

datas += [(str(RAIZ / 'LICENSE'), '.'), (str(RECURSOS / 'AVISOS_TERCEROS.txt'), '.')]

a = Analysis(
    [str(RAIZ / 'app' / 'main.py')],
    pathex=[str(RAIZ)],
    binaries=binaries,
    datas=datas,
    # QtNetwork: canal local entre aperturas de la app (instancia.py). SecretService: el llavero del
    # escritorio (KWallet o GNOME Keyring).
    hiddenimports=hiddenimports + ['subtitulos.nucleo', 'app.trabajador', 'keyring.backends.SecretService',
                                   'PySide6.QtNetwork'],
    excludes=['tkinter', '_tkinter', 'PySide6.QtQml', 'PySide6.QtQuick',
              'PySide6.QtOpenGL', 'PySide6.QtPdf', 'PySide6.QtDBus', 'IPython', 'pytest',
              # Pruebas y herramientas de las librerías que la app no usa.
              'guessit.test', 'rebulk.test', 'babelfish.tests', 'subliminal.cli', 'click', 'tomlkit',
              'setuptools', 'stevedore.example', 'stevedore.example2', 'stevedore.sphinxext',
              'stevedore.tests', 'docutils', 'sphinx',
              'numpy', 'torch', 'transformers', 'ctranslate2.converters', 'ctranslate2.specs'],
    noarchive=False,
    optimize=0,     # sin -O: las librerías se comportan exactamente igual que en la skill (con sus assert)
)

# Complementos de Qt: de pantalla, solo X11, Wayland y offscreen (sin pantalla); ni el tema de GTK (cargaría
# el GTK del sistema junto a las librerías de dentro), ni lo que es de servidores Wayland, ni traducciones de
# Qt, ni formatos de imagen que la app no usa (solo PNG, ICO y SVG).
PANTALLAS = ('libqxcb.so', 'libqwayland.so', 'libqoffscreen.so')


def sobra(destino):
    d = destino.replace('\\', '/')
    if '/plugins/platforms/' in d:
        return d.rsplit('/', 1)[1] not in PANTALLAS
    return ('/translations/' in d or '/plugins/platformthemes/libqgtk3' in d
            or '/plugins/wayland-graphics-integration-server/' in d or '/plugins/egldeviceintegrations/' in d
            or '/plugins/networkinformation/' in d or '/plugins/tls/' in d
            or any(f'/plugins/imageformats/libq{x}' in d for x in
                   ('tga', 'tiff', 'webp', 'wbmp', 'icns', 'pdf', 'gif', 'jpeg')))


a.binaries = podar([x for x in a.binaries if not sobra(x[0]) and not del_sistema(x[0])])
a.datas = [x for x in a.datas if not sobra(x[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='bajar-subtitulos-esp',
    console=False,
    strip=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name='bajar-subtitulos-esp', upx=False)
