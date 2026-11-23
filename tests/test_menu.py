"""Menú contextual del Explorador, una sola app abierta y búsquedas en segundo plano.

Necesitan PySide6 (venv de la app). Las del registro, Windows (usan una clave de pruebas, nunca el
menú de verdad). Desde WSL:
    scripts/windows.sh python -I tests/test_menu.py
"""
import json
import os
import sys
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon
except ImportError:  # pragma: no cover - sin PySide6 (p. ej. el venv de la skill)
    raise unittest.SkipTest('PySide6 no está instalado')

import test_nucleo  # noqa: E402
from subtitulos import eventos as ev  # noqa: E402
from subtitulos.archivos import buscar_en_varias, buscar_videos  # noqa: E402
from subtitulos.opciones import Opciones  # noqa: E402

APP = QApplication.instance() or QApplication([])

from app import instancia, main, menu_contextual as mc, tema  # noqa: E402
from app.plataforma import menu_windows as mw  # noqa: E402
from app.bandeja import Bandeja, resumen  # noqa: E402
from app.config import Config  # noqa: E402
from app.ventana import Ventana, icono_app  # noqa: E402
from test_app import esperar  # noqa: E402

tema.aplicar(APP, 'claro')
WINDOWS = sys.platform == 'win32'


class SinSubcarpetas(test_nucleo.ConSimulacion):
    def test_buscar_videos(self):
        todos = [p.name for p in buscar_videos(self.videos)]
        solo = [p.name for p in buscar_videos(self.videos, recursivo=False)]
        self.assertIn('k_lat_incrustado.mkv', todos)
        self.assertNotIn('k_lat_incrustado.mkv', solo)
        self.assertEqual(solo, [n for n in todos if n != 'k_lat_incrustado.mkv'])
        self.assertEqual(len(buscar_en_varias([self.videos], recursivo=False)), len(solo))

    def test_nucleo(self):
        r = test_nucleo.nucleo.procesar(self.videos, Opciones(dry_run=True, max_videos=0), credenciales={},
                                        recursivo=False)
        self.assertNotIn('k_lat_incrustado.mkv', [x.nombre for x in r])
        self.assertEqual(len(r), 10)                 # los 10 de la carpeta (sample-x no cuenta)

    def test_ventana_y_procesar_pendientes(self):
        with tempfile.TemporaryDirectory() as d:
            v = Ventana(Config(Path(d) / 'config.json'))
            v.procesar([self.videos], recursivo=False)
            esperar(lambda: v.trabajador is None)
            nombres = [f.nombre for f in v.inicio.modelo.filas]
            self.assertNotIn('k_lat_incrustado.mkv', nombres)
            self.assertTrue(v.inicio.r_sub.text().endswith('sin subcarpetas)'))
            # «Procesar pendientes» repite la búsqueda igual: sin subcarpetas.
            v.inicio.repetir.emit(list(v.inicio.lote))
            esperar(lambda: v.trabajador is None)
            self.assertNotIn('k_lat_incrustado.mkv', [f.nombre for f in v.inicio.modelo.filas])
            v.close()


