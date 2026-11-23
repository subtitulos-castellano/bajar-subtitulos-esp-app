"""Pruebas del actualizador (app/actualizar.py), sin Qt y sin conectarse a GitHub.

La descarga se prueba de verdad contra un servidor HTTP local.
"""
import hashlib
import http.server
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import actualizar as act  # noqa: E402

REPO = 'https://github.com/subtitulos-castellano/bajar-subtitulos-esp-app'
SHA = 'ab' * 32


def release(tag='v1.0.2', digest=f'sha256:{SHA}', **extra):
    v = tag.lstrip('v')
    datos = {
        'tag_name': tag, 'draft': False, 'prerelease': False,
        'html_url': f'{REPO}/releases/tag/{tag}',
        'body': '- **Actualizaciones** automáticas\n- Más `rápido`',
        'assets': [
            {'name': f'BajarSubtitulosESP-{v}-instalador.exe', 'size': 1234, 'digest': digest,
             'browser_download_url': f'{REPO}/releases/download/{tag}/BajarSubtitulosESP-{v}-instalador.exe'},
            {'name': f'BajarSubtitulosESP-{v}-portable.zip', 'size': 99, 'digest': f'sha256:{"cd" * 32}',
             'browser_download_url': f'{REPO}/releases/download/{tag}/BajarSubtitulosESP-{v}-portable.zip'},
            {'name': 'SHA256SUMS.txt', 'size': 10, 'digest': None,
             'browser_download_url': f'{REPO}/releases/download/{tag}/SHA256SUMS.txt'},
        ],
    }
    datos.update(extra)
    return datos


class Versiones(unittest.TestCase):
    def test_numeros(self):
        self.assertEqual(act.version('1.0.2'), (1, 0, 2))
        self.assertEqual(act.version('v10.20.30'), (10, 20, 30))
        for malo in ('1.0', 'v1.0.0-beta', '1.0.0.0', '', None, 1, 'latest', '١.٠.٠'):
            self.assertIsNone(act.version(malo), malo)
        self.assertLess(act.version('1.0.9'), act.version('1.0.10'))     # números, no texto

    def test_version_de_la_app_valida(self):
        self.assertIsNotNone(act.version(act.__version__))

    def test_version_corta(self):
        self.assertEqual(act.version_corta('1.0.0'), '1.0')
        self.assertEqual(act.version_corta('1.0.2'), '1.0.2')


def interpretar(*releases, actual='1.0.0', sistema='windows'):
    """Como la respuesta de /releases: una lista (las pruebas de Windows salvo que se diga otra cosa)."""
    return act.interpretar(list(releases), actual=actual, sistema=sistema)


