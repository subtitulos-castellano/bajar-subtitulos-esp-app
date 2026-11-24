"""Lo propio de Linux: carpetas XDG, una sola app abierta (bloqueo), token de activación de Wayland y un
llavero del sistema lento o bloqueado. Desde la raíz del proyecto:
    python -I tests/test_linux.py
"""
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import credenciales  # noqa: E402
from app.plataforma import LINUX  # noqa: E402

if LINUX:
    from app.plataforma import linux


@unittest.skipUnless(LINUX, 'solo en Linux')
class EntornoParaOtrosProgramas(unittest.TestCase):
    def test_desde_el_codigo_no_cambia(self):
        with mock.patch.dict(os.environ, {'LD_LIBRARY_PATH': '/x', 'LD_LIBRARY_PATH_ORIG': '/y'}):
            linux.entorno_para_otros_programas()
            self.assertEqual(os.environ['LD_LIBRARY_PATH'], '/x')

    def test_compilado_vuelve_al_de_antes(self):
        with mock.patch.object(sys, 'frozen', True, create=True):
            with mock.patch.dict(os.environ, {'LD_LIBRARY_PATH': '/app/_internal', 'LD_LIBRARY_PATH_ORIG': '/y'}):
                linux.entorno_para_otros_programas()
                self.assertEqual(os.environ['LD_LIBRARY_PATH'], '/y')
                self.assertNotIn('LD_LIBRARY_PATH_ORIG', os.environ)
            with mock.patch.dict(os.environ, {'LD_LIBRARY_PATH': '/app/_internal'}):
                os.environ.pop('LD_LIBRARY_PATH_ORIG', None)
                linux.entorno_para_otros_programas()
                self.assertNotIn('LD_LIBRARY_PATH', os.environ)


@unittest.skipUnless(LINUX, 'solo en Linux')
class Certificados(unittest.TestCase):
    """El OpenSSL del programa compilado viene de AlmaLinux: en otras distribuciones hay que decirle dónde
    están los certificados del sistema (si no, «SSLCertVerificationError» con OpenSubtitles.org)."""
    SIN = {'SSL_CERT_FILE': '', 'SSL_CERT_DIR': ''}

    def _limpio(self, extra=None):
        entorno = mock.patch.dict(os.environ, dict(self.SIN, **(extra or {})))
        entorno.start()
        self.addCleanup(entorno.stop)
        for v in ('SSL_CERT_FILE', 'SSL_CERT_DIR'):
            if not os.environ[v]:
                del os.environ[v]

    def _openssl_busca_en(self, ruta):
        import ssl
        rutas = ssl.get_default_verify_paths()
        return mock.patch('ssl.get_default_verify_paths', return_value=rutas._replace(openssl_cafile=ruta))

    def test_desde_el_codigo_no_cambia(self):
        self._limpio()
        with self._openssl_busca_en('/no-existe/cert.pem'):
            self.assertIsNone(linux.certificados())
        self.assertNotIn('SSL_CERT_FILE', os.environ)

    def test_compilado_usa_los_del_sistema(self):
        self._limpio()
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sys, 'frozen', True, create=True):
            debian = Path(d, 'ca-certificates.crt')
            debian.write_text('x')
            with self._openssl_busca_en('/no-existe/cert.pem'), \
                    mock.patch.object(linux, 'CERTIFICADOS', ('/no-existe/ca-bundle.crt', str(debian))):
                self.assertEqual(linux.certificados(), str(debian))
                self.assertEqual(os.environ['SSL_CERT_FILE'], str(debian))

    def test_compilado_sin_certificados_del_sistema_usa_certifi(self):
        self._limpio()
        import certifi
        with mock.patch.object(sys, 'frozen', True, create=True), self._openssl_busca_en('/no-existe/cert.pem'), \
                mock.patch.object(linux, 'CERTIFICADOS', ('/no-existe/ca-bundle.crt',)):
            self.assertEqual(linux.certificados(), certifi.where())

    def test_no_toca_nada_si_openssl_los_encuentra_o_el_usuario_eligio(self):
        with tempfile.NamedTemporaryFile() as f, mock.patch.object(sys, 'frozen', True, create=True):
            self._limpio()
            with self._openssl_busca_en(f.name):            # AlmaLinux, Fedora…
                self.assertIsNone(linux.certificados())
                self.assertNotIn('SSL_CERT_FILE', os.environ)
            self._limpio({'SSL_CERT_DIR': '/mis/certificados'})
            with self._openssl_busca_en('/no-existe/cert.pem'):
                self.assertIsNone(linux.certificados())
                self.assertNotIn('SSL_CERT_FILE', os.environ)