class ArgumentosDelExplorador(unittest.TestCase):
    def test_raiz_de_una_unidad(self):
        """"%V" en la raíz de una unidad llega como D:" (la barra escapa la comilla)."""
        self.assertEqual(str(mc.ruta_de_argumento('D:"')), str(Path('D:\\')))
        self.assertEqual(str(mc.ruta_de_argumento('D:\\')), str(Path('D:\\')))
        self.assertEqual(mc.ruta_de_argumento(r'C:\Series\Mi serie'), Path(r'C:\Series\Mi serie'))

    def test_pedido(self):
        ap = mock.Mock(menu_carpeta=None, menu_subcarpetas=None, menu_archivos=None, rutas=[])
        self.assertIsNone(main._pedido(ap))
        ap.menu_carpeta = r'C:\Series'
        self.assertEqual(main._pedido(ap), {'rutas': [str(Path(r'C:\Series'))], 'recursivo': False, 'menu': True})
        ap.menu_carpeta, ap.menu_subcarpetas = None, r'C:\Series'
        self.assertTrue(main._pedido(ap)['recursivo'])
        ap.menu_subcarpetas, ap.menu_archivos = None, r'C:\Series\a.mkv'
        self.assertEqual(main._pedido(ap)['recursivo'], True)
        ap.menu_archivos, ap.rutas = None, ['a.mkv']
        self.assertFalse(main._pedido(ap)['menu'])

    def test_solo_rutas_validas(self):
        """Lo que llega por el canal local también se comprueba: carpetas y vídeos que existen."""
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / 'a.mkv').write_bytes(b'x')
            (d / 'b.txt').write_bytes(b'x')
            pedido = {'rutas': [str(d), str(d / 'a.mkv'), str(d / 'b.txt'), str(d / 'no.mkv'), 'a.mkv', 3, '']}
            self.assertEqual(main.rutas_del_pedido(pedido), [d, d / 'a.mkv'])
        for malo in (None, [], {'rutas': 'C:\\'}, {'rutas': None}):
            self.assertEqual(main.rutas_del_pedido(malo), [])


class EntradasDelRegistro(unittest.TestCase):
    PROG = [r'C:\Program Files\Bajar Subtítulos ESP\BajarSubtitulosESP.exe']

    def test_carpetas_con_submenu(self):
        e = mw.entradas(self.PROG)
        for base in (r'Directory\shell', r'Directory\Background\shell', r'Drive\shell'):
            k = rf'{base}\BajarSubtitulosESP'
            self.assertEqual(e[k]['MUIVerb'], 'Bajar subtítulos aquí')
            self.assertEqual(e[k]['SubCommands'], '')
            self.assertEqual(e[k]['Icon'], f'"{self.PROG[0]}",0')
            self.assertEqual(e[rf'{k}\shell\1solo']['MUIVerb'], 'Solo esta carpeta')
            self.assertEqual(e[rf'{k}\shell\2todo']['MUIVerb'], 'Esta carpeta y sus subcarpetas')
            self.assertEqual(e[rf'{k}\shell\1solo\command'][''], f'"{self.PROG[0]}" --menu-carpeta "%V"')
            self.assertEqual(e[rf'{k}\shell\2todo\command'][''], f'"{self.PROG[0]}" --menu-subcarpetas "%V"')

    def test_videos(self):
        e = mw.entradas(self.PROG)
        for ext in ('.mkv', '.mp4', '.avi'):
            k = rf'SystemFileAssociations\{ext}\shell\BajarSubtitulosESP'
            self.assertEqual(e[k]['MUIVerb'], 'Bajar subtítulos')
            self.assertEqual(e[k]['MultiSelectModel'], 'Player')        # también con más de 15
            self.assertEqual(e[rf'{k}\command'][''], f'"{self.PROG[0]}" --menu-archivos "%1"')

    def test_sin_menu_en_ts(self):
        # .ts es también TypeScript: sin menú en esos archivos.
        self.assertFalse(any('.ts' in k for k in mw.entradas(self.PROG)))

    def test_desde_el_codigo_fuente(self):
        prog = [r'C:\venv\Scripts\pythonw.exe', '-I', r'C:\app\main.py']
        self.assertEqual(mw.comando(prog, mc.ARG_CARPETA, '%V'),
                         r'"C:\venv\Scripts\pythonw.exe" -I "C:\app\main.py" --menu-carpeta "%V"')
        self.assertNotIn('Icon', mw.entradas(prog)[r'Directory\shell\BajarSubtitulosESP'])


