"""Idioma de la app (castellano o inglés): traducciones completas, núcleo, Configuración y recarga.

Las de la traducción y del núcleo solo necesitan la biblioteca estándar y subliminal; las de la
ventana, PySide6 (venv de la app). Desde WSL:
    scripts/windows.sh python -I tests/test_idioma.py
"""
import ast
import json
import os
import re
import string
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_nucleo  # noqa: E402
from subtitulos import idioma  # noqa: E402
from subtitulos.en import TEXTOS  # noqa: E402
from subtitulos.idioma import tr  # noqa: E402


class EnIngles:
    """Mezcla para pruebas: inglés durante la prueba y castellano al terminar (el resto lo espera)."""

    def setUp(self):
        super().setUp()
        idioma.poner('en')
        self.addCleanup(idioma.poner, 'es')


def _textos_marcados():
    """{texto: [archivo:línea]} de todo lo que va en tr('…') o N_('…') en la app y el núcleo, y la
    lista de llamadas con algo que no es un texto fijo."""
    marcados, variables = {}, []
    for archivo in sorted((RAIZ / 'app').glob('*.py')) + sorted((RAIZ / 'subtitulos').glob('*.py')):
        for n in ast.walk(ast.parse(archivo.read_text(encoding='utf-8'))):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ('tr', 'N_') and n.args:
                donde = f'{archivo.relative_to(RAIZ).as_posix()}:{n.lineno}'
                if isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                    marcados.setdefault(n.args[0].value, []).append(donde)
                else:
                    variables.append(donde)
    return marcados, variables


def _campos(texto):
    return sorted((c, f) for _, c, f, _ in string.Formatter().parse(texto) if c is not None)


class Traducciones(unittest.TestCase):
    def test_todo_tiene_traduccion(self):
        marcados, _ = _textos_marcados()
        faltan = {t: d for t, d in marcados.items() if t not in TEXTOS}
        self.assertEqual(faltan, {}, 'textos sin traducir en subtitulos/en.py')

    def test_no_sobra_ninguna(self):
        marcados, _ = _textos_marcados()
        self.assertEqual([t for t in TEXTOS if t not in marcados], [], 'traducciones que ya no se usan')

    def test_mismos_campos(self):
        distintos = {k: v for k, v in TEXTOS.items() if _campos(k) != _campos(v)}
        self.assertEqual(distintos, {})

    def test_mismos_espacios_al_principio(self):
        """Las líneas de Detalles van sangradas: la traducción, igual."""
        distintos = [k for k, v in TEXTOS.items() if len(k) - len(k.lstrip(' ')) != len(v) - len(v.lstrip(' '))]
        self.assertEqual(distintos, [])

    def test_sin_restos_de_castellano(self):
        castellano = re.compile(r'[áéíóúñ¿¡]|\b(de|el|los|las|que|por|para|con|vídeo)\b', re.IGNORECASE)
        permitidos = {'Abrir Bajar Subtítulos ESP': 'Open Bajar Subtítulos ESP'}   # el nombre no se traduce
        restos = {k: v for k, v in TEXTOS.items() if castellano.search(re.sub(r'\{[^}]*\}', '', v).replace('Bajar Subtítulos ESP', ''))
                  and k not in permitidos}
        self.assertEqual(restos, {})

    def test_llamadas_con_variables_solo_donde_toca(self):
        """tr(variable) solo para lo marcado con N_ (estados, columnas, menú…): si aparece otra, revisar
        que lo que recibe esté marcado y añadirla aquí."""
        _, variables = _textos_marcados()
        archivos = sorted({d.split(':')[0] for d in variables})
        self.assertEqual(archivos, ['app/bandeja.py', 'app/componentes.py', 'app/demo.py', 'app/menu_contextual.py',
                                    'app/tema.py', 'subtitulos/nucleo.py'])

    def test_tr(self):
        self.assertEqual(tr('Vídeo {indice} de {total}', indice=2, total=5), 'Vídeo 2 de 5')
        idioma.poner('en')
        self.addCleanup(idioma.poner, 'es')
        self.assertEqual(tr('Vídeo {indice} de {total}', indice=2, total=5), 'Video 2 of 5')
        self.assertEqual(tr('Un texto que no está'), 'Un texto que no está')
        idioma.poner('fr')
        self.assertEqual(idioma.actual(), 'es')


