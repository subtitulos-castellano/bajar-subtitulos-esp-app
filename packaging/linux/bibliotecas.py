"""Qué librerías del sistema usa el programa compilado para Linux, y qué paquetes las traen.

- NUCLEO: las de glibc, que tiene cualquier Linux (la versión mínima la fija GLIBC_MAXIMA).
- SISTEMA: las que tiene cualquier escritorio y deben ser las del propio sistema (van a juego con su servidor
  gráfico, sus controladores o su configuración). No se meten en el programa (BajarSubtitulosESP.spec); los
  .deb y .rpm las piden como dependencias. Para cada una, el paquete de Debian/Ubuntu que la trae (con «|»,
  alternativas: el nombre cambió en Ubuntu 24.04 y Debian 13). El .rpm las pide por su nombre de librería
  (p. ej. «libX11.so.6()(64bit)»), que entienden dnf y zypper en cualquier distribución.
- Todo lo demás va dentro del programa.

dependencias(carpeta) mira qué pide cada archivo del programa compilado (con readelf) y devuelve las
librerías del sistema que hacen falta; si alguna no está ni dentro, ni en NUCLEO, ni en SISTEMA, es un error.
"""
import re
import subprocess
from pathlib import Path

GLIBC_MAXIMA = (2, 34)        # AlmaLinux/RHEL 9; la exige también PySide6 6.12

NUCLEO = {'libc.so.6', 'libm.so.6', 'libpthread.so.0', 'libdl.so.2', 'librt.so.1', 'libutil.so.1',
          'libresolv.so.2', 'ld-linux-x86-64.so.2', 'libanl.so.1'}

_GLIB = 'libglib2.0-0t64 | libglib2.0-0'
SISTEMA = {
    # OpenGL y EGL (los da el controlador gráfico del sistema)
    'libGL.so.1': 'libgl1', 'libEGL.so.1': 'libegl1', 'libOpenGL.so.0': 'libopengl0', 'libGLX.so.0': 'libglx0',
    'libGLdispatch.so.0': 'libglvnd0', 'libdrm.so.2': 'libdrm2', 'libgbm.so.1': 'libgbm1',
    # X11 (las de libxcb; las de xcb-util van dentro)
    'libX11.so.6': 'libx11-6', 'libX11-xcb.so.1': 'libx11-xcb1', 'libxcb.so.1': 'libxcb1',
    'libxcb-randr.so.0': 'libxcb-randr0', 'libxcb-render.so.0': 'libxcb-render0',
    'libxcb-shape.so.0': 'libxcb-shape0', 'libxcb-shm.so.0': 'libxcb-shm0', 'libxcb-sync.so.1': 'libxcb-sync1',
    'libxcb-xfixes.so.0': 'libxcb-xfixes0', 'libxcb-xkb.so.1': 'libxcb-xkb1', 'libxcb-glx.so.0': 'libxcb-glx0',
    'libxkbcommon.so.0': 'libxkbcommon0', 'libxkbcommon-x11.so.0': 'libxkbcommon-x11-0',
    # Wayland
    'libwayland-client.so.0': 'libwayland-client0', 'libwayland-cursor.so.0': 'libwayland-cursor0',
    'libwayland-egl.so.1': 'libwayland-egl1',
    # Letras (con la configuración de fuentes del sistema)
    'libfontconfig.so.1': 'libfontconfig1', 'libfreetype.so.6': 'libfreetype6', 'libexpat.so.1': 'libexpat1',
    'libharfbuzz.so.0': 'libharfbuzz0b', 'libpng16.so.16': 'libpng16-16t64 | libpng16-16',
    # glib (bucle de eventos de Qt) y D-Bus (bandeja, llavero, portales del escritorio)
    'libglib-2.0.so.0': _GLIB, 'libgthread-2.0.so.0': _GLIB, 'libgobject-2.0.so.0': _GLIB,
    'libgio-2.0.so.0': _GLIB, 'libgmodule-2.0.so.0': _GLIB, 'libpcre2-8.so.0': 'libpcre2-8-0',
    'libdbus-1.so.3': 'libdbus-1-3',
    # Básicas
    'libz.so.1': 'zlib1g', 'libzstd.so.1': 'libzstd1', 'libgssapi_krb5.so.2': 'libgssapi-krb5-2',
    'libstdc++.so.6': 'libstdc++6', 'libgcc_s.so.1': 'libgcc-s1',
}


