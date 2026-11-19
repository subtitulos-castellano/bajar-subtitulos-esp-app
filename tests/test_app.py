"""Pruebas de la app (Qt) sin mostrar ventanas, con los proveedores simulados de test_nucleo.

Necesitan PySide6 (venv de la app). Desde WSL:
    scripts/windows.sh python -I tests/test_app.py
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from PySide6.QtCore import QMimeData, Qt, QUrl
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - sin PySide6 (p. ej. el venv de la skill)
    raise unittest.SkipTest('PySide6 no está instalado')

import test_nucleo  # noqa: E402
from subtitulos import eventos as ev  # noqa: E402
from subtitulos.opciones import Opciones  # noqa: E402

APP = QApplication.instance() or QApplication([])

from app import credenciales, tema  # noqa: E402
from app.componentes import FilaOpcion  # noqa: E402
from app.config import Config  # noqa: E402
from app.trabajador import Trabajador  # noqa: E402
from app.ventana import Ventana, rutas_validas  # noqa: E402

tema.aplicar(APP, 'claro')


def esperar(condicion, segundos=20):
    fin = time.monotonic() + segundos
    while not condicion():
        if time.monotonic() > fin:
            raise AssertionError('tiempo de espera agotado')
        APP.processEvents()
        time.sleep(0.01)


CATEGORIAS_S1 = [ev.YA_CASTELLANO, ev.YA_CASTELLANO, ev.CASTELLANO, ev.CASTELLANO, ev.LATINO, ev.INGLES,
                 ev.NO_ENCONTRADO, ev.SIN_CAMBIOS, ev.CASTELLANO, ev.LATINO, ev.PENDIENTE]


class Interruptor(unittest.TestCase):
    def test_no_se_mueve_al_pulsarlo(self):
        """Antes, la animación usaba la propiedad 'pos' de Qt y movía el interruptor a la izquierda."""
        fila = FilaOpcion('Opción', 'explicación')
        fila.resize(600, 60)
        fila.setAttribute(Qt.WA_DontShowOnScreen)
        fila.show()
        APP.processEvents()
        i = fila.control
        antes = i.pos()
        for esperado in (True, False):
            i.click()
            fin = time.monotonic() + 0.4
            while time.monotonic() < fin:
                APP.processEvents()
            self.assertEqual(i.isChecked(), esperado)
            self.assertEqual(i.pos(), antes)


class CamposDeNumero(unittest.TestCase):
    def test_los_limites_se_ven(self):
        """Con NoButtons + hoja de estilos, Qt dejaba el campo con 1 px de ancho y el número no se veía."""
        from app.vista_ajustes import Limite
        lim = Limite(40, 1000)
        lim.setAttribute(Qt.WA_DontShowOnScreen)
        lim.show()
        APP.processEvents()
        self.assertGreater(lim.numero.lineEdit().width(), 40)
        self.assertEqual(lim.numero.lineEdit().text(), '40')


class Configuracion(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self._tmp.name) / 'sub' / 'config.json'

    def tearDown(self):
        self._tmp.cleanup()

    def test_por_defecto_sin_archivo(self):
        c = Config(self.ruta)
        self.assertEqual(c.opciones, Opciones())
        self.assertEqual(c.tema, 'sistema')

    def test_guardar_y_cargar(self):
        c = Config(self.ruta)
        c.opciones = Opciones(force=True, dry_run=True, max_videos=0, max_descargas=9)
        c.tema = 'oscuro'
        c.usuario_opensubtitles = 'pepe'
        c.guardar()
        d = Config(self.ruta)
        self.assertEqual(d.opciones, c.opciones)
        self.assertEqual((d.tema, d.usuario_opensubtitles), ('oscuro', 'pepe'))
        self.assertNotIn('password', self.ruta.read_text(encoding='utf-8'))

    def test_archivo_danado_o_valores_invalidos(self):
        self.ruta.parent.mkdir(parents=True)
        for contenido in ('{no es json', '[1, 2]', json.dumps({'opciones': {'max_videos': -5}, 'tema': 'rosa'}),
                          json.dumps({'opciones': {'max_videos': 'muchos'}})):
            with self.subTest(contenido):
                self.ruta.write_text(contenido, encoding='utf-8')
                c = Config(self.ruta)
                self.assertEqual(c.opciones, Opciones())
                self.assertEqual(c.tema, 'sistema')

    def test_ignora_opciones_desconocidas(self):
        self.ruta.parent.mkdir(parents=True)
        self.ruta.write_text(json.dumps({'opciones': {'force': True, 'futura': 1}}), encoding='utf-8')
        self.assertTrue(Config(self.ruta).opciones.force)


class Credenciales(unittest.TestCase):
    def test_proveedores_solo_con_cuenta_completa(self):
        with mock.patch.object(credenciales, 'leer_clave', lambda u: 'secreta' if u == 'pepe' else ''):
            self.assertEqual(credenciales.credenciales_proveedores('pepe'),
                             {'opensubtitles': {'username': 'pepe', 'password': 'secreta'}})
            self.assertEqual(credenciales.credenciales_proveedores('otro'), {})
            self.assertEqual(credenciales.credenciales_proveedores(''), {})

    def test_importar_de_la_skill(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(credenciales, 'HOME', Path(d)):
            self.assertIsNone(credenciales.credenciales_skill())
            (Path(d) / 'credenciales.json').write_text(
                json.dumps({'opensubtitles': {'username': 'ana', 'password': 'x'}}), encoding='utf-8')
            self.assertEqual(credenciales.credenciales_skill(), ('ana', 'x'))
            (Path(d) / 'credenciales.json').write_text('{"opensubtitles": 3}', encoding='utf-8')
            self.assertIsNone(credenciales.credenciales_skill())


class RutasSoltadas(unittest.TestCase):
    def test_solo_carpetas_y_videos(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / 'serie').mkdir()
            for n in ('a.mkv', 'b.MP4', 'notas.txt', 'sample-c.mkv'):
                (d / n).write_bytes(b'')
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(d / n)) for n in
                          ('serie', 'a.mkv', 'b.MP4', 'notas.txt', 'sample-c.mkv', 'no-existe.mkv')]
                         + [QUrl('https://example.com/x.mkv')])
            self.assertEqual([p.name for p in rutas_validas(mime)], ['serie', 'a.mkv', 'b.MP4'])
            self.assertEqual(rutas_validas(QMimeData()), [])


class TrabajadorReal(test_nucleo.ConSimulacion):
    """El trabajador ejecuta el núcleo de verdad (con proveedores simulados) en otro hilo."""

    def ejecutar(self, opciones, cancelar_tras=None):
        t = Trabajador(self.videos, opciones, {})
        s = {'progreso': [], 'detalles': [], 'resultados': [], 'fin': None, 'errores': []}
        t.video.connect(lambda i, n, p: s['progreso'].append(i))
        t.detalle.connect(s['detalles'].append)
        t.error.connect(s['errores'].append)

        def resultado(r):
            s['resultados'].append(r)
            if cancelar_tras and len(s['resultados']) >= cancelar_tras:
                t.cancelar()
        t.resultado.connect(resultado)
        t.terminado.connect(lambda res, canc, seg: s.__setitem__('fin', (res, canc)))
        t.empezar()
        esperar(lambda: s['fin'] is not None)
        t.esperar()
        return s

    def test_mismos_resultados_que_el_nucleo(self):
        s = self.ejecutar(Opciones(max_videos=7))
        resultados, cancelado = s['fin']
        self.assertFalse(cancelado)
        self.assertEqual(s['errores'], [])
        self.assertEqual([r.categoria for r in resultados], CATEGORIAS_S1)
        self.assertEqual(s['resultados'], resultados)
        self.assertEqual(s['progreso'], list(range(1, 12)))
        self.assertIn('\n== d_red_cast.avi', s['detalles'])
        self.assertTrue((self.videos / 'd_red_cast.srt').exists())

    def test_cancelar(self):
        s = self.ejecutar(Opciones(), cancelar_tras=2)
        resultados, cancelado = s['fin']
        self.assertTrue(cancelado)
        self.assertEqual(len(resultados), 2)

    def test_un_error_no_rompe_la_app(self):
        def falla(*a, **k):
            raise PermissionError('acceso denegado')
        with mock.patch.object(test_nucleo.nucleo, 'scan_video', falla):
            s = self.ejecutar(Opciones())
        resultados, _ = s['fin']
        self.assertEqual(len(resultados), 3)            # los 3 primeros no necesitan internet
        self.assertEqual(s['errores'], ['PermissionError: acceso denegado'])


class VentanaCompleta(test_nucleo.ConSimulacion):
    def test_soltar_procesa_y_muestra_el_resumen(self):
        with tempfile.TemporaryDirectory() as d:
            config = Config(Path(d) / 'config.json')
            config.opciones = Opciones(max_videos=7)
            v = Ventana(config)
            v.procesar([self.videos, self.videos / 'c_incrustado.mkv'])    # el segundo, a la cola
            self.assertEqual(v.cola, [self.videos / 'c_incrustado.mkv'])
            esperar(lambda: v.trabajador is None)
            self.assertEqual(v.inicio.pila.currentIndex(), 2)                # resumen
            self.assertEqual([r.nombre for r in v.inicio.modelo.filas], ['c_incrustado.mkv'])
            self.assertTrue(v.inicio.tarjetas[ev.YA_CASTELLANO].isVisibleTo(v.inicio))
            v.close()
            self.assertTrue(json.loads((Path(d) / 'config.json').read_text(encoding='utf-8'))['geometria'])

    def test_resumen_con_pendientes(self):
        with tempfile.TemporaryDirectory() as d:
            config = Config(Path(d) / 'config.json')
            config.opciones = Opciones(max_videos=7)
            v = Ventana(config)
            v.procesar([self.videos])
            esperar(lambda: v.trabajador is None)
            i = v.inicio
            self.assertEqual(i.tarjetas[ev.PENDIENTE].valor, 1)
            self.assertTrue(i.b_pendientes.isVisibleTo(i))
            self.assertEqual(i.r_titulo.text(), 'Listo, con avisos')
            i.tarjetas[ev.LATINO].click()
            self.assertEqual(i.filtro.rowCount(), 2)
            self.assertIn('==== RESUMEN ====', i._texto_resumen())
            v.close()

    def test_preferencias_se_guardan_al_cambiar(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / 'config.json'
            v = Ventana(Config(ruta))
            v.ajustes.simulacion.click()
            v.ajustes.latino.click()
            guardado = Config(ruta).opciones
            self.assertTrue(guardado.dry_run)
            self.assertTrue(guardado.solo_castellano)
            self.assertIn('Solo castellano', v.inicio.resumen_opciones.text())
            self.assertTrue(v.inicio.banner_sim.isVisibleTo(v.inicio))
            v.ajustes.restaurar()
            self.assertEqual(Config(ruta).opciones, Opciones())
            v.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