@unittest.skipUnless(WINDOWS, 'el registro es de Windows')
class Registro(unittest.TestCase):
    """En una clave de pruebas (HKCU\\Software\\BajarSubtitulosESP-pruebas-…), nunca en el menú de verdad."""

    def setUp(self):
        import winreg
        self.winreg = winreg
        self.raiz = rf'Software\BajarSubtitulosESP-pruebas-{uuid.uuid4().hex[:8]}'
        parche = mock.patch.object(mw, 'RAIZ', self.raiz)
        parche.start()
        self.addCleanup(parche.stop)
        self.addCleanup(lambda: mw._borrar_arbol(winreg.HKEY_CURRENT_USER, self.raiz))
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.exe = Path(self._tmp.name) / 'BajarSubtitulosESP.exe'
        self.exe.write_bytes(b'')
        self.config = Config(Path(self._tmp.name) / 'config.json')

    def claves(self):
        """Todas las subclaves que hay bajo la raíz de pruebas."""
        hallado = []

        def recorrer(sub):
            try:
                with self.winreg.OpenKey(self.winreg.HKEY_CURRENT_USER, sub) as k:
                    i = 0
                    while True:
                        try:
                            hija = self.winreg.EnumKey(k, i)
                        except OSError:
                            break
                        hallado.append(rf'{sub}\{hija}')
                        recorrer(rf'{sub}\{hija}')
                        i += 1
            except FileNotFoundError:
                pass
        recorrer(self.raiz)
        return hallado

    def test_registrar_y_quitar(self):
        prog = [str(self.exe)]
        self.assertFalse(mc.registrado())
        mc.registrar(prog)
        self.assertTrue(mc.registrado())
        self.assertTrue(mc.es_de(prog))
        self.assertEqual(mc.programa_registrado(), self.exe)
        escritas = {c.removeprefix(self.raiz + '\\') for c in self.claves()}
        self.assertTrue(set(mw.entradas(prog)) <= escritas)
        with self.winreg.OpenKey(self.winreg.HKEY_CURRENT_USER,
                                 rf'{self.raiz}\SystemFileAssociations\.mkv\shell\BajarSubtitulosESP') as k:
            self.assertEqual(self.winreg.QueryValueEx(k, 'MultiSelectModel')[0], 'Player')
        mc.quitar()
        self.assertFalse(mc.registrado())
        # Solo quedan las claves de los tipos (Directory, .mkv…), vacías: nada de la app.
        self.assertFalse([c for c in self.claves() if 'BajarSubtitulosESP' in c.removeprefix(self.raiz)])

    def test_instalada_sin_decidir_lo_añade(self):
        self.assertTrue(mc.asegurar(self.config, instalada=True, prog=[str(self.exe)]))
        self.assertTrue(mc.registrado())
        self.assertTrue(Config(self.config.ruta).menu_contextual)

    def test_portable_sin_decidir_no_lo_añade(self):
        self.assertFalse(mc.asegurar(self.config, instalada=False, prog=[str(self.exe)]))
        self.assertFalse(mc.registrado())
        self.assertIsNone(self.config.menu_contextual)

    def test_desactivado_no_se_toca(self):
        self.config.menu_contextual = False
        self.assertFalse(mc.asegurar(self.config, instalada=True, prog=[str(self.exe)]))
        self.assertFalse(mc.registrado())

    def test_programa_movido_se_rehace(self):
        movido = Path(self._tmp.name) / 'antes' / 'BajarSubtitulosESP.exe'      # ya no existe
        mc.registrar([str(movido)])
        self.config.menu_contextual = True
        self.assertTrue(mc.asegurar(self.config, instalada=False, prog=[str(self.exe)]))
        self.assertEqual(mc.programa_registrado(), self.exe)

    def test_programa_borrado_sin_activar_se_quita(self):
        borrado = Path(self._tmp.name) / 'borrada' / 'BajarSubtitulosESP.exe'     # portable borrada
        for valor in (None, False):
            mc.registrar([str(borrado)])
            self.config.menu_contextual = valor
            self.assertTrue(mc.asegurar(self.config, instalada=False, prog=[str(self.exe)]))
            self.assertFalse(mc.registrado())

    def test_portable_activado_sin_menu_no_lo_añade(self):
        self.config.menu_contextual = True
        self.assertFalse(mc.asegurar(self.config, instalada=False, prog=[str(self.exe)]))
        self.assertFalse(mc.registrado())

    def test_instalada_activado_sin_menu_lo_añade(self):
        self.config.menu_contextual = True
        self.assertTrue(mc.asegurar(self.config, instalada=True, prog=[str(self.exe)]))
        self.assertTrue(mc.es_de([str(self.exe)]))

    def test_el_instalador_se_queda_con_el_menu(self):
        portable = Path(self._tmp.name) / 'portable' / 'BajarSubtitulosESP.exe'
        portable.parent.mkdir()
        portable.write_bytes(b'')
        mc.registrar([str(portable)])
        self.config.menu_contextual = True
        self.assertTrue(mc.al_instalar(self.config, prog=[str(self.exe)]))
        self.assertTrue(mc.es_de([str(self.exe)]))

    def test_el_instalador_respeta_el_desactivado(self):
        self.config.menu_contextual = False
        self.assertFalse(mc.al_instalar(self.config, prog=[str(self.exe)]))
        self.assertFalse(mc.registrado())

    def test_el_instalador_sin_decidir_lo_añade(self):
        self.assertTrue(mc.al_instalar(self.config, prog=[str(self.exe)]))
        self.assertTrue(Config(self.config.ruta).menu_contextual)

    def test_el_desinstalador_lo_quita_aunque_sea_de_una_portable(self):
        portable = Path(self._tmp.name) / 'portable' / 'BajarSubtitulosESP.exe'
        portable.parent.mkdir()
        portable.write_bytes(b'')
        mc.registrar([str(portable)])
        self.config.menu_contextual = True
        mc.al_desinstalar(self.config)
        self.assertFalse(mc.registrado())
        self.assertIsNone(Config(self.config.ruta).menu_contextual)        # sin decidir
        # La portable ya no lo vuelve a añadir sola; si se reinstala, el instalador sí.
        self.assertFalse(mc.asegurar(Config(self.config.ruta), instalada=False, prog=[str(portable)]))
        self.assertFalse(mc.registrado())
        self.assertTrue(mc.al_instalar(Config(self.config.ruta), prog=[str(self.exe)]))
        self.assertTrue(mc.es_de([str(self.exe)]))

    def test_el_desinstalador_mantiene_el_desactivado(self):
        self.config.menu_contextual = False
        self.config.guardar()
        mc.al_desinstalar(self.config)
        self.assertIs(Config(self.config.ruta).menu_contextual, False)

    def test_otro_programa_que_existe_se_respeta(self):
        otro = Path(self._tmp.name) / 'portable' / 'BajarSubtitulosESP.exe'
        otro.parent.mkdir()
        otro.write_bytes(b'')
        mc.registrar([str(otro)])
        self.config.menu_contextual = True
        self.assertFalse(mc.asegurar(self.config, instalada=True, prog=[str(self.exe)]))
        self.assertEqual(mc.programa_registrado(), otro)
        self.assertFalse(mc.es_de([str(self.exe)]))

    def test_configuracion(self):
        """El interruptor añade y quita el menú; el modo se guarda."""
        v = Ventana(self.config)
        a = v.ajustes
        self.assertFalse(a.menu.isChecked())
        with mock.patch.object(mc, 'programa', lambda: [str(self.exe)]):
            a.menu.click()
        self.assertTrue(mc.registrado())
        self.assertTrue(Config(self.config.ruta).menu_contextual)
        a.b_menu_fondo.click()
        self.assertTrue(Config(self.config.ruta).menu_segundo_plano)
        a.b_menu_ventana.click()
        self.assertFalse(Config(self.config.ruta).menu_segundo_plano)
        a.menu.click()
        self.assertFalse(mc.registrado())
        self.assertIs(Config(self.config.ruta).menu_contextual, False)
        v.close()

    def test_error_al_cambiarlo(self):
        v = Ventana(self.config)
        with mock.patch.object(mc, 'registrar', side_effect=PermissionError(5, 'Acceso denegado')):
            v.ajustes.menu.click()
        self.assertFalse(v.ajustes.menu.isChecked())
        self.assertIn('Acceso denegado', v.ajustes.estado_menu.text())
        self.assertIsNone(Config(self.config.ruta).menu_contextual)
        v.close()


