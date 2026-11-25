"""Pruebas del actualizador (app/actualizar.py), sin Qt y sin conectarse a GitHub.

La descarga se prueba de verdad contra un servidor HTTP local.
"""
import hashlib
import http.server
import json
import re
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
            {'name': f'BajarSubtitulosESP-{v}-windows-instalador.exe', 'size': 1234, 'digest': digest,
             'browser_download_url': f'{REPO}/releases/download/{tag}/BajarSubtitulosESP-{v}-windows-instalador.exe'},
            {'name': f'BajarSubtitulosESP-{v}-windows-portable.zip', 'size': 99, 'digest': f'sha256:{"cd" * 32}',
             'browser_download_url': f'{REPO}/releases/download/{tag}/BajarSubtitulosESP-{v}-windows-portable.zip'},
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
        self.assertEqual(n.instalador.nombre, 'BajarSubtitulosESP-1.0.2-windows-instalador.exe')
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
        self.assertEqual(n.instalador.nombre, 'BajarSubtitulosESP-1.0.10-windows-instalador.exe')
        self.assertIn('/v1.0.10/', sumas)

    def test_solo_descargas_de_este_repositorio_y_con_el_nombre_exacto(self):
        d = release()
        d['assets'][0]['browser_download_url'] = 'https://ejemplo.com/BajarSubtitulosESP-1.0.2-windows-instalador.exe'
        self.assertIsNone(interpretar(d)[0].instalador)
        d = release()
        d['assets'][0]['name'] = 'BajarSubtitulosESP-1.0.3-windows-instalador.exe'    # otra versión que la etiqueta
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

    def test_en_linux_segun_como_se_instalo(self):
        d = release()
        for sufijo in ('linux-amd64.deb', 'linux-x86_64.rpm', 'linux-x86_64.AppImage', 'linux-x86_64.tar.gz'):
            d['assets'].append({'name': f'BajarSubtitulosESP-1.0.2-{sufijo}', 'size': 5, 'digest': f'sha256:{SHA}',
                                'browser_download_url': f'{REPO}/releases/download/v1.0.2/BajarSubtitulosESP-1.0.2-{sufijo}'})
        for tipo, nombre in (('deb', 'BajarSubtitulosESP-1.0.2-linux-amd64.deb'),
                             ('rpm', 'BajarSubtitulosESP-1.0.2-linux-x86_64.rpm'),
                             ('appimage', 'BajarSubtitulosESP-1.0.2-linux-x86_64.AppImage')):
            n, _ = act.interpretar([d], actual='1.0.0', sistema='linux', tipo=tipo)
            self.assertEqual(n.instalador.nombre, nombre)
        with mock.patch.object(act, 'tipo_linux', return_value=None):      # .tar.gz o desde el código
            n, _ = interpretar(d, sistema='linux')
        self.assertEqual(n.version, '1.0.2')
        self.assertIsNone(n.instalador)                     # solo se ofrece abrir la página

    def test_los_nombres_de_antes_de_la_2_ya_no_valen(self):
        """Desde la 2.0.0 los archivos llevan el sistema delante (…-windows-instalador.exe, …-linux-amd64.deb):
        los de antes (…-instalador.exe, …-amd64.deb) ya no se reconocen, ni uno de otro sistema."""
        tag, v = 'v2.0.1', '2.0.1'

        def con(*nombres):
            return release(tag=tag, assets=[{'name': n, 'size': 5, 'digest': f'sha256:{SHA}',
                                             'browser_download_url': f'{REPO}/releases/download/{tag}/{n}'}
                                            for n in nombres])
        viejos = con(*(f'BajarSubtitulosESP-{v}-{s}' for s in ('instalador.exe', 'amd64.deb', 'x86_64.rpm',
                                                                 'x86_64.AppImage')))
        self.assertIsNone(act.interpretar([viejos], actual='2.0.0', sistema='windows')[0].instalador)
        for tipo in ('deb', 'rpm', 'appimage'):
            self.assertIsNone(act.interpretar([viejos], actual='2.0.0', sistema='linux', tipo=tipo)[0].instalador)
        otro = con(f'BajarSubtitulosESP-{v}-linux-instalador.exe')
        self.assertIsNone(act.interpretar([otro], actual='2.0.0', sistema='windows')[0].instalador)

    def test_leer_sumas(self):
        texto = f'{SHA}  BajarSubtitulosESP-1.0.2-windows-instalador.exe\n{"cd" * 32} *otro.zip\nbasura\n'
        self.assertEqual(act.leer_sumas(texto, 'BajarSubtitulosESP-1.0.2-windows-instalador.exe'), SHA)
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
        self.assertEqual(n.instalador.nombre, 'BajarSubtitulosESP-1.0.3-windows-instalador.exe')
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
                          f'{SHA}  BajarSubtitulosESP-1.0.2-windows-instalador.exe\n'.encode()}
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
        cls.url = f'http://127.0.0.1:{cls.httpd.server_address[1]}/BajarSubtitulosESP-1.0.2-windows-instalador.exe'
        cls.sha = hashlib.sha256(_Servidor.contenido).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.carpeta = Path(self._d.name)
        self.addCleanup(self._d.cleanup)

    def archivo(self, sha=None, tamano=0, nombre='BajarSubtitulosESP-1.0.2-windows-instalador.exe'):
        return act.Archivo(nombre, self.url, self.sha if sha is None else sha, tamano)

    def test_descarga_y_comprueba_la_huella(self):
        avances = []
        ruta = act.descargar(self.archivo(), self.carpeta, progreso=lambda h, t: avances.append((h, t)))
        self.assertEqual(ruta, self.carpeta / 'BajarSubtitulosESP-1.0.2-windows-instalador.exe')
        self.assertEqual(ruta.read_bytes(), _Servidor.contenido)
        self.assertEqual(avances[-1], (len(_Servidor.contenido), len(_Servidor.contenido)))
        self.assertEqual([f.name for f in self.carpeta.iterdir()], [ruta.name])

    def test_huella_distinta_no_deja_nada(self):
        with self.assertRaisesRegex(act.ErrorActualizacion, 'no coincide con la huella'):
            act.descargar(self.archivo(sha='0' * 64), self.carpeta)
        self.assertEqual(list(self.carpeta.iterdir()), [])

    def test_sin_huella_o_nombre_raro_no_descarga(self):
        for archivo in (self.archivo(sha=''), self.archivo(nombre='..\\..\\otro.exe'),
                        self.archivo(nombre='BajarSubtitulosESP-1.0.2-windows-instalador.bat')):
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
        a = act.Archivo('BajarSubtitulosESP-1.0.2-windows-instalador.exe', 'http://127.0.0.1:9/x', self.sha, 0)
        with self.assertRaisesRegex(act.ErrorActualizacion, 'interrumpido'):
            act.descargar(a, self.carpeta)
        self.assertEqual(list(self.carpeta.iterdir()), [])

    def test_ya_descargada_y_comprobada_no_se_repite(self):
        ruta = act.descargar(self.archivo(), self.carpeta)
        with mock.patch.object(act, '_abrir', side_effect=AssertionError('no debería descargar')):
            self.assertEqual(act.descargar(self.archivo(), self.carpeta), ruta)
        ruta.write_bytes(b'cambiado')                                      # ya no coincide: se descarga
        self.assertEqual(act.descargar(self.archivo(), self.carpeta).read_bytes(), _Servidor.contenido)

    def test_nombres_de_linux(self):
        for sufijo in ('linux-amd64.deb', 'linux-x86_64.rpm', 'linux-x86_64.AppImage', 'windows-instalador.exe'):
            self.assertTrue(act.descargar(self.archivo(nombre=f'BajarSubtitulosESP-1.0.2-{sufijo}'), self.carpeta)
                            .is_file())
        for malo in ('BajarSubtitulosESP-1.0.2-linux-amd64.deb.sh', 'BajarSubtitulosESP-1.0.2-linux-x86_64.AppImage/../x',
                     'otro-1.0.2-linux-amd64.deb', 'BajarSubtitulosESP-1.0.2-mac-amd64.deb',
                     'BajarSubtitulosESP-1.0.2-amd64.deb', 'BajarSubtitulosESP-1.0.2-instalador.exe'):
            with self.assertRaises(act.ErrorActualizacion):
                act.descargar(self.archivo(nombre=malo), self.carpeta)

    def test_limpiar_descargas(self):
        for nombre in ('BajarSubtitulosESP-1.0.1-windows-instalador.exe', 'x.exe.part', 'instalacion.log'):
            (self.carpeta / nombre).write_text('x')
        act.limpiar_descargas(self.carpeta)
        self.assertEqual([f.name for f in self.carpeta.iterdir()], ['instalacion.log'])
        act.limpiar_descargas(self.carpeta / 'no-existe')               # sin errores


