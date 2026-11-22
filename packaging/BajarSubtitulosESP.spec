# Receta de PyInstaller: un .exe sin consola y su carpeta (_internal) con Python, Qt y las librerías.
# Modo carpeta (onedir) y sin UPX: arranca rápido (nada que descomprimir) y da menos falsos
# positivos de antivirus. Uso (desde la raíz del proyecto, tras packaging/generar_recursos.py):
#     pyinstaller --noconfirm --clean packaging/BajarSubtitulosESP.spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

RAIZ = Path(SPECPATH).parent
RECURSOS = RAIZ / 'packaging' / 'build'

# Librerías que cargan módulos o datos por nombre (proveedores, refinadores, conversores de idioma,
# reglas de guessit, backends de keyring): PyInstaller no los ve solo, se incluyen enteras.
datas, binaries, hiddenimports = [], [], []
for paquete in ('subliminal', 'guessit', 'rebulk', 'babelfish', 'knowit', 'trakit', 'enzyme', 'pymediainfo',
                'keyring', 'dogpile', 'srt', 'pysrt', 'pysubs2'):
    try:
        d, b, h = collect_all(paquete)
    except Exception:          # no instalada: no hace falta
        continue
    datas += d
    binaries += b
    hiddenimports += h

datas += [(str(RAIZ / 'LICENSE'), '.'), (str(RECURSOS / 'AVISOS_TERCEROS.txt'), '.')]

a = Analysis(
    [str(RAIZ / 'app' / 'main.py')],
    pathex=[str(RAIZ)],
    binaries=binaries,
    datas=datas,
    # QtNetwork: canal local entre aperturas de la app (instancia.py).
    hiddenimports=hiddenimports + ['subtitulos.nucleo', 'app.trabajador', 'keyring.backends.Windows',
                                   'PySide6.QtNetwork'],
    excludes=['tkinter', '_tkinter', 'PySide6.QtQml', 'PySide6.QtQuick',
              'PySide6.QtOpenGL', 'PySide6.QtPdf', 'PySide6.QtDBus', 'IPython', 'pytest',
              # Pruebas y herramientas de las librerías que la app no usa.
              'guessit.test', 'rebulk.test', 'babelfish.tests', 'subliminal.cli', 'click', 'tomlkit',
              'setuptools', 'stevedore.example', 'stevedore.example2', 'stevedore.sphinxext',
              'stevedore.tests', 'docutils', 'sphinx'],
    noarchive=False,
    optimize=0,     # sin -O: las librerías se comportan exactamente igual que en la skill (con sus assert)
)

# Fuera lo que no se usa: renderizado OpenGL por software (20 MB), traducciones de Qt y plugins de
# imagen que la app no necesita (solo usa PNG, ICO y SVG).
def sobra(destino):
    d = destino.replace('\\', '/').lower()
    return ('opengl32sw' in d or '/translations/' in d
            or any(f'imageformats/q{x}' in d for x in ('tga', 'tiff', 'webp', 'wbmp', 'icns', 'pdf', 'gif', 'jpeg')))


a.binaries = [x for x in a.binaries if not sobra(x[0])]
a.datas = [x for x in a.datas if not sobra(x[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BajarSubtitulosESP',
    console=False,
    icon=str(RECURSOS / 'icono.ico'),
    version=str(RECURSOS / 'version.txt'),
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name='BajarSubtitulosESP', upx=False)