class Interpretar(unittest.TestCase):
    def test_version_nueva(self):
        n, sumas = interpretar(release(), actual='1.0.1')
        self.assertEqual(n.version, '1.0.2')
        self.assertEqual(n.pagina, f'{REPO}/releases/tag/v1.0.2')
        self.assertEqual(n.instalador.nombre, 'BajarSubtitulosESP-1.0.2-instalador.exe')
        self.assertEqual(n.instalador.sha256, SHA)
        self.assertEqual(n.instalador.tamano, 1234)
        self.assertEqual(n.notas, '• Actualizaciones automáticas\n• Más rápido')
        self.assertTrue(sumas.endswith('/SHA256SUMS.txt'))

    def test_misma_o_anterior_no_es_novedad(self):
        for actual in ('1.0.2', '1.0.3', '2.0.0'):
            self.assertEqual(interpretar(release(), actual=actual), (None, None))

    def test_borradores_y_versiones_previas_no_cuentan(self):
        self.assertEqual(interpretar(release(prerelease=True)), (None, None))
        self.assertEqual(interpretar(release(draft=True)), (None, None))
        self.assertEqual(interpretar(release(draft=True, tag='v1.0.3'), release())[0].version, '1.0.2')

    def test_etiqueta_no_valida_no_cuenta(self):
        self.assertEqual(interpretar(release(tag_name='ultima')), (None, None))
        self.assertEqual(interpretar(release(tag_name='v9.0.0-beta'), release())[0].version, '1.0.2')
        self.assertEqual(interpretar('no es un diccionario', 7, None, release())[0].version, '1.0.2')

    def test_respuesta_que_no_es_una_lista(self):
        for malo in (release(), 'texto', None, 3):
            with self.assertRaises(act.ErrorActualizacion):
                act.interpretar(malo, actual='1.0.0')

    def test_la_mas_nueva_aunque_github_las_ordene_de_otra_forma(self):
        n, sumas = interpretar(release('v1.0.2'), release('v1.0.10'), release('v1.0.9'))
        self.assertEqual(n.version, '1.0.10')
        self.assertEqual(n.instalador.nombre, 'BajarSubtitulosESP-1.0.10-instalador.exe')
        self.assertIn('/v1.0.10/', sumas)

    def test_solo_descargas_de_este_repositorio_y_con_el_nombre_exacto(self):
        d = release()
        d['assets'][0]['browser_download_url'] = 'https://ejemplo.com/BajarSubtitulosESP-1.0.2-instalador.exe'
        self.assertIsNone(interpretar(d)[0].instalador)
        d = release()
        d['assets'][0]['name'] = 'BajarSubtitulosESP-1.0.3-instalador.exe'    # otra versión que la etiqueta
        self.assertIsNone(interpretar(d)[0].instalador)
        d = release(html_url='https://ejemplo.com/engaño')
        self.assertEqual(interpretar(d)[0].pagina, f'{REPO}/releases/latest')

    def test_huella_no_valida_queda_vacia(self):
        for digest in (None, 'md5:abc', 'sha256:xyz', f'sha256:{SHA}00', 7):
            n, _ = interpretar(release(digest=digest))
            self.assertEqual(n.instalador.sha256, '', digest)

    def test_notas_como_texto_plano_y_limitadas(self):
        n, _ = interpretar(release(body='Hola\x1b[31m\u202e [enlace](https://x.y) <b>sin html</b>'))
        self.assertEqual(n.notas, 'Hola[31m enlace <b>sin html</b>')       # la ventana lo pinta como texto
        n, _ = interpretar(release(body='línea\n' * 2000))
        self.assertLessEqual(len(n.notas), act.MAX_NOTAS + 2)
        self.assertTrue(n.notas.endswith('…'))

    def test_en_linux_aun_no_se_instala_sola(self):
        n, _ = interpretar(release(), sistema='linux')
        self.assertEqual(n.version, '1.0.2')
        self.assertIsNone(n.instalador)                     # solo se ofrece abrir la página

    def test_leer_sumas(self):
        texto = f'{SHA}  BajarSubtitulosESP-1.0.2-instalador.exe\n{"cd" * 32} *otro.zip\nbasura\n'
        self.assertEqual(act.leer_sumas(texto, 'BajarSubtitulosESP-1.0.2-instalador.exe'), SHA)
        self.assertEqual(act.leer_sumas(texto, 'otro.zip'), 'cd' * 32)
        self.assertEqual(act.leer_sumas(texto, 'no-esta.exe'), '')


class NovedadesPorSistema(unittest.TestCase):
    """«- [Windows] …» y «- [Linux] …» en el CHANGELOG: solo para ese sistema; sin marca, para los dos."""
    NOTAS = ('- Opción nueva para todos.\n'
             '- [Windows] Arreglado el menú del Explorador.\n'
             '  - Con sus detalles.\n'
             '- [Linux] El icono junto al reloj.\n'
             '  - También con detalles.\n'
             '\n'
             'Un párrafo final.')

    def test_filtrar(self):
        texto, propia = act.notas_del_sistema(self.NOTAS, 'linux')
        self.assertTrue(propia)
        self.assertEqual(texto, '- Opción nueva para todos.\n- El icono junto al reloj.\n'
                                '  - También con detalles.\n\nUn párrafo final.')
        texto, _ = act.notas_del_sistema(self.NOTAS, 'windows')
        self.assertEqual(texto, '- Opción nueva para todos.\n- Arreglado el menú del Explorador.\n'
                                '  - Con sus detalles.\nUn párrafo final.')

    def test_solo_de_otro_sistema(self):
        self.assertFalse(act.notas_del_sistema('- [Windows] Algo.\n- [windows] Otra cosa.', 'linux')[1])
        self.assertTrue(act.notas_del_sistema('- [Linux] Algo.', 'linux')[1])
        self.assertTrue(act.notas_del_sistema('Sin lista de novedades.', 'linux')[1])     # cuenta para todos
        self.assertTrue(act.notas_del_sistema('', 'linux')[1])

    def test_sin_cambios_para_este_sistema_no_avisa(self):
        solo_windows = release('v1.0.2', body='- [Windows] Arreglo.')
        self.assertIsNone(interpretar(solo_windows, sistema='linux')[0])
        self.assertEqual(interpretar(solo_windows, sistema='windows')[0].notas, '• Arreglo.')

    def test_junta_las_versiones_que_se_salta_y_actualiza_a_la_ultima(self):
        """En la 1.0.0: la 1.0.3 solo cambia Windows, pero la 1.0.2 traía algo de Linux."""
        lista = [release('v1.0.3', body='- [Windows] Solo Windows.'),
                 release('v1.0.2', body='- [Linux] Para Linux.\n- Para todos.'),
                 release('v1.0.1', body='- [Windows] Otro de Windows.'),
                 release('v1.0.0', body='- Ya instalada.')]
        n, _ = act.interpretar(lista, actual='1.0.0', sistema='linux')
        self.assertEqual(n.version, '1.0.3')
        self.assertEqual(n.pagina, f'{REPO}/releases/tag/v1.0.3')
        self.assertEqual(n.notas, '• Para Linux.\n• Para todos.')
        n, _ = act.interpretar(lista, actual='1.0.0', sistema='windows')
        self.assertEqual(n.version, '1.0.3')
        self.assertEqual(n.instalador.nombre, 'BajarSubtitulosESP-1.0.3-instalador.exe')
        self.assertEqual(n.notas, 'Versión 1.0.3\n• Solo Windows.\n\nVersión 1.0.2\n• Para todos.\n\n'
                                  'Versión 1.0.1\n• Otro de Windows.')

    def test_en_ingles(self):
        from subtitulos import idioma
        self.addCleanup(idioma.poner, 'es')
        idioma.poner('en')
        cuerpo = '- [Linux] Para Linux.\n\n<!-- en -->\n\n### English\n\n- [Linux] For Linux.\n- For both.'
        lista = [release('v1.0.2', body=cuerpo), release('v1.0.1', body='- For both, again.')]
        n, _ = act.interpretar(lista, actual='1.0.0', sistema='linux')
        self.assertEqual(n.notas, 'Version 1.0.2\n• For Linux.\n• For both.\n\nVersion 1.0.1\n• For both, again.')
        n, _ = act.interpretar([release('v1.0.2', body=cuerpo)], actual='1.0.0', sistema='windows')
        self.assertEqual(n.notas, '• For both.')