class ConfiguracionNueva(unittest.TestCase):
    def test_guardar_y_cargar(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / 'config.json'
            c = Config(ruta)
            self.assertIsNone(c.menu_contextual)
            self.assertFalse(c.menu_segundo_plano)
            c.guardar()
            self.assertNotIn('menu_contextual', json.loads(ruta.read_text(encoding='utf-8')))
            c.menu_contextual, c.menu_segundo_plano = False, True
            c.guardar()
            c = Config(ruta)
            self.assertIs(c.menu_contextual, False)
            self.assertTrue(c.menu_segundo_plano)
            ruta.write_text('{"menu_contextual": "sí", "menu_segundo_plano": 1}', encoding='utf-8')
            c = Config(ruta)
            self.assertIsNone(c.menu_contextual)
            self.assertFalse(c.menu_segundo_plano)


_SERVIDORES = []      # vivos hasta el final: destruirlos con conexiones recién cerradas puede romper Qt


class UnaSolaApp(unittest.TestCase):
    def servidor(self):
        s = instancia.Servidor()
        self.assertTrue(s.escuchar())
        _SERVIDORES.append(s)
        self.addCleanup(s.servidor.close)
        return s

    def setUp(self):
        nombre = f'BajarSubtitulosESP-pruebas-{uuid.uuid4().hex[:8]}'
        parche = mock.patch.object(instancia, 'nombre_canal', lambda: nombre)
        parche.start()
        self.addCleanup(parche.stop)

    def test_las_demas_aperturas_le_pasan_el_pedido(self):
        servidor = self.servidor()
        recibidos, enviados = [], []
        servidor.pedido.connect(recibidos.append)
        pedidos = [{'rutas': [f'C:\\v\\{i}.mkv'], 'recursivo': True, 'menu': True} for i in range(5)]
        hilos = [threading.Thread(target=lambda p=p: enviados.append(instancia.enviar(p, 10))) for p in pedidos]
        for h in hilos:
            h.start()
        esperar(lambda: len(recibidos) == 5 and len(enviados) == 5)
        for h in hilos:
            h.join()
        self.assertEqual(enviados, [True] * 5)
        self.assertEqual(sorted(p['rutas'][0] for p in recibidos), sorted(p['rutas'][0] for p in pedidos))

    def test_sin_app_abierta_no_se_envia(self):
        self.assertFalse(instancia.enviar({'mostrar': True}, segundos=0.3))

    def test_lo_que_no_es_un_pedido_se_ignora(self):
        servidor = self.servidor()
        recibidos = []
        servidor.pedido.connect(recibidos.append)

        def mandar(datos):
            with mock.patch.object(instancia, 'nombre_canal', lambda: nombre):
                instancia._enviar_tuberia(datos) if WINDOWS else instancia._enviar_qt(datos)
        nombre = instancia.nombre_canal()
        for datos in (b'no es json\n', b'[1, 2]\n', '{"mostrar": true}\n'.encode()):
            h = threading.Thread(target=mandar, args=(datos,))
            h.start()
            esperar(lambda: not h.is_alive())
        self.assertEqual(recibidos, [{'mostrar': True}])

    def test_agrupador_junta_lo_que_llega_seguido(self):
        listos = []
        g = instancia.Agrupador(pausa=150)
        g.listo.connect(lambda r, rec, menu: listos.append((r, rec, menu)))
        for n in ('a.mkv', 'b.mkv', 'a.mkv', 'c.mkv'):
            g.agregar([Path(n)], True, True)
        g.agregar([Path('carpeta')], False, True)
        self.assertEqual(listos, [])
        esperar(lambda: listos, 5)
        self.assertEqual(listos, [([Path('a.mkv'), Path('b.mkv'), Path('c.mkv')], True, True),
                                  ([Path('carpeta')], False, True)])

    def test_agrupador_no_espera_para_siempre(self):
        listos = []
        g = instancia.Agrupador(pausa=10_000, maximo=0)
        g.listo.connect(lambda *a: listos.append(a))
        g.agregar([Path('a.mkv')])
        self.assertEqual(len(listos), 1)


def r(nombre, cat):
    return ev.Resultado(Path(nombre), '', '', cat)


class AvisoFinal(unittest.TestCase):
    def test_todo_bien(self):
        t, x = resumen([r('a', ev.CASTELLANO), r('b', ev.YA_CASTELLANO)], False, [])
        self.assertEqual(t, 'Subtítulos listos')
        self.assertEqual(x, '2 vídeos: 1 castellano, 1 ya lo tenían.')

    def test_con_avisos_y_pendientes(self):
        t, x = resumen([r('a', ev.CASTELLANO), r('b', ev.NO_ENCONTRADO), r('c', ev.PENDIENTE)], False, [])
        self.assertEqual(t, 'Subtítulos listos, con avisos')
        self.assertTrue(x.startswith('3 vídeos: 1 castellano, 1 pendientes, 1 sin subtítulos.'))
        self.assertIn('Procesar pendientes', x)

    def test_error_y_vacio(self):
        self.assertEqual(resumen([], False, ['OSError: disco lleno'])[0], 'Se ha detenido por un error')
        self.assertEqual(resumen([], False, []), ('No hay vídeos', 'No se ha encontrado ningún vídeo.'))


class SegundoPlano(test_nucleo.ConSimulacion):
    def setUp(self):
        super().setUp()
        self._d = tempfile.TemporaryDirectory()
        self.addCleanup(self._d.cleanup)
        self.v = Ventana(Config(Path(self._d.name) / 'config.json'))
        self.salidas = []
        self.b = Bandeja(self.v, icono_app(), lambda: self.salidas.append(1))
        self.avisos = []
        parche = mock.patch.object(self.b.icono, 'showMessage', lambda *a: self.avisos.append(a))
        parche.start()
        self.addCleanup(parche.stop)

    def tearDown(self):
        self.b.icono.hide()
        self.v.ocultar_al_cerrar = False
        self.v.close()
        super().tearDown()

    def test_busca_sin_ventana_y_avisa_al_terminar(self):
        self.b.empezar()
        self.v.procesar([self.videos / 'c_incrustado.mkv', self.videos / 'a_ya.mkv'])
        self.assertTrue(self.b.icono.isVisible())
        esperar(lambda: self.avisos)
        self.assertFalse(self.v.isVisible())
        titulo, texto = self.avisos[0][:2]
        self.assertEqual(titulo, 'Subtítulos listos')
        self.assertEqual(texto, '2 vídeos: 1 castellano, 1 ya lo tenían.')
        self.assertTrue(self.b._fin.isActive())          # sigue un rato por si se pulsa el aviso
        self.assertEqual(self.salidas, [])
        self.b._fin.timeout.emit()
        self.assertEqual(self.salidas, [1])               # y luego se cierra sola
        self.assertFalse(self.b.icono.isVisible())

    def test_pulsar_el_aviso_abre_el_resumen(self):
        self.b.empezar()
        self.v.procesar([self.videos / 'a_ya.mkv'])
        esperar(lambda: self.avisos)
        self.b.icono.messageClicked.emit()
        self.assertTrue(self.v.isVisible())
        self.assertEqual(self.v.inicio.pila.currentIndex(), 2)
        self.assertFalse(self.b.activa)
        self.assertFalse(self.b._fin.isActive())          # ya no se cierra sola
        self.assertEqual(self.salidas, [])

    def test_cerrar_la_ventana_durante_la_busqueda_la_oculta(self):
        with mock.patch.object(test_nucleo.nucleo, 'ProviderPool', PoolLento):
            self.b.empezar()
            self.v.procesar([self.videos])
            self.b.ver()
            self.assertTrue(self.v.isVisible())
            self.v.close()
            self.assertFalse(self.v.isVisible())
            self.assertIsNotNone(self.v.trabajador)      # sigue buscando
            self.b._cancelar()
            esperar(lambda: self.salidas)                # cancelado por el usuario: se cierra sin aviso
        self.assertEqual(self.avisos, [])

    def test_varias_tandas_un_solo_aviso(self):
        self.b.empezar()
        self.v.procesar([self.videos / 'a_ya.mkv'])
        self.v.procesar([self.videos / 'c_incrustado.mkv'])
        esperar(lambda: self.avisos)
        esperar(lambda: self.v.trabajador is None)
        self.assertEqual(len(self.avisos), 1)
        self.assertTrue(self.avisos[0][1].startswith('2 vídeos'))


class JuntoAlReloj(test_nucleo.ConSimulacion):
    """«Al cerrar la ventana, seguir junto al reloj» (Configuración)."""

    def setUp(self):
        super().setUp()
        self._d = tempfile.TemporaryDirectory()
        self.addCleanup(self._d.cleanup)
        self.config = Config(Path(self._d.name) / 'config.json')
        self.config.cerrar_a_bandeja = True
        self.v = Ventana(self.config)
        self.v.puede_ir_a_bandeja = True
        self.salidas = []
        self.b = Bandeja(self.v, icono_app(), lambda: self.salidas.append(1), lambda: self.config.cerrar_a_bandeja)
        self.b.actualizar()
        self.avisos = []
        parche = mock.patch.object(self.b.icono, 'showMessage', lambda *a: self.avisos.append(a))
        parche.start()
        self.addCleanup(parche.stop)

    def tearDown(self):
        self.b.icono.hide()
        self.v.salir()
        super().tearDown()

    def test_cerrar_la_oculta_y_el_icono_la_vuelve_a_abrir(self):
        self.assertTrue(self.b.icono.isVisible())          # con la opción, el icono está siempre
        self.v.mostrar()
        ocultas = []
        self.v.oculta.connect(lambda: ocultas.append(1))
        self.assertFalse(self.v.close())                   # cerrar no cierra
        self.assertFalse(self.v.isVisible())
        self.assertEqual(ocultas, [1])
        self.assertTrue(self.b.icono.isVisible())
        self.b._activado(QSystemTrayIcon.Trigger)
        self.assertTrue(self.v.isVisible())
        self.assertTrue(self.b.icono.isVisible())
        self.assertEqual(self.salidas, [])

    def test_salir_desde_el_icono(self):
        self.v.mostrar()
        self.v.close()
        self.b.a_salir.trigger()
        self.assertEqual(self.salidas, [1])

    def test_salir_cierra_de_verdad(self):
        self.v.mostrar()
        ocultas = []
        self.v.oculta.connect(lambda: ocultas.append(1))
        self.v.salir()
        self.assertEqual(ocultas, [])
        self.assertFalse(self.v.isVisible())

    def test_cerrar_durante_una_busqueda_sigue_y_avisa_sin_cerrarse(self):
        with mock.patch.object(test_nucleo.nucleo, 'ProviderPool', PoolLento):
            self.v.mostrar()
            self.v.procesar([self.videos / 'c_incrustado.mkv', self.videos / 'a_ya.mkv'])
            self.v.close()
            self.assertFalse(self.v.isVisible())
            self.assertTrue(self.b.activa)                 # sigue buscando, en segundo plano
            esperar(lambda: self.avisos)
        self.assertEqual(self.avisos[0][0], 'Subtítulos listos')
        self.b._fin.timeout.emit()
        self.assertEqual(self.salidas, [])                 # con la opción, la app no se cierra sola
        self.assertTrue(self.b.icono.isVisible())
        self.assertFalse(self.b.activa)

    def test_sin_la_opcion_cerrar_cierra(self):
        self.config.cerrar_a_bandeja = False
        self.b.actualizar()
        self.assertFalse(self.b.icono.isVisible())
        self.v.mostrar()
        ocultas = []
        self.v.oculta.connect(lambda: ocultas.append(1))
        self.assertTrue(self.v.close())
        self.assertEqual(ocultas, [])

    def test_la_opcion_se_guarda(self):
        self.v.ajustes.bandeja.setChecked(False)
        self.assertFalse(Config(self.config.ruta).cerrar_a_bandeja)
        self.v.ajustes.bandeja.setChecked(True)
        self.assertTrue(Config(self.config.ruta).cerrar_a_bandeja)


class PoolLento(test_nucleo.PoolFalso):
    def list_subtitles(self, *a, **k):
        import time
        time.sleep(0.3)
        return super().list_subtitles(*a, **k)


if __name__ == '__main__':
    unittest.main(verbosity=2)
