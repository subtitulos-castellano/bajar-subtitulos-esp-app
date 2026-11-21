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

from app import __version__, actualizar, credenciales, tema  # noqa: E402
from app.componentes import FilaOpcion  # noqa: E402
from app.config import Config  # noqa: E402
from app.trabajador import Trabajador  # noqa: E402
from app.ventana import AJUSTES, BUSCANDO, INICIO, Ventana, rutas_validas  # noqa: E402

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

    def test_actualizaciones(self):
        c = Config(self.ruta)
        self.assertEqual((c.actualizaciones, c.ultima_comprobacion, c.version), (True, 0.0, ''))
        c.actualizaciones, c.ultima_comprobacion, c.version = False, 1795000000.5, '1.0.1'
        c.guardar()
        d = Config(self.ruta)
        self.assertEqual((d.actualizaciones, d.ultima_comprobacion, d.version), (False, 1795000000.5, '1.0.1'))
        for malo in ({'actualizaciones': 'no'}, {'ultima_comprobacion': -1}, {'ultima_comprobacion': True},
                     {'version': 7}, {'version': 'x' * 50}):
            with self.subTest(malo):
                self.ruta.write_text(json.dumps(malo), encoding='utf-8')
                c = Config(self.ruta)
                self.assertEqual((c.actualizaciones, c.ultima_comprobacion, c.version), (True, 0.0, ''))


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
        with mock.patch.object(test_nucleo.nucleo, 'ProviderPool', PoolLento):
            s = self.ejecutar(Opciones(), cancelar_tras=3)    # cuando d_red_cast espera al proveedor
        resultados, cancelado = s['fin']
        self.assertTrue(cancelado)
        self.assertEqual(len(resultados), 3)

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
            v.mostrar()
            v.procesar([self.videos])
            v.procesar([self.videos / 'c_incrustado.mkv'])                  # soltado después: a la cola
            self.assertEqual(v.cola, [[self.videos / 'c_incrustado.mkv']])
            esperar(lambda: v.trabajador is None)
            self.assertEqual(v.inicio.pila.currentIndex(), 2)                # resumen
            self.assertEqual([r.nombre for r in v.inicio.modelo.filas], ['c_incrustado.mkv'])
            self.assertTrue(v.inicio.tarjetas[ev.YA_CASTELLANO].isVisibleTo(v.inicio))
            v.close()
            self.assertGreater(json.loads((Path(d) / 'config.json').read_text(encoding='utf-8'))['ventana']['ancho'], 0)

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


class PoolLento(test_nucleo.PoolFalso):
    """Proveedor que tarda 3 s en responder."""

    def list_subtitles(self, video, languages):
        time.sleep(3)
        return super().list_subtitles(video, languages)


class CancelarAlMomento(test_nucleo.ConSimulacion):
    def test_la_interfaz_no_espera_a_la_consulta_en_curso(self):
        with mock.patch.object(test_nucleo.nucleo, 'ProviderPool', PoolLento):
            t = Trabajador(self.videos, Opciones(), {})
            s = {'fin': None, 'tras_cancelar': []}
            t.terminado.connect(lambda res, canc, seg: s.__setitem__('fin', (res, canc)))

            def video(i, n, path):
                if path.name == 'd_red_cast.avi':          # primer vídeo que consulta a internet
                    QTimerSingleShot(300, cancelar)
            t.video.connect(video)

            def cancelar():
                s['pulsado'] = time.monotonic()
                t.cancelar()
                s['respuesta'] = time.monotonic() - s['pulsado']
            t.resultado.connect(lambda r: s['tras_cancelar'].append(r) if 'pulsado' in s else None)
            t.empezar()
            esperar(lambda: s['fin'] is not None)
            self.assertLess(s['respuesta'], 0.1)            # la interfaz se entera al instante
            resultados, cancelado = s['fin']
            self.assertTrue(cancelado)
            self.assertEqual(len(resultados), 3)
            t.esperar(10)                                   # el hilo termina su consulta y para
            self.assertFalse(t.activo())
            self.assertEqual(s['tras_cancelar'], [])        # nada llega a la interfaz después
            self.assertFalse((self.videos / 'd_red_cast.srt').exists())   # ni se escribe


