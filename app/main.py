"""Arranque de Bajar Subtítulos ESP.

    python -I app/main.py [--tema sistema|claro|oscuro] [--captura CARPETA]

--captura guarda imágenes de cada pantalla en claro y oscuro sin mostrar la ventana (sirve para
revisar el diseño).
"""
import time

_T0 = time.perf_counter()

import argparse  # noqa: E402
import sys  # noqa: E402
from pathlib import Path

# Con -I, Python no añade la carpeta del script a sys.path: se añade la raíz del proyecto.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

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
    ventana.resize(1080, 720)
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
        ventana.inicio.mostrar_reposo()
        guardar(f'{nombre_tema}_1_reposo')
        ventana.capa.mostrar('Suelta para buscar subtítulos', 'Serie de Ejemplo - Temporada 1')
        guardar(f'{nombre_tema}_2_arrastrando')
        ventana.capa.hide()
        ventana.inicio.empezar(ejemplo, demo=True)
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
        ventana.inicio.terminar(resultados, False, 83)
        guardar(f'{nombre_tema}_4_resumen')
        ventana.inicio.tarjetas['latino'].setChecked(True)
        guardar(f'{nombre_tema}_5_resumen_filtrado')
        ventana.inicio.tarjetas['latino'].setChecked(False)
        ventana.ir(1)
        guardar(f'{nombre_tema}_6_configuracion')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--tema', choices=('sistema', 'claro', 'oscuro'), default='sistema')
    ap.add_argument('--captura', metavar='CARPETA')
    ap.add_argument('--medir-arranque', action='store_true', help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    _id_windows()
    app = QApplication(sys.argv[:1])
    app.setApplicationName('Bajar Subtítulos ESP')
    app.setOrganizationName('subtitulos-castellano')
    tema.aplicar(app, args.tema)
    from app.ventana import Ventana
    ventana = Ventana(args.tema)
    if args.captura:
        capturar(app, ventana, args.captura)
        return 0
    ventana.show()
    if args.medir_arranque:
        from PySide6.QtCore import QTimer
        app.processEvents()
        print(f'ventana visible en {time.perf_counter() - _T0:.2f} s '
              f'(subliminal cargado: {"subliminal" in sys.modules})')
        QTimer.singleShot(0, app.quit)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
