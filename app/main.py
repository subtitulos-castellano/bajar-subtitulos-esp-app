"""Arranque de Bajar Subtítulos ESP.

    python -I app/main.py [--tema sistema|claro|oscuro] [--idioma es|en] [--demo] [--captura CARPETA]
                          [--config ARCHIVO] [VÍDEO_O_CARPETA ...]

Con vídeos o carpetas (p. ej., soltados sobre el icono del programa), los busca al abrirse.
--menu-carpeta, --menu-subcarpetas y --menu-archivos los usa el menú contextual del Explorador
(menu_contextual.py); --menu-contextual-instalar y --menu-contextual-quitar, el instalador (con
--idioma-inicial, el idioma elegido al instalar, que solo cuenta si aún no se había elegido).
--pagina ajustes: abrirse en Configuración (al volver a abrirse tras cambiar el idioma).

--tema e --idioma solo valen para esta apertura (no cambian la configuración).

--demo usa resultados de demostración (no busca ni descarga nada).
--captura guarda imágenes de cada pantalla en claro y oscuro sin mostrar la ventana (sirve para
revisar el diseño; implica --demo).
--config usa otro archivo de configuración (para pruebas).
"""
import time

_T0 = time.perf_counter()

import argparse  # noqa: E402
import sys  # noqa: E402
from pathlib import Path

# Con -I, Python no añade la carpeta del script a sys.path: se añade la raíz del proyecto.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QScrollArea  # noqa: E402

from app import tema  # noqa: E402
from app.plataforma import LINUX, WINDOWS  # noqa: E402

ID_APP = 'subtitulos-castellano.BajarSubtitulosESP'


def _identificarse():
    """En Windows: para que agrupe la app en la barra de tareas con su propio icono, y para que el
    instalador sepa si la app está abierta (y, al actualizar, cuándo se ha cerrado)."""
    if WINDOWS:
        from app.plataforma import windows
        windows.id_de_app(ID_APP)
    from app import actualizar
    actualizar.crear_mutex()