def del_sistema(ruta):
    """True si la librería `ruta` (o su nombre) es de las que pone el sistema."""
    return Path(str(ruta).replace('\\', '/')).name in SISTEMA


def _necesita(ruta):
    """Librerías que pide el archivo ELF `ruta` (NEEDED)."""
    try:
        return re.findall(r'\(NEEDED\)\s+Shared library: \[([^\]]+)\]', _readelf('-d', '-W', str(ruta)))
    except subprocess.CalledProcessError:
        return []


def podar(binarios):
    """Quita de la lista de PyInstaller las librerías sueltas (en la raíz de _internal) que ya no pide nadie.

    PyInstaller las recoge siguiendo lo que pide cada complemento de Qt, también los que luego no se meten
    (p. ej. el tema de GTK arrastraría GTK, cairo…). Se quedan los módulos de Python, lo de PySide6 y demás
    paquetes (también los módulos sueltos, como el de chardet), libpython y las librerías sueltas que alguno de ellos pida (directa o indirectamente)."""
    sueltas = {Path(d).name: (d, o, t) for d, o, t in binarios
               if t == 'BINARY' and '/' not in d.replace('\\', '/') and not d.startswith('libpython')}
    quedan = [x for x in binarios if x not in sueltas.values()]
    pendientes = [o for _, o, _ in quedan]
    usadas = set()
    while pendientes:
        for nombre in _necesita(pendientes.pop()):
            if nombre in sueltas and nombre not in usadas:
                usadas.add(nombre)
                pendientes.append(sueltas[nombre][1])
    return quedan + [x for n, x in sueltas.items() if n in usadas]


def es_elf(ruta):
    try:
        with open(ruta, 'rb') as f:
            return f.read(4) == b'\x7fELF'
    except OSError:
        return False


def _readelf(*args):
    return subprocess.run(['readelf', *args], capture_output=True, text=True, check=True).stdout


def elfs(carpeta):
    return sorted(p for p in Path(carpeta).rglob('*') if p.is_file() and not p.is_symlink() and es_elf(p))


def dependencias(carpeta):
    """(del sistema, glibc más nueva que se pide, avisos). Error si falta alguna librería."""
    carpeta = Path(carpeta)
    dentro = {p.name for p in carpeta.rglob('*.so*')}
    sistema, faltan, glibc = set(), {}, (0, 0)
    for archivo in elfs(carpeta):
        dinamica = _readelf('-d', '-W', str(archivo))
        for nombre in re.findall(r'\(NEEDED\)\s+Shared library: \[([^\]]+)\]', dinamica):
            if nombre in dentro or nombre in NUCLEO:
                continue
            if nombre in SISTEMA:
                sistema.add(nombre)
            else:
                faltan.setdefault(nombre, []).append(str(archivo.relative_to(carpeta)))
        for v in re.findall(r'Name: GLIBC_(\d+)\.(\d+)', _readelf('-V', '-W', str(archivo))):
            glibc = max(glibc, (int(v[0]), int(v[1])))
    if faltan:
        detalle = '\n'.join(f'  {n}: la piden {", ".join(q[:3])}' for n, q in sorted(faltan.items()))
        raise SystemExit(f'Librerías que no van dentro ni están en bibliotecas.SISTEMA:\n{detalle}')
    return sorted(sistema), glibc


def depende_deb(sistema):
    """Dependencias del .deb (sin repetir) para las librerías del sistema que usa el programa."""
    vistas = []
    for nombre in sistema:
        if SISTEMA[nombre] not in vistas:
            vistas.append(SISTEMA[nombre])
    return [f'libc6 (>= {GLIBC_MAXIMA[0]}.{GLIBC_MAXIMA[1]})'] + sorted(vistas)


def depende_rpm(sistema):
    """Dependencias del .rpm: por el nombre de cada librería, como las calcula rpmbuild."""
    return [f'libc.so.6(GLIBC_{GLIBC_MAXIMA[0]}.{GLIBC_MAXIMA[1]})(64bit)'] + [f'{n}()(64bit)' for n in sistema]
