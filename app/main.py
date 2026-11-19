"""Arranque de Bajar Subtítulos ESP.

    python -I app/main.py [--tema sistema|claro|oscuro] [--demo] [--captura CARPETA] [--config ARCHIVO]

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

ID_APP = 'subtitulos-castellano.BajarSubtitulosESP'


def _id_windows():
    """Para que Windows agrupe la app en la barra de tareas con su propio icono."""
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ID_APP)


def capturar(app, ventana, carpeta):
    from app.demo import resultados_demo, NOMBRES_EJEMPLO, lineas_demo
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
        ventana.capa.mostrar('Suelta para buscar subtítulos', 'Serie de Ejemplo - Temporada 1')
        guardar(f'{nombre_tema}_2_arrastrando')
        ventana.capa.hide()
        ventana.inicio.empezar(ejemplo, demo=True)
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


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--tema', choices=('sistema', 'claro', 'oscuro'))
    ap.add_argument('--demo', action='store_true')
    ap.add_argument('--captura', metavar='CARPETA')
    ap.add_argument('--config', metavar='ARCHIVO')
    ap.add_argument('--medir-arranque', action='store_true', help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    _id_windows()
    app = QApplication(sys.argv[:1])
    app.setApplicationName('Bajar Subtítulos ESP')
    app.setOrganizationName('subtitulos-castellano')
    from app.config import Config
    config = Config(args.config)
    if args.tema:
        config.tema = args.tema
    tema.aplicar(app, config.tema, config.tamano_texto)
    from app.ventana import Ventana
    ventana = Ventana(config, demo=args.demo or bool(args.captura))
    if args.captura:
        capturar(app, ventana, args.captura)
        return 0
    ventana.mostrar()
    if not args.demo:
        from app.trabajador import precargar
        QTimer.singleShot(300, precargar)     # subliminal se carga cuando la ventana ya se ve
    if args.medir_arranque:
        app.processEvents()
        print(f'ventana visible en {time.perf_counter() - _T0:.2f} s '
              f'(subliminal cargado: {"subliminal" in sys.modules})')
        QTimer.singleShot(0, app.quit)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
