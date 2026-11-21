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


class Interpretar(unittest.TestCase):
    def test_version_nueva(self):
        n, sumas = act.interpretar(release(), actual='1.0.1')
        self.assertEqual(n.version, '1.0.2')
        self.assertEqual(n.pagina, f'{REPO}/releases/tag/v1.0.2')
        self.assertEqual(n.instalador.nombre, 'BajarSubtitulosESP-1.0.2-instalador.exe')
        self.assertEqual(n.instalador.sha256, SHA)
        self.assertEqual(n.instalador.tamano, 1234)
        self.assertEqual(n.notas, '• Actualizaciones automáticas\n• Más rápido')
        self.assertTrue(sumas.endswith('/SHA256SUMS.txt'))

    def test_misma_o_anterior_no_es_novedad(self):
        for actual in ('1.0.2', '1.0.3', '2.0.0'):
            self.assertEqual(act.interpretar(release(), actual=actual), (None, None))

    def test_borradores_y_versiones_previas_no_cuentan(self):
        self.assertEqual(act.interpretar(release(prerelease=True), actual='1.0.0'), (None, None))
        self.assertEqual(act.interpretar(release(draft=True), actual='1.0.0'), (None, None))

    def test_etiqueta_no_valida(self):
        with self.assertRaises(act.ErrorActualizacion):
            act.interpretar(release(tag_name='ultima'), actual='1.0.0')
        with self.assertRaises(act.ErrorActualizacion):
            act.interpretar(['no', 'es', 'un', 'diccionario'], actual='1.0.0')

    def test_solo_descargas_de_este_repositorio_y_con_el_nombre_exacto(self):
        d = release()
        d['assets'][0]['browser_download_url'] = 'https://ejemplo.com/BajarSubtitulosESP-1.0.2-instalador.exe'
        self.assertIsNone(act.interpretar(d, actual='1.0.0')[0].instalador)
        d = release()
        d['assets'][0]['name'] = 'BajarSubtitulosESP-1.0.3-instalador.exe'    # otra versión que la etiqueta
        self.assertIsNone(act.interpretar(d, actual='1.0.0')[0].instalador)
        d = release(html_url='https://ejemplo.com/engaño')
        self.assertEqual(act.interpretar(d, actual='1.0.0')[0].pagina, f'{REPO}/releases/latest')

    def test_huella_no_valida_queda_vacia(self):
        for digest in (None, 'md5:abc', 'sha256:xyz', f'sha256:{SHA}00', 7):
            n, _ = act.interpretar(release(digest=digest), actual='1.0.0')
            self.assertEqual(n.instalador.sha256, '', digest)

    def test_notas_como_texto_plano_y_limitadas(self):
        n, _ = act.interpretar(release(body='Hola\x1b[31m\u202e [enlace](https://x.y) <b>sin html</b>'),
                               actual='1.0.0')
        self.assertEqual(n.notas, 'Hola[31m enlace <b>sin html</b>')       # la ventana lo pinta como texto
        n, _ = act.interpretar(release(body='línea\n' * 2000), actual='1.0.0')
        self.assertLessEqual(len(n.notas), act.MAX_NOTAS + 2)
        self.assertTrue(n.notas.endswith('…'))

    def test_leer_sumas(self):
        texto = f'{SHA}  BajarSubtitulosESP-1.0.2-instalador.exe\n{"cd" * 32} *otro.zip\nbasura\n'
        self.assertEqual(act.leer_sumas(texto, 'BajarSubtitulosESP-1.0.2-instalador.exe'), SHA)
        self.assertEqual(act.leer_sumas(texto, 'otro.zip'), 'cd' * 32)
        self.assertEqual(act.leer_sumas(texto, 'no-esta.exe'), '')


class Consultar(unittest.TestCase):
    def test_usa_sha256sums_si_falta_la_huella(self):
        respuestas = {act.URL_API: json.dumps(release(digest=None)).encode(),
                      f'{REPO}/releases/download/v1.0.2/SHA256SUMS.txt':
                          f'{SHA}  BajarSubtitulosESP-1.0.2-instalador.exe\n'.encode()}
        with mock.patch.object(act, '_leer', side_effect=lambda url, *a, **k: respuestas[url]):
            n = act.consultar('1.0.0')
        self.assertEqual(n.instalador.sha256, SHA)

    def test_sin_huella_no_hay_instalacion_automatica(self):
        d = release(digest=None)
        d['assets'] = d['assets'][:1]                       # ni digest ni SHA256SUMS.txt
        with mock.patch.object(act, '_leer', return_value=json.dumps(d).encode()):
            n = act.consultar('1.0.0')
        self.assertEqual(n.version, '1.0.2')
        self.assertIsNone(n.instalador)                     # solo se ofrece abrir la página

    def test_al_dia(self):
        with mock.patch.object(act, '_leer', return_value=json.dumps(release()).encode()):
            self.assertIsNone(act.consultar('1.0.2'))

    def test_errores_con_mensaje_legible(self):
        error_404 = urllib.error.HTTPError(act.URL_API, 404, 'Not Found', {}, None)
        with mock.patch.object(act, '_leer', side_effect=error_404):
            self.assertIsNone(act.consultar('1.0.0'))       # aún no hay ninguna Release
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