class NucleoEnIngles(EnIngles, test_nucleo.ConSimulacion):
    def test_resumen_y_detalles(self):
        from subtitulos import nucleo
        from subtitulos.opciones import Opciones
        g = test_nucleo.Grabadora()
        r = nucleo.procesar(self.videos, Opciones(max_videos=7, dry_run=True), g)
        estados = {x.nombre: (x.estado, x.fuente) for x in r}
        self.assertEqual(estados['c_incrustado.mkv'], ('SPANISH FROM SPAIN (embedded)', 'track 1 Español (España)'))
        self.assertEqual(estados['b_renombra.mp4'], ('already had Spanish from Spain', 'renamed from .es.srt'))
        self.assertEqual(estados['h_latino_previo.avi'], ('LATIN AMERICAN (already had .srt)', '-'))
        self.assertEqual(estados['g_nada.avi'], ('NOT FOUND', 'no Spanish or English'))
        self.assertEqual(estados['z_pend.avi'], ('PENDING (limit)', 'max. 7 per run'))
        texto = '\n'.join(g.lineas)
        for linea in ('  2 embedded subtitle tracks', '  embedded track 1 [spa] Español (España): spain=5 latam=0',
                      '  already has i_mejora.srt in English', '  [dry-run] would save d_red_cast.srt',
                      '  limit of 7 videos searched online reached: left for another run'):
            self.assertIn(linea, texto)
        self.assertIn('sync=18 spain=6 latam=0 episode_ok=True duration_ok=True', texto)
        self.assertNotRegex(texto, r'pista|españa=|guardaría|ya tiene')

    def test_la_cli_sigue_en_castellano(self):
        """La CLI y la skill no eligen idioma: en una ejecución normal, castellano."""
        idioma.poner('es')
        from subtitulos import pistas
        self.assertIn('unos 40 s', pistas.aviso_lento(pistas.Lento(40)))


class NotasDeLaRelease(unittest.TestCase):
    NOTAS = ('- **Idioma**: inglés.\n\n<!-- en -->\n\n### English\n\n- **Language**: English.')

    def test_cada_idioma_su_parte(self):
        from app import actualizar
        self.assertEqual(actualizar.notas_del_idioma(self.NOTAS, 'es').strip(), '- **Idioma**: inglés.')
        self.assertEqual(actualizar.notas_del_idioma(self.NOTAS, 'en').strip(), '- **Language**: English.')
        self.assertEqual(actualizar.limpiar_notas(self.NOTAS), '• Idioma: inglés.')
        idioma.poner('en')
        self.addCleanup(idioma.poner, 'es')
        self.assertEqual(actualizar.limpiar_notas(self.NOTAS), '• Language: English.')

    def test_releases_anteriores_solo_en_castellano(self):
        from app import actualizar
        self.assertEqual(actualizar.notas_del_idioma('- Algo nuevo.', 'en'), '- Algo nuevo.')


try:
    from PySide6.QtWidgets import QAbstractButton, QApplication, QLabel, QLineEdit, QWidget
except ImportError:  # pragma: no cover - sin PySide6 (p. ej. el venv de la skill)
    QApplication = None