def QTimerSingleShot(ms, funcion):
    from PySide6.QtCore import QTimer
    QTimer.singleShot(ms, funcion)


class MenuLateralYTabla(test_nucleo.ConSimulacion):
    def setUp(self):
        super().setUp()
        self._d = tempfile.TemporaryDirectory()
        config = Config(Path(self._d.name) / 'config.json')
        config.opciones = Opciones(max_videos=7)
        self.v = Ventana(config)

    def espiar_video(self, funcion):
        """Llama a `funcion` en cada vídeo, ANTES de empezar la búsqueda (con los proveedores simulados
        va tan rápido que, si se conecta después, los primeros avisos ya han pasado)."""
        original = self.v.inicio.al_video

        def espia(*args):
            original(*args)
            funcion(*args)
        parche = mock.patch.object(self.v.inicio, 'al_video', espia)
        parche.start()
        self.addCleanup(parche.stop)

    def tearDown(self):
        self.v.close()
        self._d.cleanup()
        super().tearDown()

    def test_estados_del_menu(self):
        v, nav = self.v, self.v.nav_botones
        self.assertTrue(nav[INICIO].isChecked())
        self.assertFalse(nav[BUSCANDO].isEnabled())            # sin búsqueda, no se puede pulsar
        estados = []

        def al_video(*a):
            estados.append((nav[INICIO].isEnabled(), nav[BUSCANDO].isChecked(), nav[AJUSTES].isEnabled()))
        self.espiar_video(al_video)
        v.procesar([self.videos])
        esperar(lambda: v.trabajador is None)
        self.assertTrue(estados)
        self.assertTrue(all(e == (False, True, False) for e in estados))   # buscando: solo 'Buscando…'
        self.assertTrue(nav[INICIO].isEnabled() and nav[AJUSTES].isEnabled())
        self.assertTrue(nav[BUSCANDO].isChecked() and nav[BUSCANDO].isEnabled())
        v.ir(AJUSTES)
        v.ir(BUSCANDO)                                          # se puede volver al resumen
        self.assertEqual(v.inicio.pila.currentIndex(), 2)
        v.ir(INICIO)
        self.assertEqual(v.inicio.pila.currentIndex(), 0)       # la pantalla del principio
        self.assertFalse(nav[BUSCANDO].isEnabled())

    def test_lista_completa_desde_el_principio(self):
        v = self.v
        capturas = []

        def al_video(i, total, path):
            capturas.append([f.categoria for f in v.inicio.modelo.filas])
        self.espiar_video(al_video)
        v.procesar([self.videos])
        self.assertTrue(v.inicio.detalles_p.boton.isChecked())   # Detalles abierto al empezar
        esperar(lambda: v.trabajador is None)
        primera = capturas[0]
        self.assertEqual(len(primera), 11)                        # todos los vídeos, desde el principio
        self.assertEqual(primera[0], tema.BUSCANDO)
        self.assertTrue(all(c == tema.EN_ESPERA for c in primera[1:]))
        quinta = capturas[4]
        self.assertEqual(quinta[4], tema.BUSCANDO)
        self.assertNotIn(tema.EN_ESPERA, quinta[:4])
        self.assertEqual([f.categoria for f in v.inicio.modelo.filas], CATEGORIAS_S1)

    def test_tras_cancelar_lo_que_falta_queda_no_revisado(self):
        v = self.v
        with mock.patch.object(test_nucleo.nucleo, 'ProviderPool', PoolLento):
            v.procesar([self.videos])
            # Cancelar mientras d_red_cast espera al proveedor (3 s).
            v.trabajador.video.connect(lambda i, n, p: v._cancelar() if p.name == 'd_red_cast.avi' else None)
            inicio = time.monotonic()
            esperar(lambda: v.trabajador is None)
            self.assertLess(time.monotonic() - inicio, 2.5)    # no espera a que responda el proveedor
        cats = [f.categoria for f in v.inicio.modelo.filas]
        self.assertEqual(cats[:3], [ev.YA_CASTELLANO, ev.YA_CASTELLANO, ev.CASTELLANO])
        self.assertTrue(all(c == tema.NO_REVISADO for c in cats[3:]))
        self.assertEqual(v.inicio.r_titulo.text(), 'Cancelado')
        self.assertEqual(v.inicio.tarjetas[tema.NO_REVISADO].valor, 8)
        self.assertIn('3 de 11', v.inicio.r_sub.text())
        time.sleep(3.2)                                        # el hilo acaba su consulta en segundo plano...
        APP.processEvents()
        self.assertEqual([f.categoria for f in v.inicio.modelo.filas], cats)    # ...sin tocar el resumen
        self.assertFalse((self.videos / 'd_red_cast.srt').exists())

    def test_un_solo_video_anima_la_barra(self):
        v = self.v
        animada = []
        self.espiar_video(lambda *a: animada.append(v.inicio.barra.trabajando))
        v.procesar([self.videos / 'd_red_cast.avi'])
        esperar(lambda: v.trabajador is None)
        self.assertEqual(animada, [True])
        self.assertFalse(v.inicio.barra.trabajando)


    def test_varios_videos_sueltos_son_una_sola_busqueda(self):
        v = self.v
        sueltos = [self.videos / 'z_pend.avi', self.videos / 'c_incrustado.mkv', self.videos / 'a_ya.mkv']
        filas = []
        self.espiar_video(lambda *a: filas.append(len(v.inicio.modelo.filas)))
        v.procesar(sueltos)                                   # se sueltan los tres a la vez
        self.assertEqual(v.cola, [])                          # nada en cola: una sola búsqueda
        esperar(lambda: v.trabajador is None)
        self.assertEqual(filas, [3, 3, 3])                   # los tres en la tabla desde el principio
        self.assertEqual([f.nombre for f in v.inicio.modelo.filas], ['z_pend.avi', 'c_incrustado.mkv', 'a_ya.mkv'])
        self.assertIn('3 elementos de', v.inicio.r_sub.text())
        self.assertEqual(v.inicio.ruta_actual, self.videos)   # 'Abrir carpeta' abre la que los contiene