@unittest.skipUnless(LINUX, 'solo en Linux')
class WSL(unittest.TestCase):
    def test_deteccion(self):
        with mock.patch.dict(os.environ, {'WSL_DISTRO_NAME': 'Ubuntu'}):
            self.assertTrue(linux.en_wsl())
        with mock.patch.dict(os.environ, {'WSL_DISTRO_NAME': ''}):
            with mock.patch('platform.release', return_value='6.18.58.1-microsoft-standard-WSL2'):
                self.assertTrue(linux.en_wsl())
            with mock.patch('platform.release', return_value='6.12.0-264.17.1.el10_3.x86_64'):
                self.assertFalse(linux.en_wsl())


@unittest.skipUnless(LINUX, 'solo en Linux')
class Carpetas(unittest.TestCase):
    def test_config_xdg(self):
        with mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': '/tmp/xdg-prueba'}):
            self.assertEqual(linux.carpeta_config(), Path('/tmp/xdg-prueba'))
        for malo in ('', 'relativa/config'):           # la especificación solo admite rutas absolutas
            with mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': malo}):
                self.assertEqual(linux.carpeta_config(), Path.home() / '.config')

    def test_config_de_la_app(self):
        from app import config
        with mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': '/tmp/xdg-prueba'}):
            self.assertEqual(config.carpeta(), Path('/tmp/xdg-prueba/BajarSubtitulosEsp'))

    def test_carpeta_de_ejecucion(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {'XDG_RUNTIME_DIR': d}):
                self.assertEqual(linux.carpeta_ejecucion(), Path(d))
            with mock.patch.dict(os.environ, {'XDG_RUNTIME_DIR': d + '/no-existe'}):
                self.assertEqual(linux.carpeta_ejecucion(), Path(tempfile.gettempdir()))

    def test_canal_en_la_carpeta_privada(self):
        from app import instancia
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {'XDG_RUNTIME_DIR': d}):
            self.assertEqual(Path(instancia.nombre_canal()).parent, Path(d))


@unittest.skipUnless(LINUX, 'solo en Linux')
class Bloqueo(unittest.TestCase):
    def test_solo_uno_a_la_vez(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / 'app.lock'
            primero = linux.bloquear(ruta)
            self.assertIsInstance(primero, int)
            self.assertIsNone(linux.bloquear(ruta))       # otra apertura: ya lo tiene la primera
            linux.soltar(primero)
            segundo = linux.bloquear(ruta)                # al soltarlo (o morir el proceso), se libera
            self.assertIsInstance(segundo, int)
            linux.soltar(segundo)
            self.assertEqual(os.stat(ruta).st_mode & 0o777, 0o600)

    def test_sin_poder_comprobarlo(self):
        self.assertIs(linux.bloquear('/no-existe/app.lock'), False)

    def test_es_la_primera(self):
        from app import instancia
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {'XDG_RUNTIME_DIR': d}):
            self.assertTrue(instancia.es_la_primera())
            try:
                otro = linux.bloquear(instancia.nombre_canal() + '.lock')
                self.assertIsNone(otro)                   # una segunda apertura no lo sería
            finally:
                instancia.soltar()
            self.assertIsNone(instancia._mutex)