def lista(*releases):
    return json.dumps(list(releases)).encode()


class Consultar(unittest.TestCase):
    def test_usa_sha256sums_si_falta_la_huella(self):
        respuestas = {act.URL_API: lista(release(digest=None)),
                      f'{REPO}/releases/download/v1.0.2/SHA256SUMS.txt':
                          f'{SHA}  BajarSubtitulosESP-1.0.2-instalador.exe\n'.encode()}
        with mock.patch.object(act, '_leer', side_effect=lambda url, *a, **k: respuestas[url]):
            n = act.consultar('1.0.0', 'windows')
        self.assertEqual(n.instalador.sha256, SHA)

    def test_sin_huella_no_hay_instalacion_automatica(self):
        d = release(digest=None)
        d['assets'] = d['assets'][:1]                       # ni digest ni SHA256SUMS.txt
        with mock.patch.object(act, '_leer', return_value=lista(d)):
            n = act.consultar('1.0.0', 'windows')
        self.assertEqual(n.version, '1.0.2')
        self.assertIsNone(n.instalador)                     # solo se ofrece abrir la página

    def test_al_dia(self):
        with mock.patch.object(act, '_leer', return_value=lista(release())):
            self.assertIsNone(act.consultar('1.0.2'))
        with mock.patch.object(act, '_leer', return_value=lista()):
            self.assertIsNone(act.consultar('1.0.2'))       # aún no hay ninguna Release

    def test_errores_con_mensaje_legible(self):
        error_404 = urllib.error.HTTPError(act.URL_API, 404, 'Not Found', {}, None)
        with mock.patch.object(act, '_leer', side_effect=error_404):
            self.assertIsNone(act.consultar('1.0.0'))       # el repositorio aún no tiene Releases
        error_403 = urllib.error.HTTPError(act.URL_API, 403, 'rate limit', {}, None)
        for fallo in (error_403, urllib.error.URLError('sin red'), TimeoutError(), ValueError('json')):
            with mock.patch.object(act, '_leer', side_effect=fallo):
                with self.assertRaises(act.ErrorActualizacion):
                    act.consultar('1.0.0')
        with mock.patch.object(act, '_leer', return_value=b'{no es json'):
            with self.assertRaises(act.ErrorActualizacion):
                act.consultar('1.0.0')


class _Servidor(http.server.BaseHTTPRequestHandler):
    contenido = b''

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Length', str(len(self.contenido)))
        self.end_headers()
        self.wfile.write(self.contenido)

    def log_message(self, *args):
        pass