class PosicionDeLaVentana(unittest.TestCase):
    def test_se_recuerda_sin_desplazarse(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / 'config.json'
            c = Config(ruta)
            c.ventana = {'x': 40, 'y': 30, 'ancho': 1500, 'alto': 950, 'maximizada': False}
            c.guardar()
            for _ in range(3):                       # abrir y cerrar varias veces: no debe moverse
                v = Ventana(Config(ruta))
                v.mostrar()
                APP.processEvents()
                v.close()
            self.assertEqual(Config(ruta).ventana, c.ventana)

    def test_fuera_de_la_pantalla_no_se_mueve_alli(self):
        with tempfile.TemporaryDirectory() as d:
            c = Config(Path(d) / 'config.json')
            c.ventana = {'x': 50000, 'y': 50000, 'ancho': 900, 'alto': 620, 'maximizada': False}
            v = Ventana(c)
            self.assertLess(v.pos().x(), 10000)
            v.close()


class TamanoDelTexto(unittest.TestCase):
    def tearDown(self):
        tema.aplicar(APP, 'claro')

    def test_escala_todo(self):
        tema.aplicar(APP, 'claro', 150)
        self.assertEqual(tema.px(100), 150)
        self.assertAlmostEqual(APP.font().pointSizeF(), 15)
        self.assertIn('font-size: 15.00pt', APP.styleSheet())
        tema.aplicar(APP, 'claro', 100)
        self.assertEqual(tema.px(100), 100)

    def test_como_windows_por_defecto(self):
        tema.aplicar(APP, 'claro', 0)
        self.assertAlmostEqual(tema.escala(), tema.escala_windows() / 100)

    def test_configuracion(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / 'config.json'
            v = Ventana(Config(ruta))
            a = v.ajustes
            a.b_tamano_propio.click()
            a.tamano.setValue(140)
            a._aplicar_tamano()                      # (normalmente, 0,4 s después de dejar de cambiarlo)
            self.assertEqual(Config(ruta).tamano_texto, 140)
            self.assertEqual(tema.px(100), 140)
            a.b_tamano_windows.click()
            self.assertEqual(Config(ruta).tamano_texto, 0)
            v.close()
        for valor, esperado in ((300, 0), (50, 0), ('120', 0), (True, 0), (120, 120)):
            with tempfile.TemporaryDirectory() as d:
                ruta = Path(d) / 'config.json'
                ruta.write_text(json.dumps({'tamano_texto': valor}), encoding='utf-8')
                self.assertEqual(Config(ruta).tamano_texto, esperado)


NOVEDAD = actualizar.Novedad(
    '99.0.0', 'https://github.com/subtitulos-castellano/bajar-subtitulos-esp-app/releases/tag/v99.0.0',
    '• Actualizaciones automáticas\n• <b>no es HTML</b>',
    actualizar.Archivo('BajarSubtitulosESP-99.0.0-instalador.exe', 'https://github.com/x', 'ab' * 32, 10))


class Actualizaciones(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.addCleanup(self._d.cleanup)
        self.ruta = Path(self._d.name) / 'config.json'
        c = Config(self.ruta)
        c.version = __version__
        c.guardar()
        self.v = Ventana(Config(self.ruta))
        self.v.setAttribute(Qt.WA_DontShowOnScreen)
        self.v.show()
        self.addCleanup(self.v.close)
        APP.processEvents()

    def test_opcion_en_configuracion(self):
        a = self.v.ajustes
        self.assertTrue(a.auto_actualizar.isChecked())
        a.auto_actualizar.click()
        self.assertFalse(Config(self.ruta).actualizaciones)
        self.assertFalse(self.v.actualizador.toca())           # desactivada: no se comprueba al abrir
        a.auto_actualizar.click()
        self.assertTrue(Config(self.ruta).actualizaciones)

    def test_como_mucho_una_vez_al_dia(self):
        act = self.v.actualizador
        self.assertTrue(act.toca())
        self.v.config.ultima_comprobacion = time.time() - 3600
        self.assertFalse(act.toca())
        self.v.config.ultima_comprobacion = time.time() - 25 * 3600
        self.assertTrue(act.toca())

    def test_buscar_ahora(self):
        a = self.v.ajustes
        with mock.patch.object(actualizar, 'consultar', return_value=None):
            a.b_buscar_version.click()
            esperar(lambda: 'última versión' in a.estado_version.text())
        self.assertTrue(a.b_buscar_version.isEnabled())
        self.assertGreater(Config(self.ruta).ultima_comprobacion, 0)
        with mock.patch.object(actualizar, 'consultar', side_effect=actualizar.ErrorActualizacion('Sin red.')):
            a.b_buscar_version.click()
            esperar(lambda: 'No se ha podido comprobar: Sin red.' in a.estado_version.text())
        self.assertFalse(self.v.marco_aviso.isVisible())       # un fallo no molesta con avisos

    def test_aviso_de_version_nueva(self):
        v = self.v
        with mock.patch.object(actualizar, 'consultar', return_value=NOVEDAD), \
                mock.patch.object(actualizar, 'instalada', return_value=True):
            v.actualizador.comprobar()
            esperar(lambda: v.marco_aviso.isVisible())
        aviso = v.aviso
        self.assertEqual(aviso.estado, 'disponible')
        self.assertEqual(aviso.titulo.text(), 'Hay una versión nueva: 99.0')
        self.assertEqual(aviso.b_accion.text(), 'Actualizar')
        self.assertIn('Hay una versión nueva: 99.0', v.ajustes.estado_version.text())
        self.assertFalse(aviso.notas.isVisible())
        aviso.b_notas.click()
        self.assertTrue(aviso.notas.isVisible())
        self.assertEqual(aviso.notas.textFormat(), Qt.PlainText)      # las notas nunca se pintan como HTML
        aviso.b_tarde.click()
        self.assertFalse(v.marco_aviso.isVisible())

    def test_version_portable_solo_ofrece_la_descarga(self):
        v = self.v
        with mock.patch.object(actualizar, 'instalada', return_value=False):
            v._novedad(NOVEDAD, False)
        self.assertEqual(v.aviso.estado, 'portable')
        self.assertEqual(v.aviso.b_accion.text(), 'Descargar')
        with mock.patch.object(actualizar, 'descargar') as descargar, \
                mock.patch('app.ventana.QDesktopServices.openUrl') as abrir:
            v.aviso.b_accion.click()
        descargar.assert_not_called()
        self.assertEqual(abrir.call_args.args[0].toString(), NOVEDAD.pagina)

    def test_no_se_actualiza_durante_una_busqueda(self):
        v = self.v
        with mock.patch.object(actualizar, 'instalada', return_value=True):
            v._novedad(NOVEDAD, False)
        v.trabajador = object()
        v._actualizar_nav()
        self.assertFalse(v.aviso.b_accion.isEnabled())
        v.trabajador = None
        v._actualizar_nav()
        self.assertTrue(v.aviso.b_accion.isEnabled())

    def test_actualizar_descarga_instala_y_cierra(self):
        v = self.v
        with mock.patch.object(actualizar, 'instalada', return_value=True):
            v._novedad(NOVEDAD, False)
        ruta = Path(self._d.name) / NOVEDAD.instalador.nombre

        def descargar(archivo, progreso=None, cancelada=None):
            self.assertEqual(archivo, NOVEDAD.instalador)
            progreso(5, 10)
            return ruta
        with mock.patch.object(actualizar, 'descargar', side_effect=descargar), \
                mock.patch.object(actualizar, 'lanzar_instalador') as lanzar:
            v.aviso.b_accion.click()
            esperar(lambda: lanzar.called)
            APP.processEvents()
        lanzar.assert_called_once_with(ruta)
        self.assertEqual(v.aviso.estado, 'instalando')
        self.assertFalse(v.isVisible())                       # la app se cierra para que se instale

    def test_fallo_al_descargar(self):
        v = self.v
        with mock.patch.object(actualizar, 'instalada', return_value=True):
            v._novedad(NOVEDAD, False)
        with mock.patch.object(actualizar, 'descargar',
                               side_effect=actualizar.ErrorActualizacion('No coincide la huella.')), \
                mock.patch.object(actualizar, 'lanzar_instalador') as lanzar:
            v.aviso.b_accion.click()
            esperar(lambda: v.aviso.estado == 'error')
        lanzar.assert_not_called()
        self.assertEqual(v.aviso.detalle.text(), 'No coincide la huella.')
        self.assertEqual(v.aviso.b_accion.text(), 'Reintentar')
        self.assertTrue(v.isVisible())

    def test_aviso_tras_actualizarse(self):
        for anterior, aviso in (('0.9.0', True), (__version__, False), ('', False), ('basura', False)):
            with self.subTest(anterior):
                c = Config(self.ruta)
                c.version = anterior
                c.guardar()
                v = Ventana(Config(self.ruta))
                self.assertEqual(v.aviso.estado == 'actualizada', aviso)
                self.assertEqual(Config(self.ruta).version, __version__)    # solo se avisa una vez
                v.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