@unittest.skipIf(QApplication is None, 'PySide6 no está instalado')
class App(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from app import tema
        tema.aplicar(cls.app, 'claro')

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ruta = Path(self._tmp.name) / 'config.json'
        self.addCleanup(idioma.poner, 'es')

    def ventana(self, codigo=None, **config):
        from app.config import Config
        from app.ventana import Ventana
        if codigo or config:
            datos = dict(config)
            if codigo:
                datos['idioma'] = codigo
            self.ruta.write_text(json.dumps(datos), encoding='utf-8')
        c = Config(self.ruta)
        idioma.poner(c.idioma)
        v = Ventana(c, demo=True)
        self.addCleanup(v.close)
        return v

    def test_configuracion(self):
        from app.config import Config
        self.assertIsNone(Config(self.ruta).idioma)
        for valor in ('fr', 3, None, 'EN'):
            self.ruta.write_text(json.dumps({'idioma': valor}), encoding='utf-8')
            self.assertIsNone(Config(self.ruta).idioma)
        c = Config(self.ruta)
        c.idioma = 'en'
        c.guardar()
        self.assertEqual(Config(self.ruta).idioma, 'en')

    def test_toda_la_ventana_en_ingles(self):
        """Ningún texto a la vista (ni ayuda emergente) con restos de castellano."""
        from app.ventana import AJUSTES
        v = self.ventana('en')
        v.ir(AJUSTES)
        castellano = re.compile(r'[áéíóúñ¿¡]|\b(de|el|los|las|que|por|para|con|una?|vídeos?)\b', re.IGNORECASE)
        permitidos = {'Bajar Subtítulos', 'Español', 'Idioma · Language'}
        restos = []
        for w in v.findChildren(QWidget):
            textos = [w.toolTip()]
            if isinstance(w, (QLabel, QAbstractButton)):
                textos.append(w.text())
            if isinstance(w, QLineEdit):
                textos.append(w.placeholderText())
            for t in textos:
                t = t.replace(str(Path.home()), '')
                if t and t.strip() not in permitidos and castellano.search(t):
                    restos.append(t)
        self.assertEqual(restos, [])
        self.assertEqual(v.nav_botones[AJUSTES].text().strip(), 'Settings')
        self.assertTrue(v.ajustes.botones_idioma['en'].isChecked())

    def test_por_defecto_castellano(self):
        v = self.ventana()
        self.assertTrue(v.ajustes.botones_idioma['es'].isChecked())
        self.assertEqual(v.nav_botones[2].text().strip(), 'Configuración')

    def test_busqueda_de_demostracion_en_ingles(self):
        from app.demo import lineas_demo, resultados_demo
        v = self.ventana('en')
        r = resultados_demo()
        v.inicio.empezar(Path('C:/Series'), demo=True)
        v.inicio.al_iniciar([x.video for x in r])
        for x in r:
            for linea in lineas_demo(x):
                v.inicio.al_detalle(linea)
            v.inicio.al_resultado(x)
        v.inicio.terminar(r, False, 12)
        log = v.inicio.detalles_p.log.toPlainText()
        self.assertNotRegex(log, r'pista|españa=|incrustadas')
        estados = {v.inicio.modelo.data(v.inicio.modelo.index(i, 0)) for i in range(len(r))}
        self.assertLessEqual(estados, {'Spanish from Spain', 'Spanish from Spain (embedded)', 'Already had Spanish from Spain',
                                       'Latin American', 'Latin American (embedded)', 'English (embedded)',
                                       'Latin American (already had .srt)', 'Not found', 'Pending (limit)'})
        self.assertIn('checked in', v.inicio.r_sub.text())

    def test_cambiar_el_idioma_vuelve_a_abrir_la_app(self):
        """Se guarda, se avisa al lado de la opción y la app se vuelve a abrir (en Configuración)."""
        from app.config import Config
        v = self.ventana('es')
        reinicios = []
        v.al_reiniciar = lambda: reinicios.append(True) or True
        with mock.patch('app.ventana.QTimer.singleShot', lambda ms, f: f()):
            v.ajustes.botones_idioma['es'].click()              # el que ya está: nada
            self.assertEqual(reinicios, [])
            v.ajustes.botones_idioma['en'].click()
        self.assertEqual(Config(self.ruta).idioma, 'en')
        self.assertEqual(reinicios, [True])
        self.assertIn('restarting', v.ajustes.estado_idioma.text())
        self.assertFalse(v.ajustes.botones_idioma['es'].isEnabled())

    def test_si_no_se_puede_volver_a_abrir_lo_dice(self):
        v = self.ventana('es')
        v.al_reiniciar = lambda: False
        with mock.patch('app.ventana.QTimer.singleShot', lambda ms, f: f()):
            v.ajustes.botones_idioma['en'].click()
        self.assertIn('próxima vez', v.ajustes.estado_idioma.text())

    def test_volver_a_abrir(self):
        """Lanza la app otra vez (en Configuración, con la misma configuración) y cierra esta."""
        from app import main
        args = main.argparse.Namespace(config=str(self.ruta), demo=False)
        pasos = []
        with mock.patch('subprocess.Popen', lambda orden, **k: pasos.append(('lanzar', orden))):
            self.assertTrue(main._reiniciar(args, lambda: pasos.append('salir'), lambda: pasos.append('soltar')))
        self.assertEqual(pasos[0], 'soltar')
        self.assertEqual(pasos[2], 'salir')
        orden = pasos[1][1]
        self.assertEqual(orden[-4:], ['--pagina', 'ajustes', '--config', str(self.ruta.resolve())])

        def falla(*a, **k):
            raise OSError('no')
        pasos.clear()
        with mock.patch('subprocess.Popen', falla):
            self.assertFalse(main._reiniciar(args, lambda: pasos.append('salir')))
        self.assertEqual(pasos, [])

    def test_el_instalador_solo_elige_la_primera_vez(self):
        from app import main, menu_contextual
        from app.config import Config
        llamadas = []
        with mock.patch.object(menu_contextual, 'al_instalar', lambda c: llamadas.append(tr('Bajar subtítulos'))):
            main.main(['--menu-contextual-instalar', '--idioma-inicial', 'en', '--config', str(self.ruta)])
            self.assertEqual(Config(self.ruta).idioma, 'en')
            c = Config(self.ruta)
            c.idioma = 'es'                     # cambiado después en Configuración
            c.guardar()
            main.main(['--menu-contextual-instalar', '--idioma-inicial', 'en', '--config', str(self.ruta)])
            self.assertEqual(Config(self.ruta).idioma, 'es')
        self.assertEqual(llamadas, ['Get subtitles', 'Bajar subtítulos'])   # el menú, en el idioma de la app

    def test_menu_contextual_en_ingles(self):
        from app.plataforma import menu_windows as mw
        idioma.poner('en')
        claves = mw.entradas([r'C:\app\BajarSubtitulosESP.exe'])
        self.assertEqual(claves[r'Directory\shell\BajarSubtitulosESP']['MUIVerb'], 'Get subtitles here')
        self.assertEqual(claves[r'Directory\shell\BajarSubtitulosESP\shell\1solo']['MUIVerb'], 'This folder only')
        self.assertEqual(claves[r'SystemFileAssociations\.mkv\shell\BajarSubtitulosESP']['MUIVerb'], 'Get subtitles')

    def test_aviso_junto_al_reloj(self):
        from app.bandeja import resumen
        from subtitulos import eventos as ev
        idioma.poner('en')
        r = [ev.Resultado(Path(f'{n}.mkv'), '', '', c) for n, c in enumerate((ev.CASTELLANO, ev.CASTELLANO, ev.PENDIENTE))]
        titulo, texto = resumen(r, False, [])
        self.assertEqual(titulo, 'Subtitles ready, with warnings')
        self.assertEqual(texto, '3 videos: 2 Spanish from Spain, 1 pending.\nThe pending ones are over the limit per batch: '
                                'click here and then Process pending.')
        self.assertEqual(resumen(r[:1], True, []), ('Search cancelled', '1 video checked before cancelling.'))


@unittest.skipUnless(sys.platform == 'win32' and QApplication is not None, 'el registro es de Windows')
class MenuQueCambiaDeIdioma(unittest.TestCase):
    def test_al_abrir_la_app_se_traduce_sin_tocar_el_comando(self):
        import uuid
        import winreg
        from app import menu_contextual as mc
        from app.config import Config
        from app.plataforma import menu_windows as mw
        raiz = rf'Software\BajarSubtitulosESP-pruebas-{uuid.uuid4().hex[:8]}'
        parche = mock.patch.object(mw, 'RAIZ', raiz)
        parche.start()
        self.addCleanup(parche.stop)
        self.addCleanup(lambda: mw._borrar_arbol(winreg.HKEY_CURRENT_USER, raiz))
        self.addCleanup(idioma.poner, 'es')
        with tempfile.TemporaryDirectory() as d:
            otro = Path(d) / 'portable' / 'BajarSubtitulosESP.exe'      # el menú es de otra copia
            otro.parent.mkdir()
            otro.write_bytes(b'')
            mc.registrar([str(otro)])
            config = Config(Path(d) / 'config.json')
            config.menu_contextual = True
            self.assertEqual(mc.texto_registrado(), 'Bajar subtítulos aquí')
            idioma.poner('en')
            self.assertTrue(mc.asegurar(config, instalada=True, prog=[str(Path(d) / 'BajarSubtitulosESP.exe')]))
            self.assertEqual(mc.texto_registrado(), 'Get subtitles here')
            self.assertEqual(mc.programa_registrado(), otro)
            self.assertFalse(mc.asegurar(config, instalada=True, prog=[str(otro)]))   # ya está: nada


if __name__ == '__main__':
    unittest.main()
