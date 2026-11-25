"""Linux: lo que el usuario ha hecho con la app en su escritorio y que debe desaparecer al desinstalarla
(app --desinstalar: los .deb y .rpm lo ejecutan para cada usuario al quitarse; con el AppImage y el .tar.gz,
la línea de desinstalar de INSTALAR-<versión>.txt).

- Accesos del escritorio: KDE crea un enlace a /usr/share/applications/bajar-subtitulos-esp.desktop;
  Cinnamon o GNOME, una copia de ese archivo. Se quitan solo los que son de la app.
- Anclado en la barra de tareas de Plasma (launchers=…). Plasma reescribe su configuración mientras está
  abierto: con la sesión abierta se le pide a él (D-Bus, evaluateScript); si no está abierto, se edita el
  archivo. Si no se puede, se queda (no rompe nada).
- La app oculta del menú a mano: KDE la saca de su categoría (<Exclude>) y la mete en el menú «.hidden»
  (<Include>) en ~/.config/menus/applications-kmenuedit.menu; otros editores de menú (alacarte, menulibre…)
  dejan una copia con NoDisplay=true en ~/.local/share/applications. Esa nota sobrevive al desinstalar:
  sin quitarla, al reinstalar la app no volvería a «Todas las aplicaciones».

Todo con las rutas del usuario que ejecuta la app ($HOME, $XDG_CONFIG_HOME, $XDG_DATA_HOME).
"""
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from .linux import ID_ESCRITORIO
from .menu_linux import carpeta_datos

DESKTOP = f'{ID_ESCRITORIO}.desktop'
DESKTOP_SISTEMA = Path('/usr/share/applications') / DESKTOP
MARCA_APPIMAGE = 'X-BajarSubtitulosESP-AppImage=true'      # la de menu_aplicaciones
_APPIMAGE = re.compile(r'BajarSubtitulosESP.*\.AppImage$', re.IGNORECASE)
WIDGETS_TAREAS = ('org.kde.plasma.icontasks', 'org.kde.plasma.taskmanager')


def carpeta_config():
    base = os.environ.get('XDG_CONFIG_HOME', '')
    return Path(base) if os.path.isabs(base) else Path.home() / '.config'


def carpeta_escritorio():
    """La carpeta del escritorio del usuario (XDG_DESKTOP_DIR de user-dirs.dirs, o ~/Desktop)."""
    try:
        texto = (carpeta_config() / 'user-dirs.dirs').read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        texto = ''
    m = re.search(r'^\s*XDG_DESKTOP_DIR\s*=\s*"([^"]*)"', texto, re.M)
    if m:
        valor = m.group(1)
        if valor.startswith('$HOME'):
            valor = str(Path.home()) + valor[len('$HOME'):]
        if os.path.isabs(valor):
            return Path(valor)
    return Path.home() / 'Desktop'


def _entrada(texto):
    """Claves del grupo [Desktop Entry] de un archivo .desktop."""
    claves, dentro = {}, False
    for linea in texto.splitlines():
        linea = linea.strip()
        if linea.startswith('['):
            dentro = linea == '[Desktop Entry]'
        elif dentro and '=' in linea and not linea.startswith('#'):
            k, v = linea.split('=', 1)
            claves.setdefault(k.strip(), v.strip())
    return claves


def _programa(exec_):
    try:
        partes = shlex.split(exec_)
    except ValueError:
        return ''
    return Path(partes[0]).name if partes else ''


def es_acceso_de_la_app(ruta):
    """True si `ruta` es un acceso a la app: un enlace a su .desktop, o una copia de él (o de la entrada
    del AppImage). Cualquier otro archivo, aunque se llame igual, no lo es."""
    ruta = Path(ruta)
    if ruta.suffix != '.desktop':
        return False
    if ruta.is_symlink():
        try:
            destino = os.readlink(ruta)
        except OSError:
            return False
        return Path(destino).name == DESKTOP and Path(destino).parent.name == 'applications'
    try:
        if not ruta.is_file() or ruta.stat().st_size > 64 * 1024:
            return False
        texto = ruta.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return False
    e = _entrada(texto)
    if e.get('Type', 'Application') != 'Application' or e.get('Icon') != ID_ESCRITORIO:
        return False
    programa = _programa(e.get('Exec', ''))
    return programa == ID_ESCRITORIO or bool(_APPIMAGE.search(programa)) or MARCA_APPIMAGE in texto


def quitar_accesos_escritorio():
    """Borra los accesos a la app del escritorio. Devuelve los que ha borrado."""
    carpeta = carpeta_escritorio()
    try:
        candidatos = sorted(p for p in carpeta.iterdir() if p.suffix == '.desktop')
    except OSError:
        return []
    quitados = []
    for p in candidatos:
        if es_acceso_de_la_app(p):
            try:
                p.unlink()
                quitados.append(p)
            except OSError:
                pass
    return quitados


# ---------- La app oculta del menú a mano ----------

_BLOQUE = re.compile(r'(<(Include|Exclude)>)(.*?)(</\2>)', re.S)
_NUESTRO = re.compile(r'[ \t]*<Filename>\s*' + re.escape(DESKTOP) + r'\s*</Filename>[ \t]*(\r?\n)?')


