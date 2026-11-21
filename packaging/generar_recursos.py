"""Genera los recursos del empaquetado (se ejecuta antes de PyInstaller, con el Python de Windows):

- packaging/build/icono.ico: el icono de la app (16-256 px, PNG dentro del .ico), desde iconos.ICONO_APP.
- packaging/build/version.txt: datos de versión del .exe (Propiedades › Detalles en Windows).
- packaging/build/AVISOS_TERCEROS.txt: licencias de las librerías incluidas.

Uso: python -I packaging/generar_recursos.py
"""
import os
import struct
import sys
from importlib import metadata
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
SALIDA = RAIZ / 'packaging' / 'build'

from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import __version__  # noqa: E402


def icono():
    from app.ventana import icono_app
    ico = icono_app()
    imagenes = []
    for lado in (16, 20, 24, 32, 40, 48, 64, 128, 256):     # los que usa Windows según el escalado
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        ico.pixmap(lado, lado).toImage().save(buf, 'PNG')
        imagenes.append((lado, bytes(buf.data())))
    # Formato ICO: cabecera, una entrada por imagen y los PNG detrás (Windows Vista o posterior).
    cabecera = struct.pack('<HHH', 0, 1, len(imagenes))
    desplazamiento = 6 + 16 * len(imagenes)
    entradas, datos = b'', b''
    for lado, png in imagenes:
        entradas += struct.pack('<BBBBHHII', lado % 256, lado % 256, 0, 0, 1, 32, len(png), desplazamiento)
        desplazamiento += len(png)
        datos += png
    (SALIDA / 'icono.ico').write_bytes(cabecera + entradas + datos)


def version():
    numeros = tuple(int(x) for x in __version__.split('.')) + (0,)
    texto = f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={numeros}, prodvers={numeros}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('0C0A04B0', [
      StringStruct('CompanyName', 'subtitulos-castellano'),
      StringStruct('FileDescription', 'Bajar Subtítulos ESP'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', 'BajarSubtitulosESP'),
      StringStruct('LegalCopyright', 'MIT - bajar-subtitulos-esp contributors'),
      StringStruct('OriginalFilename', 'BajarSubtitulosESP.exe'),
      StringStruct('ProductName', 'Bajar Subtítulos ESP'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [0x0C0A, 1200])])
  ]
)
'''
    (SALIDA / 'version.txt').write_text(texto, encoding='utf-8')


def avisos():
    """Nombre, versión y licencia de cada librería instalada que acaba dentro del programa."""
    excluir = {'pip', 'setuptools', 'wheel', 'pyinstaller', 'pyinstaller-hooks-contrib', 'altgraph',
               'pefile', 'packaging', 'pywin32-ctypes'}
    filas = []
    for d in sorted(metadata.distributions(), key=lambda d: d.metadata['Name'].lower()):
        nombre = d.metadata['Name']
        if nombre.lower() in excluir:
            continue
        licencia = (d.metadata.get('License-Expression') or d.metadata.get('License') or '').strip()
        if not licencia or len(licencia) > 80:
            clasif = [c.split('::')[-1].strip() for c in d.metadata.get_all('Classifier') or []
                      if c.startswith('License ::')]
            licencia = ', '.join(clasif) or (licencia.splitlines()[0][:80] if licencia else 'ver el paquete')
        filas.append(f'{nombre} {d.version}: {licencia}')
    texto = f'''Bajar Subtítulos ESP {__version__}
Licencia del programa: MIT (ver LICENSE.txt).

Componentes de terceros incluidos
=================================

Qt 6 / PySide6 (The Qt Company): LGPL v3. Las librerías de Qt van como archivos separados
(carpeta _internal) y se pueden sustituir por otra versión compatible.
https://www.qt.io/licensing/  https://www.gnu.org/licenses/lgpl-3.0.html

Iconos: Lucide (https://lucide.dev), licencia ISC.

Python y librerías:
''' + '\n'.join(f'  - {f}' for f in filas) + '\n'
    (SALIDA / 'AVISOS_TERCEROS.txt').write_text(texto, encoding='utf-8')


if __name__ == '__main__':
    SALIDA.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    icono()
    version()
    avisos()
    print(f'Recursos generados en {SALIDA} (versión {__version__})')