def _mkv_castellano():
    """MKV mínimo con una pista de subtítulos en castellano (para la autoprueba)."""
    def el(eid, datos):
        return eid.to_bytes((eid.bit_length() + 7) // 8, 'big') + b'\x01' + len(datos).to_bytes(7, 'big') + datos
    texto = 'Vale, tío, ¿qué hacéis vosotros aquí? Os lo dije.'.encode()
    pista = el(0xAE, el(0xD7, b'\x01') + el(0x86, b'S_TEXT/UTF8') + el(0x22B59C, b'spa'))
    bloque = el(0xA0, el(0xA1, b'\x81\x00\x00\x00' + texto) + el(0x9B, (2000).to_bytes(2, 'big')))
    return el(0x1A45DFA3, el(0x4282, b'matroska')) + el(0x18538067, el(0x1654AE6B, pista)
                                                     + el(0x1F43B675, el(0xE7, b'\x00') + bloque))


def autoprueba(salida, con_red=False):
    """Comprueba que el ejecutable empaquetado lleva todo lo necesario (sin ventana) y escribe el
    informe en `salida`. Con `con_red`, además hace una búsqueda real (simulada, sin escribir) contra
    los proveedores. Devuelve 0 si todo va bien."""
    import tempfile
    import traceback
    lineas, ok = [], True

    def paso(nombre, funcion):
        nonlocal ok
        try:
            lineas.append(f'OK    {nombre}: {funcion()}')
        except Exception:  # noqa: BLE001 - se informa de cualquier fallo
            ok = False
            lineas.append(f'FALLO {nombre}:\n{traceback.format_exc()}')

    from app import __version__
    lineas.append(f'Bajar Subtítulos ESP {__version__} | Python {sys.version.split()[0]} | '
                  f'empaquetado: {getattr(sys, "frozen", False)}')
    paso('núcleo', lambda: __import__('subtitulos.nucleo', fromlist=['x']).PROVIDERS)

    def proveedores():
        from subliminal.extensions import provider_manager, refiner_manager
        nombres = sorted(provider_manager.names())
        n = __import__('subtitulos.nucleo', fromlist=['x'])
        faltan = [p for p in n.PROVIDERS + [n.ULTIMO] if p not in nombres]
        if faltan:
            raise RuntimeError(f'faltan proveedores: {faltan}')
        for p in ('addic7ed', 'gestdown', 'subtitulamos', 'opensubtitles', 'opensubtitlescom'):
            provider_manager[p].plugin                      # que se puedan importar
        for r in ('hash', 'metadata', 'tvdb'):              # los que usa el núcleo (refine)
            refiner_manager[r].plugin
        return f'{len(nombres)} proveedores; refinadores: {sorted(refiner_manager.names())}'
    paso('refinador metadata (duración del vídeo)',
         lambda: __import__('subliminal.refiners.metadata', fromlist=['x']).refine.__name__)
    paso('proveedores', proveedores)

    def idiomas():
        from babelfish import Language
        return f"{Language('spa')} {Language.fromietf('es-ES')} {Language.fromopensubtitles('spa')}"
    paso('idiomas (babelfish)', idiomas)
    def ingles():
        from subtitulos import idioma
        from subtitulos.en import TEXTOS
        idioma.poner('en')
        try:
            texto = idioma.tr('Vídeo {indice} de {total}', indice=1, total=2)
        finally:
            idioma.poner('es')
        if texto != 'Video 1 of 2':
            raise RuntimeError(f'sin traducción: {texto}')
        return f'{len(TEXTOS)} textos traducidos'
    paso('idioma inglés', ingles)
    paso('guessit', lambda: dict(__import__('guessit').guessit('Serie.S01E02.720p.WEB-DL.mkv')))
    def llavero():
        import keyring
        k = keyring.get_keyring()
        if LINUX:     # el del escritorio (KWallet o GNOME Keyring) tiene que ir dentro, aunque aquí no lo haya
            import keyring.backends.SecretService  # noqa: F401
            import secretstorage  # noqa: F401 - sin él, keyring no puede usar el llavero del escritorio
        return f'{type(k).__module__}.{type(k).__name__}'
    paso('keyring', llavero)
    paso('certificados', lambda: __import__('certifi').where())

    def actualizaciones():
        from app import actualizar
        if actualizar.version(__version__) is None:
            raise RuntimeError(f'versión no válida: {__version__}')
        actualizar._contexto_ssl()
        return (f'instalada con el instalador: {actualizar.instalada()} · '
                f'modo: {actualizar.modo_instalacion()} · descargas en {actualizar.carpeta_descargas()}')
    paso('actualizaciones', actualizaciones)

    def menu_contextual():
        """Que el ejecutable lleve QtNetwork (canal entre aperturas) y que el menú se pueda describir."""
        from PySide6.QtCore import QCoreApplication
        from app import instancia, menu_contextual as mc
        _app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841 - QLocalServer la necesita
        servidor = instancia.QLocalServer()
        nombre = f'{instancia.nombre_canal()}-autoprueba'
        if not servidor.listen(nombre):
            raise RuntimeError(f'no se puede abrir el canal local: {servidor.errorString()}')
        servidor.close()
        return mc.describir()
    paso('menú contextual y canal local', menu_contextual)

    def busqueda_sin_red():
        from subtitulos import nucleo
        from subtitulos.opciones import Opciones
        mkv = _mkv_castellano()
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / 'Prueba.S01E01.mkv'
            ruta.write_bytes(mkv)
            r = nucleo.procesar(ruta, Opciones(), credenciales={})
            if [x.estado for x in r] != ['CASTELLANO (incrustado)']:
                raise RuntimeError(f'resultado inesperado: {r}')
            if ruta.with_suffix('.srt').read_text(encoding='utf-8').count('vosotros') != 1:
                raise RuntimeError('el .srt guardado no contiene el texto de la pista')
        return 'MKV con castellano incrustado -> .srt guardado'
    paso('búsqueda (sin red)', busqueda_sin_red)

    def ruta_larga():
        """Una carpeta con acentos y más de 260 caracteres (el antiguo límite MAX_PATH de Windows)."""
        from subtitulos import nucleo
        with tempfile.TemporaryDirectory() as d:
            carpeta = Path(d) / 'Señor de los Anillos – Edición Extendida ñÁÜ'
            while len(str(carpeta)) < 300:
                carpeta = carpeta / f'Temporada con un nombre larguísimo {len(str(carpeta))}'
            try:
                carpeta.mkdir(parents=True)
            except OSError:
                return 'AVISO: Windows no admite rutas largas aquí (LongPathsEnabled desactivado)'
            mkv = _mkv_castellano()
            (carpeta / 'Prueba.S01E01.mkv').write_bytes(mkv)
            r = nucleo.procesar(carpeta, credenciales={})
            if [x.estado for x in r] != ['CASTELLANO (incrustado)'] or not (carpeta / 'Prueba.S01E01.srt').exists():
                raise RuntimeError(f'resultado inesperado con ruta de {len(str(carpeta))} caracteres: {r}')
            return f'{len(str(carpeta))} caracteres -> .srt guardado'
    paso('ruta larga con acentos', ruta_larga)

    def busqueda_con_red():
        from subtitulos import nucleo
        from subtitulos.opciones import Opciones
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / 'Breaking.Bad.S01E01.720p.BluRay.x264-DEMAND.avi'
            ruta.write_bytes(b'\0' * 1024 * 1024)
            # Mismas credenciales que la CLI (credenciales.json), para poder comparar los resultados.
            avisos = []
            eventos = nucleo.Eventos()
            eventos.detalle = lambda linea: avisos.append(linea)
            r = nucleo.procesar(ruta, Opciones(dry_run=True), eventos)
            if not r:
                raise RuntimeError('sin resultado')
            return f'{r[0].estado} · {r[0].fuente}' + ''.join(f'\n        {a}' for a in avisos)
    def consulta_github():
        from app import actualizar
        n = actualizar.consultar('0.0.1')       # como si fuera una versión antigua: siempre hay novedad
        if n is None or n.instalador is None:
            raise RuntimeError(f'sin instalador con huella en la última Release: {n}')
        return f'última versión publicada: {n.version} · {n.instalador.nombre} · sha256 {n.instalador.sha256[:12]}…'
    if con_red:
        paso('búsqueda real (proveedores, simulación)', busqueda_con_red)
        paso('actualizaciones (consulta a GitHub)', consulta_github)
    Path(salida).write_text('\n'.join(lineas) + '\n', encoding='utf-8')
    return 0 if ok else 1


def capturar(app, ventana, carpeta):
    from app.demo import resultados_demo, NOMBRES_EJEMPLO, lineas_demo
    from subtitulos.idioma import tr
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    ventana.setAttribute(Qt.WA_DontShowOnScreen)
    ventana.resize(tema.px(1080), tema.px(720))
    ventana.show()
    resultados = resultados_demo()
    ejemplo = Path('C:/Series/Ejemplo')

    def guardar(nombre):
        for _ in range(3):
            app.processEvents()
        ventana.grab().save(str(carpeta / f'{nombre}.png'))

    for nombre_tema in ('claro', 'oscuro'):
        ventana.cambiar_tema(nombre_tema)
        ventana.ir(0)
        guardar(f'{nombre_tema}_1_reposo')
        ventana.capa.mostrar(tr('Suelta para buscar subtítulos'), 'Serie de Ejemplo - Temporada 1')
        guardar(f'{nombre_tema}_2_arrastrando')
        ventana.capa.hide()
        ventana.inicio.empezar(ejemplo, demo=False)   # sin el aviso de demostración: capturas limpias
        ventana.hay_busqueda = True
        ventana.trabajador = object()          # para ver el menú lateral como durante una búsqueda
        ventana.nav_botones[1].setChecked(True)
        ventana._actualizar_nav()
        ventana.inicio.al_iniciar([ejemplo / n for n in NOMBRES_EJEMPLO])
        for i, r in enumerate(resultados[:6], 1):
            ventana.inicio.al_video(i, len(NOMBRES_EJEMPLO), r.video)
            for linea in lineas_demo(r):
                ventana.inicio.al_detalle(linea)
            ventana.inicio.al_resultado(r)
        ventana.inicio.al_video(7, len(NOMBRES_EJEMPLO), resultados[6].video)
        ventana.inicio.poner_cola(1)
        guardar(f'{nombre_tema}_3_progreso')
        for r in resultados[6:]:
            ventana.inicio.al_resultado(r)
        ventana.inicio.poner_cola(0)
        ventana.trabajador = None
        ventana._actualizar_nav()
        ventana.inicio.terminar(resultados, False, 83)
        guardar(f'{nombre_tema}_4_resumen')
        ventana.inicio.tarjetas['latino'].setChecked(True)
        guardar(f'{nombre_tema}_5_resumen_filtrado')
        ventana.inicio.tarjetas['latino'].setChecked(False)
        ventana.ir(2)
        guardar(f'{nombre_tema}_6_configuracion')
        barra = ventana.ajustes.findChild(QScrollArea).verticalScrollBar()
        barra.setValue(barra.maximum())
        guardar(f'{nombre_tema}_7_configuracion_final')
        barra.setValue(0)


def _pedido(args):
    """Lo que hay que buscar al abrirse: {'rutas', 'recursivo', 'menu'}, o None si no hay nada."""
    from app import menu_contextual as mc
    for opcion, recursivo in ((args.menu_carpeta, False), (args.menu_subcarpetas, True),
                              (args.menu_archivos, True)):
        if opcion:
            return {'rutas': [str(mc.ruta_de_argumento(opcion))], 'recursivo': recursivo, 'menu': True}
    if args.rutas:
        return {'rutas': [str(Path(r).resolve()) for r in args.rutas], 'recursivo': True, 'menu': False}
    return None


def rutas_del_pedido(pedido):
    """Solo carpetas y vídeos que existen (lo que llega por el canal local también se comprueba)."""
    from subtitulos.archivos import es_video
    rutas = pedido.get('rutas') if isinstance(pedido, dict) else None
    if not isinstance(rutas, list):
        return []
    validas = []
    for r in rutas[:5000]:
        if not isinstance(r, str) or not r or len(r) > 4000:
            continue
        p = Path(r)
        try:
            if p.is_absolute() and (p.is_dir() or (p.is_file() and es_video(p))):
                validas.append(p)
        except OSError:
            continue
    return validas


def _menu_desde_instalador(args):
    """El instalador se queda con el menú al instalar o actualizar (si no se había desactivado en
    Configuración); el desinstalador lo quita, apunte a la copia que apunte.

    Al instalar, también apunta el idioma elegido en el instalador, solo si aún no había ninguno (la
    primera instalación, o al actualizar desde una versión sin idiomas): después manda Configuración."""
    from app import menu_contextual
    from app.config import Config
    from subtitulos import idioma
    try:
        if args.menu_contextual_instalar:
            config = Config(args.config)
            if args.idioma_inicial and config.idioma is None:
                config.idioma = args.idioma_inicial
                config.guardar()
            idioma.poner(config.idioma)          # los textos del menú, en el idioma de la app
            menu_contextual.al_instalar(config)
        else:
            menu_contextual.al_desinstalar(Config(args.config))
    except OSError:
        return 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('rutas', nargs='*', metavar='VÍDEO_O_CARPETA')
    ap.add_argument('--tema', choices=('sistema', 'claro', 'oscuro'))
    ap.add_argument('--idioma', choices=('es', 'en'))
    ap.add_argument('--demo', action='store_true')
    ap.add_argument('--captura', metavar='CARPETA')
    ap.add_argument('--config', metavar='ARCHIVO')
    ap.add_argument('--medir-arranque', action='store_true', help=argparse.SUPPRESS)
    ap.add_argument('--autoprueba', metavar='INFORME', help=argparse.SUPPRESS)
    ap.add_argument('--con-red', action='store_true', help=argparse.SUPPRESS)
    # Pruebas de GitHub Actions: lo mismo que pulsar Actualizar con un instalador ya descargado.
    ap.add_argument('--probar-actualizacion', metavar='INSTALADOR', help=argparse.SUPPRESS)
    ap.add_argument('--menu-carpeta', metavar='CARPETA', help=argparse.SUPPRESS)
    ap.add_argument('--menu-subcarpetas', metavar='CARPETA', help=argparse.SUPPRESS)
    ap.add_argument('--menu-archivos', metavar='VÍDEO', help=argparse.SUPPRESS)
    ap.add_argument('--menu-contextual-instalar', action='store_true', help=argparse.SUPPRESS)
    ap.add_argument('--menu-contextual-quitar', action='store_true', help=argparse.SUPPRESS)
    ap.add_argument('--idioma-inicial', choices=('es', 'en'), help=argparse.SUPPRESS)
    ap.add_argument('--pagina', choices=('ajustes',), help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if LINUX:
        from app.plataforma import linux
        linux.entorno_para_otros_programas()
    if args.autoprueba:
        return autoprueba(args.autoprueba, args.con_red)
    if args.menu_contextual_instalar or args.menu_contextual_quitar:
        return _menu_desde_instalador(args)
    pedido = _pedido(args)
    # Una sola app abierta (salvo en las pruebas y capturas): si ya hay una, se le pasa el pedido.
    unica = not (args.demo or args.captura or args.medir_arranque or args.probar_actualizacion)
    from app import instancia
    if unica and not instancia.es_la_primera():
        instancia.permitir_primer_plano()
        return 0 if instancia.enviar(pedido or {'mostrar': True}) else 1
    _identificarse()
    if args.probar_actualizacion:
        from app import actualizar
        actualizar.lanzar_instalador(args.probar_actualizacion)
        time.sleep(3)          # como la app al cerrarse: el instalador tiene que esperar a que termine
        return 0
    app = QApplication(sys.argv[:1])
    app.setApplicationName('Bajar Subtítulos ESP')
    app.setOrganizationName('subtitulos-castellano')
    if LINUX:
        from app.plataforma import linux
        app.setDesktopFileName(linux.ID_ESCRITORIO)     # su icono en la barra de tareas
    from app.config import Config
    config = Config(args.config)
    if args.tema:
        config.tema = args.tema
    from subtitulos import idioma
    idioma.poner(args.idioma or config.idioma)    # antes de crear la ventana: sus textos ya salen así
    tema.aplicar(app, config.tema, config.tamano_texto)
    from app.ventana import AJUSTES, Ventana
    ventana = Ventana(config, demo=args.demo or bool(args.captura))
    if args.captura:
        capturar(app, ventana, args.captura)
        return 0
    if args.pagina == 'ajustes':
        ventana.ir(AJUSTES)
    if unica:
        from app import actualizar, menu_contextual
        menu_contextual.asegurar(config, actualizar.instalada())
        _atender_pedidos(app, ventana, config, args)
    else:
        ventana.al_reiniciar = lambda: _reiniciar(args, ventana.salir)
    if not (pedido and pedido['menu'] and config.menu_segundo_plano and unica):
        ventana.mostrar()
    if pedido and unica:
        app.agrupador.agregar(rutas_del_pedido(pedido), pedido['recursivo'], pedido['menu'])
    elif pedido and rutas_del_pedido(pedido):
        ventana.procesar(rutas_del_pedido(pedido), pedido['recursivo'])
    if not args.demo:
        from app.trabajador import precargar
        QTimer.singleShot(300, precargar)     # subliminal se carga cuando la ventana ya se ve
        QTimer.singleShot(2500, ventana.comprobar_actualizaciones)
    if args.medir_arranque:
        app.processEvents()
        print(f'ventana visible en {time.perf_counter() - _T0:.2f} s '
              f'(subliminal cargado: {"subliminal" in sys.modules})')
        QTimer.singleShot(0, app.quit)
    return app.exec()


def _reiniciar(args, salir, antes=None):
    """Vuelve a abrir la app (en Configuración) para aplicar el idioma nuevo: lanza otra igual y cierra
    esta. `antes` suelta lo que impediría a la nueva ser «la primera» (ver instancia.py)."""
    import subprocess

    from app import menu_contextual
    orden = menu_contextual.programa() + ['--pagina', 'ajustes']
    if args.config:
        orden += ['--config', str(Path(args.config).resolve())]
    if args.demo:
        orden.append('--demo')
    if antes:
        antes()
    try:
        if WINDOWS:
            from app.plataforma import windows
            subprocess.Popen(orden, close_fds=True, creationflags=windows.INDEPENDIENTE)
        else:
            subprocess.Popen(orden, close_fds=True, start_new_session=True)
    except OSError:
        return False
    salir()
    return True


def _atender_pedidos(app, ventana, config, args):
    """Pedidos de esta apertura y de las siguientes (menú contextual, el icono del programa…)."""
    from PySide6.QtWidgets import QSystemTrayIcon

    from app import instancia
    from app.bandeja import Bandeja
    from app.ventana import icono_app

    def salir():
        ventana.salir()          # cancela lo que esté en marcha y guarda la configuración
        config.guardar()
        app.quit()

    app.servidor = instancia.Servidor(app)
    app.servidor.escuchar()

    def soltar_instancia():
        app.servidor.cerrar()
        instancia.soltar()
    ventana.al_reiniciar = lambda: _reiniciar(args, salir, soltar_instancia)
    app.agrupador = instancia.Agrupador(parent=app)
    app.bandeja = Bandeja(ventana, icono_app(), salir, lambda: config.cerrar_a_bandeja, app)
    ventana.puede_ir_a_bandeja = QSystemTrayIcon.isSystemTrayAvailable()
    ventana.ajustes.bandeja_cambiada.connect(app.bandeja.actualizar)
    app.bandeja.actualizar()
    # Al apagar Windows o cerrar sesión, la ventana se cierra de verdad (si no, lo impediría).
    app.commitDataRequest.connect(lambda _gestor: setattr(ventana, '_saliendo', True))

    def recibido(pedido):
        if LINUX:
            from app.plataforma import linux
            linux.usar_token_activacion(pedido.get('activacion'))    # para poder ponerse delante
        if pedido.get('mostrar'):
            ventana.traer_al_frente()
            return
        app.agrupador.agregar(rutas_del_pedido(pedido), pedido.get('recursivo') is not False,
                              pedido.get('menu') is True)

    def buscar(rutas, recursivo, menu):
        if not rutas:
            if not ventana.isVisible() and ventana.trabajador is None:
                ventana.mostrar()          # nada válido que buscar: al menos se abre la app
            return
        if menu and config.menu_segundo_plano and not ventana.isVisible():
            app.bandeja.empezar()
        elif not (menu and config.menu_segundo_plano):
            ventana.traer_al_frente()
        ventana.procesar(rutas, recursivo)

    app.servidor.pedido.connect(recibido)
    app.agrupador.listo.connect(buscar)


if __name__ == '__main__':
    sys.exit(main())