def sin_ocultar(texto):
    """Un archivo .menu sin las reglas que sacan a la app de su sitio (<Include>/<Exclude> con su
    .desktop). Lo demás (orden, otras apps) se queda igual."""
    return _BLOQUE.sub(lambda m: m.group(1) + _NUESTRO.sub('', m.group(3)) + m.group(4), texto)


def mostrar_en_menu():
    """Quita las notas que ocultan la app del menú de aplicaciones. Devuelve True si ha cambiado algo."""
    cambiado = False
    menus = carpeta_config() / 'menus'
    try:
        archivos = sorted(menus.glob('*.menu')) + sorted((menus / 'applications-merged').glob('*.menu'))
    except OSError:
        archivos = []
    for archivo in archivos:
        try:
            texto = archivo.read_text(encoding='utf-8')
            nuevo = sin_ocultar(texto)
            if nuevo != texto:
                temporal = archivo.with_name(f'.{archivo.name}.tmp')
                temporal.write_text(nuevo, encoding='utf-8')
                os.replace(temporal, archivo)
                cambiado = True
        except (OSError, UnicodeDecodeError):
            pass
    # Una copia del .desktop que solo sirve para ocultarla (no la entrada del AppImage).
    copia = carpeta_datos() / 'applications' / DESKTOP
    try:
        texto = copia.read_text(encoding='utf-8')
        e = _entrada(texto)
        if MARCA_APPIMAGE not in texto and (e.get('NoDisplay') == 'true' or e.get('Hidden') == 'true'):
            copia.unlink()
            cambiado = True
    except (OSError, UnicodeDecodeError):
        pass
    if cambiado:
        _ejecutar(['kbuildsycoca6'], ['kbuildsycoca5'])      # KDE: que rehaga ya su lista de aplicaciones
    return cambiado


# ---------- Anclado en la barra de tareas de Plasma ----------

def es_lanzador_de_la_app(item):
    item = item.strip()
    return item == f'applications:{DESKTOP}' or item.endswith(f'/applications/{DESKTOP}')


def sin_lanzador(linea_launchers):
    """'a,b,c' sin los lanzadores de la app."""
    return ','.join(i for i in linea_launchers.split(',') if i and not es_lanzador_de_la_app(i))


SCRIPT_PLASMA = '''
var tipos = %s;
panels().forEach(function (panel) {
  panel.widgets().forEach(function (w) {
    if (tipos.indexOf(w.type) < 0) return;
    w.currentConfigGroup = ["General"];
    var l = w.readConfig("launchers", []);
    if (typeof l === "string") l = l ? l.split(",") : [];
    var nuevos = l.filter(function (x) {
      x = String(x).trim();
      return x && x !== "applications:%s" && x.slice(-%d) !== "/applications/%s";
    });
    if (nuevos.length !== l.length) { w.writeConfig("launchers", nuevos); w.reloadConfig(); }
  });
});
''' % ('["' + '", "'.join(WIDGETS_TAREAS) + '"]', DESKTOP, len('/applications/' + DESKTOP), DESKTOP)


def _plasma_abierto():
    """True si este usuario tiene Plasma (plasmashell) abierto."""
    uid = os.getuid()
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if proc.stat().st_uid == uid and (proc / 'comm').read_text().strip() == 'plasmashell':
                return True
        except OSError:
            continue
    return False


def _ejecutar(*ordenes, timeout=30):
    """Ejecuta la primera orden que exista. True si ha salido bien."""
    for orden in ordenes:
        programa = shutil.which(orden[0])
        if not programa:
            continue
        try:
            r = subprocess.run([programa, *orden[1:]], timeout=timeout, check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return r.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False
    return False


def _variant_texto(texto):
    """Un texto como literal de GVariant (para gdbus)."""
    return "'" + texto.replace('\\', '\\\\').replace("'", "\\'") + "'"


def quitar_anclado():
    """Quita la app de la barra de tareas de Plasma. Devuelve True si lo ha hecho (o no había nada)."""
    archivo = carpeta_config() / 'plasma-org.kde.plasma.desktop-appletsrc'
    try:
        texto = archivo.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return True                                              # sin Plasma: nada que quitar
    lineas = texto.splitlines(keepends=True)
    if not any(ln.startswith('launchers=') and sin_lanzador(ln[10:].rstrip('\r\n')) != ln[10:].rstrip('\r\n')
               for ln in lineas):
        return True
    if _plasma_abierto():
        metodo = ['org.kde.plasmashell', '/PlasmaShell', 'org.kde.PlasmaShell.evaluateScript']
        return _ejecutar(['qdbus6', *metodo, SCRIPT_PLASMA], ['qdbus-qt6', *metodo, SCRIPT_PLASMA],
                         ['gdbus', 'call', '--session', '--dest', metodo[0], '--object-path', metodo[1],
                          '--method', metodo[2], _variant_texto(SCRIPT_PLASMA)])
    nuevas = []
    for ln in lineas:
        if ln.startswith('launchers='):
            fin = ln[len(ln.rstrip('\r\n')):]
            ln = 'launchers=' + sin_lanzador(ln[10:].rstrip('\r\n')) + fin
        nuevas.append(ln)
    try:
        temporal = archivo.with_name(f'.{archivo.name}.tmp')
        temporal.write_text(''.join(nuevas), encoding='utf-8')
        os.replace(temporal, archivo)
        return True
    except OSError:
        return False
