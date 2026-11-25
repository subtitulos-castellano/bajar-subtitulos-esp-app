"""Compila Bajar Subtítulos ESP para Linux (x86_64) y genera el .deb, el .rpm y el AppImage.

    python -I packaging/linux/compilar.py        (o: scripts/linux.sh compilar)

1. Genera el icono y los avisos de licencias (generar_recursos.py).
2. PyInstaller: dist/bajar-subtitulos-esp/ (la orden y su carpeta _internal).
3. Comprueba lo compilado: que lleva lo que Qt necesita para X11 y Wayland, qué librerías del sistema usa
   (bibliotecas.py) y que no pide una glibc más nueva que la 2.34.
4. Autoprueba del programa compilado (proveedores, idiomas, llavero, lectura de MKV...), sin pantalla.
5. dist/BajarSubtitulosESP-<versión>-linux-x86_64.tar.gz: la carpeta tal cual.
6. dist/BajarSubtitulosESP-<versión>-x86_64.AppImage: con el runtime nuevo de AppImage (no necesita
   libfuse2) y squashfs (mksquashfs, del paquete squashfs-tools).
7. dist/BajarSubtitulosESP-<versión>-amd64.deb y -x86_64.rpm, con nfpm (y en dist/prueba, los mismos como
   revisión 2, para probar la actualización).

El runtime de AppImage y nfpm se descargan (en packaging/build/herramientas) solo si coinciden con su
SHA-256. Para que lo compilado valga en todos los Linux con glibc 2.34 o posterior, GitHub Actions compila
en AlmaLinux 9; en otro sistema más nuevo sale igual, pero solo vale para ese y los posteriores (se avisa).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(AQUI))
from app import __version__  # noqa: E402
from app.plataforma.linux import ID_ESCRITORIO  # noqa: E402
import bibliotecas  # noqa: E402

DIST = RAIZ / 'dist'
CARPETA = DIST / ID_ESCRITORIO
EXE = CARPETA / ID_ESCRITORIO
BUILD = RAIZ / 'packaging' / 'build'
HERRAMIENTAS = BUILD / 'herramientas'
NOMBRE = f'BajarSubtitulosESP-{__version__}'
DESTINO = f'/opt/{ID_ESCRITORIO}'           # dónde instalan el programa el .deb y el .rpm

RUNTIME = ('https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64',
           '2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d')
NFPM = ('https://github.com/goreleaser/nfpm/releases/download/v2.48.0/nfpm_2.48.0_Linux_x86_64.tar.gz',
        '6d7f9a28b2f397934403950fcbba83f598b08d02edbe79a0815b3b4897341750')

# Lo que Qt necesita para mostrar la ventana en X11 y en Wayland (y sin pantalla, para las pruebas).
IMPRESCINDIBLE = [
    'platforms/libqxcb.so', 'platforms/libqwayland.so', 'platforms/libqoffscreen.so',
    'wayland-shell-integration/libxdg-shell.so', 'wayland-decoration-client/libbradient.so',
    'xcbglintegrations/libqxcb-glx-integration.so', 'imageformats/libqsvg.so', 'iconengines/libqsvgicon.so',
    'platformthemes/libqxdgdesktopportal.so',
]


def paso(titulo):
    print(f'\n=== {titulo}', flush=True)


def ejecutar(*orden, **kw):
    subprocess.run([str(x) for x in orden], cwd=RAIZ, check=True, **kw)


def tamano(ruta):
    if ruta.is_file():
        return ruta.stat().st_size
    return sum(p.stat().st_size for p in ruta.rglob('*') if p.is_file() and not p.is_symlink())


def mb(n):
    return f'{n / 1024 / 1024:.1f} MB'


def descargar(url, sha256):
    """La herramienta de `url`, descargada una vez y comprobada con su SHA-256."""
    destino = HERRAMIENTAS / url.rsplit('/', 1)[1]
    if not destino.is_file() or hashlib.sha256(destino.read_bytes()).hexdigest() != sha256:
        HERRAMIENTAS.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=120) as r:
            datos = r.read()
        if hashlib.sha256(datos).hexdigest() != sha256:
            sys.exit(f'{destino.name}: la descarga no coincide con su SHA-256')
        destino.write_bytes(datos)
    return destino


def nfpm():
    archivo = descargar(*NFPM)
    binario = HERRAMIENTAS / 'nfpm'
    with tarfile.open(archivo) as t:
        binario.write_bytes(t.extractfile('nfpm').read())
    binario.chmod(0o755)
    return binario


def compilar():
    paso(f'Recursos (versión {__version__})')
    ejecutar(sys.executable, '-I', 'packaging/generar_recursos.py')
    paso('PyInstaller')
    shutil.rmtree(CARPETA, ignore_errors=True)
    ejecutar(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--log-level', 'WARN',
             '--distpath', DIST, '--workpath', RAIZ / 'build', 'packaging/linux/BajarSubtitulosESP.spec')
    print(f'{CARPETA.name}: {mb(tamano(CARPETA))}')


def comprobar():
    paso('Comprobaciones')
    plugins = CARPETA / '_internal' / 'PySide6' / 'Qt' / 'plugins'
    faltan = [p for p in IMPRESCINDIBLE if not (plugins / p).is_file()]
    if not list((CARPETA / '_internal').glob('libxcb-cursor.so*')):
        faltan.append('libxcb-cursor.so.0')
    if faltan:
        sys.exit(f'Faltan dentro del programa: {", ".join(faltan)}')
    print('Qt: X11, Wayland, offscreen, SVG y libxcb-cursor dentro')
    sistema, glibc = bibliotecas.dependencias(CARPETA)
    print(f'Librerías del sistema ({len(sistema)}): {" ".join(sistema)}')
    texto = '.'.join(map(str, glibc))
    if glibc > bibliotecas.GLIBC_MAXIMA:
        aviso = (f'pide glibc {texto} (como mucho debería ser '
                 f'{".".join(map(str, bibliotecas.GLIBC_MAXIMA))}): compilado en un sistema más nuevo')
        if os.environ.get('CI'):
            sys.exit(f'Error: {aviso}.')
        print(f'AVISO: {aviso}; solo vale para este sistema y los posteriores.')
    else:
        print(f'glibc: como mucho {texto}')
    return sistema


def autoprueba():
    paso('Autoprueba del programa compilado')
    with tempfile.TemporaryDirectory() as d:
        informe = Path(d) / 'informe.txt'
        t0 = time.monotonic()
        entorno = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        r = subprocess.run([str(EXE), '--autoprueba', str(informe)], timeout=180, env=entorno)
        print(informe.read_text(encoding='utf-8') if informe.exists() else '(sin informe)')
        if r.returncode != 0:
            sys.exit(f'La autoprueba ha fallado (código {r.returncode}).')
        print(f'autoprueba correcta en {time.monotonic() - t0:.1f} s')


def _tar_info_raiz(info):
    info.uid = info.gid = 0
    info.uname = info.gname = 'root'
    return info


def portable():
    paso('Carpeta comprimida (.tar.gz)')
    salida = DIST / f'{NOMBRE}-linux-x86_64.tar.gz'
    with tarfile.open(salida, 'w:gz', compresslevel=9) as t:
        t.add(CARPETA, arcname=ID_ESCRITORIO, filter=_tar_info_raiz)
    print(f'{salida.name}: {mb(tamano(salida))}')


def appimage():
    paso('AppImage')
    appdir = BUILD / 'AppDir'
    shutil.rmtree(appdir, ignore_errors=True)
    programa = appdir / 'usr' / 'lib' / ID_ESCRITORIO
    shutil.copytree(CARPETA, programa, symlinks=True)
    shutil.copy2(AQUI / 'AppRun', appdir / 'AppRun')
    shutil.copy2(AQUI / f'{ID_ESCRITORIO}.desktop', appdir / f'{ID_ESCRITORIO}.desktop')
    shutil.copytree(BUILD / 'hicolor', appdir / 'usr' / 'share' / 'icons' / 'hicolor')
    shutil.copy2(BUILD / 'hicolor' / '256x256' / 'apps' / f'{ID_ESCRITORIO}.png', appdir / f'{ID_ESCRITORIO}.png')
    (appdir / '.DirIcon').symlink_to(f'{ID_ESCRITORIO}.png')
    imagen = BUILD / 'AppImage.squashfs'
    imagen.unlink(missing_ok=True)
    ejecutar('mksquashfs', appdir, imagen, '-root-owned', '-noappend', '-no-xattrs', '-no-progress',
             '-comp', 'zstd', '-Xcompression-level', '19', '-b', '1M')
    salida = DIST / f'{NOMBRE}-x86_64.AppImage'
    with open(salida, 'wb') as f:
        f.write(descargar(*RUNTIME).read_bytes())
        with open(imagen, 'rb') as s:
            shutil.copyfileobj(s, f)
    salida.chmod(0o755)
    imagen.unlink()
    print(f'{salida.name}: {mb(tamano(salida))}')


def paquetes(sistema):
    paso('.deb y .rpm (nfpm)')
    contenido = [
        {'src': str(CARPETA), 'dst': DESTINO, 'type': 'tree'},
        {'src': f'{DESTINO}/{ID_ESCRITORIO}', 'dst': f'/usr/bin/{ID_ESCRITORIO}', 'type': 'symlink'},
        {'src': str(AQUI / f'{ID_ESCRITORIO}.desktop'), 'dst': f'/usr/share/applications/{ID_ESCRITORIO}.desktop',
         'file_info': {'mode': 0o644}},
    ]
    for icono in sorted((BUILD / 'hicolor').rglob(f'{ID_ESCRITORIO}.*')):
        contenido.append({'src': str(icono), 'dst': f'/usr/share/icons/hicolor/{icono.relative_to(BUILD / "hicolor")}',
                          'file_info': {'mode': 0o644}})
    despues = str(AQUI / 'despues.sh')
    antes_de_quitar = str(AQUI / 'antes_de_quitar.sh')     # al desinstalar: limpia lo de cada usuario
    config = {
        'name': ID_ESCRITORIO,
        'arch': 'amd64',
        'platform': 'linux',
        'version': __version__,
        'release': '1',
        'section': 'video',
        'priority': 'optional',
        'maintainer': 'subtitulos-castellano <2649530+danimagan@users.noreply.github.com>',
        'vendor': 'subtitulos-castellano',
        'homepage': 'https://github.com/subtitulos-castellano/bajar-subtitulos-esp-app',
        'license': 'MIT',
        'description': 'Subtítulos en castellano de España para series y películas en inglés.\n'
                       'Busca en varios proveedores, prefiere siempre el castellano de España y nunca sustituye '
                       'un subtítulo por otro peor.',
        'contents': contenido,
        'scripts': {'postinstall': despues, 'preremove': antes_de_quitar, 'postremove': despues},
        'overrides': {'deb': {'depends': bibliotecas.depende_deb(sistema)},
                      'rpm': {'depends': bibliotecas.depende_rpm(sistema)}},
        'deb': {'compression': 'xz'},
        'rpm': {'compression': 'zstd', 'summary': 'Subtítulos en castellano de España para series y películas'},
    }
    binario = nfpm()
    # Además, para las pruebas de la actualización (no se publican): los mismos paquetes como revisión 2,
    # que apt y dnf instalan encima de la 1 igual que harían con una versión nueva.
    for carpeta, revision in ((DIST, '1'), (DIST / 'prueba', '2')):
        carpeta.mkdir(parents=True, exist_ok=True)
        archivo = BUILD / f'nfpm-{revision}.yaml'
        archivo.write_text(json.dumps(dict(config, release=revision), ensure_ascii=False, indent=1),
                           encoding='utf-8')                                  # JSON es YAML
        for formato, nombre in (('deb', f'{NOMBRE}-amd64.deb'), ('rpm', f'{NOMBRE}-x86_64.rpm')):
            salida = carpeta / nombre
            salida.unlink(missing_ok=True)
            ejecutar(binario, 'package', '--config', archivo, '--packager', formato, '--target', salida,
                     stdout=subprocess.DEVNULL)
            print(f'{salida.relative_to(DIST)}: {mb(tamano(salida))}')


def main():
    compilar()
    sistema = comprobar()
    autoprueba()
    portable()
    appimage()
    paquetes(sistema)


if __name__ == '__main__':
    main()