@unittest.skipUnless(LINUX, 'solo en Linux')
class TokenDeActivacion(unittest.TestCase):
    def test_se_pasa_a_la_app_abierta(self):
        with mock.patch.dict(os.environ, {'XDG_ACTIVATION_TOKEN': 'kwin-123_abc'}):
            self.assertEqual(linux.token_activacion(), 'kwin-123_abc')
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('XDG_ACTIVATION_TOKEN', None)
            self.assertEqual(linux.token_activacion(), '')
            linux.usar_token_activacion('otro-456')
            self.assertEqual(os.environ['XDG_ACTIVATION_TOKEN'], 'otro-456')

    def test_lo_que_llega_por_el_canal_se_comprueba(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('XDG_ACTIVATION_TOKEN', None)
            for malo in (None, 3, '', 'con espacio', 'línea\nnueva', 'x' * 300, ['a']):
                linux.usar_token_activacion(malo)
                self.assertNotIn('XDG_ACTIVATION_TOKEN', os.environ, malo)


class LlaveroLento:
    """Un llavero bloqueado: no contesta hasta que se «desbloquea»."""

    def __init__(self):
        self.claves = {('BajarSubtitulosESP/opensubtitles', 'pepe'): 'secreta'}
        self.desbloqueado = threading.Event()

    def get_password(self, servicio, usuario):
        self.desbloqueado.wait(10)
        return self.claves.get((servicio, usuario))

    def set_password(self, servicio, usuario, clave):
        self.desbloqueado.wait(10)
        self.claves[(servicio, usuario)] = clave

    def delete_password(self, servicio, usuario):
        self.desbloqueado.wait(10)
        self.claves.pop((servicio, usuario), None)


@unittest.skipUnless(LINUX, 'solo en Linux (en Windows el llavero contesta al momento)')
class LlaveroBloqueado(unittest.TestCase):
    def setUp(self):
        self.llavero = LlaveroLento()
        for parche in (mock.patch.object(credenciales, '_keyring', lambda: self.llavero),
                       mock.patch.object(credenciales, 'PLAZO', 0.2),
                       mock.patch.object(credenciales, '_avisos', [])):
            parche.start()
            self.addCleanup(parche.stop)
        credenciales.olvidar()
        self.addCleanup(credenciales.olvidar)
        self.addCleanup(self.llavero.desbloqueado.set)
        self.avisos = threading.Event()
        credenciales.al_terminar(self.avisos.set)

    def test_leer_no_congela_y_avisa_al_contestar(self):
        t0 = time.monotonic()
        self.assertEqual(credenciales.leer_clave('pepe'), '')            # aún bloqueado: sigue sin ella
        self.assertLess(time.monotonic() - t0, 1)
        t0 = time.monotonic()
        self.assertEqual(credenciales.leer_clave('pepe'), '')            # la lectura sigue en curso: sin esperar
        self.assertLess(time.monotonic() - t0, 0.1)
        self.llavero.desbloqueado.set()
        self.assertTrue(self.avisos.wait(5))
        self.assertEqual(credenciales.leer_clave('pepe'), 'secreta')
        self.assertEqual(credenciales.credenciales_proveedores('pepe'),
                         {'opensubtitles': {'username': 'pepe', 'password': 'secreta'}})

    def test_guardar_queda_pendiente_y_avisa(self):
        self.assertEqual(credenciales.guardar_clave('ana', 'nueva'), credenciales.PENDIENTE)
        self.assertFalse(self.avisos.is_set())
        self.llavero.desbloqueado.set()
        self.assertTrue(self.avisos.wait(5))
        self.assertEqual(credenciales.leer_clave('ana'), 'nueva')
        self.assertEqual(self.llavero.claves[('BajarSubtitulosESP/opensubtitles', 'ana')], 'nueva')

    def test_desbloqueado_es_como_siempre(self):
        self.llavero.desbloqueado.set()
        self.assertIs(credenciales.guardar_clave('ana', 'x'), True)
        self.assertEqual(credenciales.leer_clave('ana'), 'x')
        self.assertFalse(self.avisos.is_set())                            # nada que avisar


class LlaveroQueNoHay(unittest.TestCase):
    def test_sin_keyring(self):
        with mock.patch.object(credenciales, '_keyring', lambda: None):
            self.assertFalse(credenciales.disponible())

    def test_con_el_llavero_que_falla(self):
        from keyring.backends import fail
        falso = mock.Mock(get_keyring=lambda: fail.Keyring())
        with mock.patch.object(credenciales, '_keyring', lambda: falso):
            self.assertFalse(credenciales.disponible())


if __name__ == '__main__':
    unittest.main(verbosity=2)
