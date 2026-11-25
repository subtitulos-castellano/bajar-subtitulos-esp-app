"""Compila Bajar Subtítulos ESP para Windows (en el PC o en GitHub Actions).

    python -I packaging/windows/compilar.py

1. Genera el icono, la versión del .exe y los avisos de licencias (generar_recursos.py).
2. PyInstaller: dist/BajarSubtitulosESP/ (el .exe y su carpeta _internal).
3. Autoprueba del .exe empaquetado (proveedores, idiomas, keyring, lectura de MKV...).
4. dist/BajarSubtitulosESP-<versión>-windows-portable.zip
5. Si está Inno Setup (ISCC.exe): dist/BajarSubtitulosESP-<versión>-windows-instalador.exe
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ))
from app import __version__  # noqa: E402

DIST = RAIZ / 'dist'
CARPETA = DIST / 'BajarSubtitulosESP'
EXE = CARPETA / 'BajarSubtitulosESP.exe'


def paso(titulo):
    print(f'\n=== {titulo}', flush=True)


def ejecutar(*orden):
    subprocess.run(orden, cwd=RAIZ, check=True)


def tamano(ruta):
    if ruta.is_file():
        return ruta.stat().st_size
    return sum(p.stat().st_size for p in ruta.rglob('*') if p.is_file())


def mb(n):
    return f'{n / 1024 / 1024:.1f} MB'


def iscc():
    candidatos = [os.environ.get('ISCC', '')]
    for base in (os.environ.get('ProgramFiles(x86)', ''), os.environ.get('ProgramFiles', ''),
                 os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs')):
        candidatos.append(os.path.join(base, 'Inno Setup 6', 'ISCC.exe'))
    return next((c for c in candidatos if c and os.path.isfile(c)), shutil.which('iscc'))


def main():
    paso(f'Recursos (versión {__version__})')
    ejecutar(sys.executable, '-I', 'packaging/generar_recursos.py')

    paso('PyInstaller')
    shutil.rmtree(CARPETA, ignore_errors=True)
    ejecutar(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--log-level', 'WARN',
             '--distpath', str(DIST), '--workpath', str(RAIZ / 'build'), 'packaging/windows/BajarSubtitulosESP.spec')
    print(f'{CARPETA.name}: {mb(tamano(CARPETA))}')

    paso('Autoprueba del ejecutable')
    with tempfile.TemporaryDirectory() as d:
        informe = Path(d) / 'informe.txt'
        t0 = time.monotonic()
        r = subprocess.run([str(EXE), '--autoprueba', str(informe)], timeout=180)
        print(informe.read_text(encoding='utf-8') if informe.exists() else '(sin informe)')
        if r.returncode != 0:
            sys.exit(f'La autoprueba del .exe ha fallado (código {r.returncode}).')
        print(f'autoprueba correcta en {time.monotonic() - t0:.1f} s')

    paso('Versión portable (zip)')
    portable = DIST / f'BajarSubtitulosESP-{__version__}-windows-portable.zip'
    portable.unlink(missing_ok=True)
    with zipfile.ZipFile(portable, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(CARPETA.rglob('*')):
            if p.is_file():
                z.write(p, Path('BajarSubtitulosESP') / p.relative_to(CARPETA))
    print(f'{portable.name}: {mb(tamano(portable))}')

    paso('Instalador (Inno Setup)')
    compilador = iscc()
    if not compilador:
        print('Inno Setup no está instalado: se omite el instalador (lo genera GitHub Actions).')
        return
    ejecutar(compilador, '/Q', f'/DVersion={__version__}', f'/DOrigen={CARPETA}', f'/DSalida={DIST}',
             'packaging/windows/instalador.iss')
    instalador = DIST / f'BajarSubtitulosESP-{__version__}-windows-instalador.exe'
    print(f'{instalador.name}: {mb(tamano(instalador))}')


if __name__ == '__main__':
    main()