class Descargar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _Servidor.contenido = b'instalador de prueba ' * 50000           # ~1 MB
        cls.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), _Servidor)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.httpd.server_address[1]}/BajarSubtitulosESP-1.0.2-instalador.exe'
        cls.sha = hashlib.sha256(_Servidor.contenido).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.carpeta = Path(self._d.name)
        self.addCleanup(self._d.cleanup)

    def archivo(self, sha=None, tamano=0, nombre='BajarSubtitulosESP-1.0.2-instalador.exe'):
        return act.Archivo(nombre, self.url, self.sha if sha is None else sha, tamano)

    def test_descarga_y_comprueba_la_huella(self):
        avances = []
        ruta = act.descargar(self.archivo(), self.carpeta, progreso=lambda h, t: avances.append((h, t)))
        self.assertEqual(ruta, self.carpeta / 'BajarSubtitulosESP-1.0.2-instalador.exe')
        self.assertEqual(ruta.read_bytes(), _Servidor.contenido)
        self.assertEqual(avances[-1], (len(_Servidor.contenido), len(_Servidor.contenido)))
        self.assertEqual([f.name for f in self.carpeta.iterdir()], [ruta.name])

    def test_huella_distinta_no_deja_nada(self):
        with self.assertRaisesRegex(act.ErrorActualizacion, 'no coincide con la huella'):
            act.descargar(self.archivo(sha='0' * 64), self.carpeta)
        self.assertEqual(list(self.carpeta.iterdir()), [])

    def test_sin_huella_o_nombre_raro_no_descarga(self):
        for archivo in (self.archivo(sha=''), self.archivo(nombre='..\\..\\otro.exe'),
                        self.archivo(nombre='BajarSubtitulosESP-1.0.2-instalador.bat')):
            with self.assertRaises(act.ErrorActualizacion):
                act.descargar(archivo, self.carpeta)
        self.assertEqual(list(self.carpeta.iterdir()), [])

    def test_demasiado_grande(self):
        with self.assertRaisesRegex(act.ErrorActualizacion, 'demasiado grande'):
            act.descargar(self.archivo(tamano=act.TAMANO_MAX + 1), self.carpeta)
        with mock.patch.object(act, 'TAMANO_MAX', 1000):
            with self.assertRaisesRegex(act.ErrorActualizacion, 'demasiado grande'):
                act.descargar(self.archivo(), self.carpeta)        # el servidor manda más de lo dicho
        self.assertEqual(list(self.carpeta.iterdir()), [])

    def test_cancelar(self):
        with self.assertRaises(act.Cancelada):
            act.descargar(self.archivo(), self.carpeta, cancelada=lambda: True)
        self.assertEqual(list(self.carpeta.iterdir()), [])

    def test_sin_conexion(self):
        a = act.Archivo('BajarSubtitulosESP-1.0.2-instalador.exe', 'http://127.0.0.1:9/x', self.sha, 0)
        with self.assertRaisesRegex(act.ErrorActualizacion, 'interrumpido'):
            act.descargar(a, self.carpeta)
        self.assertEqual(list(self.carpeta.iterdir()), [])

    def test_limpiar_descargas(self):
        for nombre in ('BajarSubtitulosESP-1.0.1-instalador.exe', 'x.exe.part', 'instalacion.log'):
            (self.carpeta / nombre).write_text('x')
        act.limpiar_descargas(self.carpeta)
        self.assertEqual([f.name for f in self.carpeta.iterdir()], ['instalacion.log'])
        act.limpiar_descargas(self.carpeta / 'no-existe')               # sin errores


class Instalar(unittest.TestCase):
    def test_nombre_del_instalador(self):
        self.assertEqual(act.nombre_instalador('1.4.0', 'windows'), 'BajarSubtitulosESP-1.4.0-instalador.exe')
        self.assertIsNone(act.nombre_instalador('1.4.0', 'linux'))

    def test_argumentos(self):
        args = act.argumentos_instalador(Path('C:/t/inst.exe'), 'usuario', Path('C:/t/instalacion.log'))
        for a in ('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CURRENTUSER', '/REABRIR=1'):
            self.assertIn(a, args)
        self.assertNotIn('/ALLUSERS', args)
        self.assertTrue(any(a.startswith('/LOG=') for a in args))
        self.assertIn('/ALLUSERS', act.argumentos_instalador(Path('i.exe'), 'todos', Path('l')))

    def test_lanzar(self):
        with mock.patch.object(act.subprocess, 'Popen') as popen:
            act.lanzar_instalador(Path('/tmp/BajarSubtitulosESP-1.0.2-instalador.exe'), 'usuario')
        args = popen.call_args.args[0]
        self.assertEqual(args[0], str(Path('/tmp/BajarSubtitulosESP-1.0.2-instalador.exe')))
        self.assertIn('/REABRIR=1', args)

    def test_instalada_o_portable(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / 'BajarSubtitulosESP.exe'
            exe.write_text('x')
            self.assertFalse(act.instalada(exe))
            (Path(d) / 'unins000.exe').write_text('x')
            self.assertTrue(act.instalada(exe))
        self.assertFalse(act.instalada())          # desde el código fuente: nunca se instala sola


if __name__ == '__main__':
    unittest.main(verbosity=2)