class Instalar(unittest.TestCase):
    def test_nombre_del_instalador(self):
        self.assertEqual(act.nombre_instalador('1.4.0', 'windows'), 'BajarSubtitulosESP-1.4.0-windows-instalador.exe')
        self.assertEqual(act.nombre_instalador('1.4.0', 'linux', 'deb'), 'BajarSubtitulosESP-1.4.0-linux-amd64.deb')
        self.assertEqual(act.nombre_instalador('1.4.0', 'linux', 'rpm'), 'BajarSubtitulosESP-1.4.0-linux-x86_64.rpm')
        self.assertEqual(act.nombre_instalador('1.4.0', 'linux', 'appimage'),
                         'BajarSubtitulosESP-1.4.0-linux-x86_64.AppImage')
        with mock.patch.object(act, 'tipo_linux', return_value=None):
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
            act.lanzar_instalador(Path('/tmp/BajarSubtitulosESP-1.0.2-windows-instalador.exe'), 'usuario')
        args = popen.call_args.args[0]
        self.assertEqual(args[0], str(Path('/tmp/BajarSubtitulosESP-1.0.2-windows-instalador.exe')))
        self.assertIn('/REABRIR=1', args)

    def test_instalada_o_portable(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / 'BajarSubtitulosESP.exe'
            exe.write_text('x')
            self.assertFalse(act.instalada(exe))
            (Path(d) / 'unins000.exe').write_text('x')
            self.assertTrue(act.instalada(exe))
        self.assertFalse(act.instalada())          # desde el código fuente: nunca se instala sola



@unittest.skipUnless(sys.platform.startswith('linux'), 'solo en Linux')
class InstalarEnLinux(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.addCleanup(self._d.cleanup)
        self.d = Path(self._d.name)

    def which(self, *programas):
        return mock.patch.object(act.shutil, 'which', lambda p: f'/usr/bin/{p}' if p in programas else None)

    def test_orden_del_gestor_de_paquetes(self):
        deb, rpm = Path('/c/a.deb'), Path('/c/a.rpm')
        with mock.patch.object(act.os, 'geteuid', return_value=1000):
            with self.which('apt-get', 'pkexec'):
                self.assertEqual(act._orden_gestor(deb, 'deb'),
                                 ['/usr/bin/pkexec', '/usr/bin/apt-get', 'install', '-y', '/c/a.deb'])
            with self.which('dnf', 'zypper', 'pkexec'):                   # dnf antes que zypper
                self.assertEqual(act._orden_gestor(rpm, 'rpm')[1:], ['/usr/bin/dnf', 'install', '-y', '/c/a.rpm'])
            with self.which('zypper', 'pkexec'):
                self.assertIn('--allow-unsigned-rpm', act._orden_gestor(rpm, 'rpm'))
            with self.which('apt-get'):                                   # sin pkexec no se puede
                self.assertIsNone(act._orden_gestor(deb, 'deb'))
            with self.which('pkexec'):
                self.assertIsNone(act._orden_gestor(rpm, 'rpm'))
        with mock.patch.object(act.os, 'geteuid', return_value=0), self.which('apt-get'):
            self.assertEqual(act._orden_gestor(deb, 'deb')[0], '/usr/bin/apt-get')    # ya es administrador

    def resultado(self, codigo, stderr=''):
        return mock.Mock(returncode=codigo, stdout='', stderr=stderr)

    def test_paquete(self):
        paquete = self.d / 'BajarSubtitulosESP-1.5.0-linux-x86_64.rpm'
        with mock.patch.object(act.os, 'geteuid', return_value=1000), self.which('dnf', 'pkexec'):
            with mock.patch.object(act.subprocess, 'run', return_value=self.resultado(0)) as run, \
                    mock.patch('app.menu_contextual.programa', return_value=['/opt/bajar-subtitulos-esp/x']):
                self.assertEqual(act.instalar_linux(paquete, '1.5.0', 'rpm'), ['/opt/bajar-subtitulos-esp/x'])
            self.assertEqual(run.call_args.args[0][:3], ['/usr/bin/pkexec', '/usr/bin/dnf', 'install'])
            for codigo in act.PKEXEC_CANCELADO:                             # cerrada la ventana de la contraseña
                with mock.patch.object(act.subprocess, 'run', return_value=self.resultado(codigo)), \
                        self.assertRaises(act.Cancelada):
                    act.instalar_linux(paquete, '1.5.0', 'rpm')
            with mock.patch.object(act.subprocess, 'run',
                                   return_value=self.resultado(1, 'Error: transacción\nNo hay sitio en disco\n')), \
                    self.assertRaisesRegex(act.ErrorActualizacion, r'código 1\): No hay sitio en disco'):
                act.instalar_linux(paquete, '1.5.0', 'rpm')

    def test_appimage(self):
        """Se escribe al lado, se renombra encima y, si el nombre llevaba la versión, se borra el viejo."""
        from app.plataforma import linux
        viejo = self.d / f'BajarSubtitulosESP-{act.__version__}-linux-x86_64.AppImage'
        viejo.write_text('viejo')
        nuevo = self.d / 'BajarSubtitulosESP-99.0.0-linux-x86_64.AppImage'
        nuevo.write_text('nuevo')
        with mock.patch.object(linux, 'appimage', return_value=viejo):
            self.assertEqual(act.instalar_linux(nuevo, '99.0.0', 'appimage'), [str(nuevo)])
        self.assertFalse(viejo.exists())
        self.assertEqual(nuevo.read_text(), 'nuevo')
        self.assertTrue(nuevo.stat().st_mode & 0o100)
        # Con otro nombre (sin la versión), se queda con ese nombre.
        propio = self.d / 'Subtitulos.AppImage'
        propio.write_text('viejo')
        otro = self.d / 'BajarSubtitulosESP-99.0.1-linux-x86_64.AppImage'
        otro.write_text('nuevo')
        with mock.patch.object(linux, 'appimage', return_value=propio):
            self.assertEqual(act.instalar_linux(otro, '99.0.1', 'appimage'), [str(propio)])
        self.assertEqual(propio.read_text(), 'nuevo')
        self.assertFalse(otro.exists())

    def test_motivos_para_solo_avisar(self):
        from app.plataforma import linux
        with mock.patch.object(act, 'tipo_linux', return_value=None):
            self.assertIn('no se actualiza sola', act.motivo_sin_instalar())
            self.assertFalse(act.puede_instalarse())
        with mock.patch.object(act, 'tipo_linux', return_value='appimage'), \
                mock.patch.object(linux, 'appimage', return_value=self.d / 'B.AppImage'):
            self.assertEqual(act.motivo_sin_instalar(), '')
            self.assertTrue(act.puede_instalarse())
            with mock.patch.object(act.os, 'access', return_value=False):
                self.assertIn('No se puede escribir', act.motivo_sin_instalar())
        with mock.patch.object(act, 'tipo_linux', return_value='deb'), mock.patch.object(act.os, 'geteuid', return_value=1000):
            with self.which('apt-get', 'pkexec'):
                self.assertTrue(act.puede_instalarse())
            with self.which('apt-get'):
                self.assertIn('pkexec', act.motivo_sin_instalar())

    def test_descargas_en_la_cache_del_usuario(self):
        with mock.patch.dict(act.os.environ, {'XDG_CACHE_HOME': str(self.d)}):
            self.assertEqual(act.carpeta_descargas(), self.d / 'bajar-subtitulos-esp' / 'actualizacion')


class InstruccionesDeLaRelease(unittest.TestCase):
    """packaging/instalar.py (el workflow lo ejecuta y sube a cada Release INSTALAR-<versión>.txt y .md) nombra
    exactamente los archivos que se publican: si cambia un nombre, hay que cambiarlo también ahí."""
    RAIZ = Path(__file__).resolve().parent.parent

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location('instalar', cls.RAIZ / 'packaging' / 'instalar.py')
        cls.inst = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.inst)

    def nombres(self, v):
        nombres = {act.nombre_instalador(v, 'windows')}
        nombres |= {act.nombre_instalador(v, 'linux', t) for t in act.SUFIJOS_LINUX}
        return nombres | {f'BajarSubtitulosESP-{v}-windows-portable.zip', f'BajarSubtitulosESP-{v}-linux-x86_64.tar.gz'}

    def test_nombra_los_archivos_de_la_release(self):
        for formato in ('txt', 'md'):
            with self.subTest(formato=formato):
                texto = getattr(self.inst, formato)('9.8.7')
                self.assertNotIn('\r', texto)       # con retornos de carro, las órdenes pegadas en Linux fallan
                citados = set(re.findall(r'BajarSubtitulosESP-9\.8\.7-[A-Za-z0-9_.-]*[A-Za-z0-9]', texto))
                self.assertEqual(citados, self.nombres('9.8.7'))          # todos y ninguno más (una errata
                self.assertNotRegex(texto, r'BajarSubtitulosESP-(?!9\.8\.7-)[0-9]')   # dejaría una orden rota)

    def test_los_dos_formatos_dicen_lo_mismo(self):
        """Las mismas órdenes, una por línea, en los dos (en el .txt con sangría; en el .md, en bloques)."""
        def ordenes(texto):
            return [ln.strip() for ln in texto.splitlines()
                    if ln.startswith('    ') or (ln and not ln.startswith(('```', '|', '#', '*', '-', ' ')) and
                                                 ln.split(' ', 1)[0] in ('sudo', 'chmod', 'tar', 'for', './bajar-subtitulos-esp/bajar-subtitulos-esp',
                                                                         'rm', 'sha256sum', 'Get-FileHash'))]
        txt, md = self.inst.txt('9.8.7'), self.inst.md('9.8.7')
        self.assertEqual(ordenes(txt), ordenes(md))
        self.assertEqual(len(ordenes(txt)), 2 * 13)           # instalar (5), desinstalar (5), borrar, 2 sumas: por idioma

    def test_genera_los_dos_archivos(self):
        with tempfile.TemporaryDirectory() as d:
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                self.inst.main(['9.8.7', d])
            self.assertEqual(sorted(p.name for p in Path(d).iterdir()), ['INSTALAR-9.8.7.md', 'INSTALAR-9.8.7.txt'])

    def test_el_workflow_lo_publica(self):
        wf = (self.RAIZ / '.github' / 'workflows' / 'compilar.yml').read_text(encoding='utf-8')
        self.assertIn('python3 -I packaging/instalar.py "${GITHUB_REF_NAME#v}" dist', wf)
        for ext in ('txt', 'md'):
            self.assertIn(f'"dist/INSTALAR-${{GITHUB_REF_NAME#v}}.{ext}#', wf)
            self.assertIn(f'dist/INSTALAR-*.{ext}\n', wf)
        self.assertIn('INSTALAR-*.txt INSTALAR-*.md > SHA256SUMS.txt', wf)
        for nombre in self.nombres('$v'):
            self.assertIn(f'"{nombre}"', wf)                   # el workflow comprueba que estén todos

if __name__ == '__main__':
    unittest.main(verbosity=2)
