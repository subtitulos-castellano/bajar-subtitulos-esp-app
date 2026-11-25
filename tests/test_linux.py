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
            self.assertNotIn('PYINSTALLER_RESET_ENVIRONMENT', os.environ)

    def test_compilado_vuelve_al_de_antes(self):
        with mock.patch.object(sys, 'frozen', True, create=True):
            with mock.patch.dict(os.environ, {'LD_LIBRARY_PATH': '/app/_internal', 'LD_LIBRARY_PATH_ORIG': '/y'}):
                linux.entorno_para_otros_programas()
                self.assertEqual(os.environ['LD_LIBRARY_PATH'], '/y')
                self.assertNotIn('LD_LIBRARY_PATH_ORIG', os.environ)
                self.assertEqual(os.environ['PYINSTALLER_RESET_ENVIRONMENT'], '1')   # al volver a abrirse
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



@unittest.skipUnless(LINUX, 'solo en Linux')
class MenuContextualLinux(unittest.TestCase):
    """En una carpeta de datos temporal ($XDG_DATA_HOME), nunca en el ~/.local/share de verdad."""

    def setUp(self):
        from app import menu_contextual as mc
        from app.config import Config
        from app.plataforma import menu_linux as ml
        from subtitulos import idioma
        self.mc, self.ml, self.idioma = mc, ml, idioma
        self._d = tempfile.TemporaryDirectory()
        self.addCleanup(self._d.cleanup)
        self.d = Path(self._d.name)
        entorno = mock.patch.dict(os.environ, {'XDG_DATA_HOME': str(self.d / 'datos')})
        entorno.start()
        self.addCleanup(entorno.stop)
        self.addCleanup(idioma.poner, 'es')
        # Un «programa» que apunta lo que recibe, en una ruta con espacios y caracteres raros.
        self.salida = self.d / 'recibido.txt'
        self.prog = self.d / 'mi carpeta $x' / 'bajar-subtitulos-esp'
        self.prog.parent.mkdir()
        self.prog.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > {self.salida}\n')
        self.prog.chmod(0o755)
        self.config = Config(self.d / 'config.json')

    def todos(self):
        return sorted(p.relative_to(self.d / 'datos').as_posix() for p in (self.d / 'datos').rglob('*')
                      if p.is_file())

    def ejecutar(self, orden, cwd=None):
        import subprocess
        subprocess.run(orden, cwd=cwd, check=True, timeout=30)
        return self.salida.read_text().splitlines() if self.salida.exists() else None

    def test_registrar_y_quitar(self):
        self.mc.registrar([str(self.prog)])
        self.assertEqual(self.todos(), [
            'bajar-subtitulos-esp/icono.svg', 'bajar-subtitulos-esp/menu-contextual',
            'kio/servicemenus/bajar-subtitulos-esp-carpetas.desktop',
            'kio/servicemenus/bajar-subtitulos-esp-videos.desktop',
            'nautilus/scripts/Bajar subtítulos', 'nautilus/scripts/Bajar subtítulos (solo esta carpeta)',
            'nautilus/scripts/Bajar subtítulos en inglés',
            'nautilus/scripts/Bajar subtítulos en inglés (solo esta carpeta)']
            + sorted(f'nemo/actions/bajar-subtitulos-esp-{n}.nemo_action' for n in range(1, 11)))
        datos = self.d / 'datos'
        for ejecutable in ('kio/servicemenus/bajar-subtitulos-esp-carpetas.desktop', 'nautilus/scripts/Bajar subtítulos',
                           'bajar-subtitulos-esp/menu-contextual'):
            self.assertTrue(os.access(datos / ejecutable, os.X_OK), ejecutable)
        self.assertTrue(self.mc.registrado())
        self.assertEqual(self.mc.programa_registrado(), self.prog)
        self.assertTrue(self.mc.es_de([str(self.prog)]))
        self.assertTrue(self.ml.al_dia([str(self.prog)]))
        self.assertEqual(self.mc.texto_registrado(), 'Bajar subtítulos aquí')
        # Un script del usuario en la misma carpeta no se toca.
        (datos / 'nautilus/scripts/Mío').write_text('#!/bin/sh\n')
        self.mc.quitar()
        self.assertEqual(self.todos(), ['nautilus/scripts/Mío'])
        self.assertFalse(self.mc.registrado())

    def test_dolphin(self):
        self.mc.registrar([str(self.prog)])
        texto = (self.d / 'datos/kio/servicemenus/bajar-subtitulos-esp-carpetas.desktop').read_text()
        lz = str(self.ml.lanzador())
        self.assertIn('MimeType=inode/directory;', texto)
        self.assertIn('X-KDE-Submenu=Bajar subtítulos aquí', texto)
        self.assertIn('[Desktop Action solo]\nName=Solo esta carpeta', texto)
        self.assertIn(f'Exec="{lz}" --menu-carpeta %F', texto)
        self.assertIn(f'Exec="{lz}" --menu-subcarpetas %F', texto)
        videos = (self.d / 'datos/kio/servicemenus/bajar-subtitulos-esp-videos.desktop').read_text()
        self.assertIn('video/x-matroska;', videos)
        self.assertNotIn('video/mp2t', videos)                      # .ts: también es TypeScript
        self.assertIn(f'Exec="{lz}" --menu-archivos %F', videos)

    def test_exec_con_caracteres_reservados(self):
        self.assertEqual(self.ml._exec('/a b/$x"y`z\\w%', '--menu-archivos', '%F'),
                         '"/a b/\\$x\\"y\\`z\\\\w%%" --menu-archivos %F')

    def test_el_lanzador_abre_la_app_con_lo_seleccionado(self):
        self.mc.registrar([str(self.prog)])
        recibido = self.ejecutar([str(self.ml.lanzador()), '--menu-archivos', '/v/a b.mkv', '/v/c.mkv'])
        self.assertEqual(recibido, ['--menu-archivos', '/v/a b.mkv', '/v/c.mkv'])

    def test_scripts_de_nautilus(self):
        self.mc.registrar([str(self.prog)])
        carpeta = self.d / 'Serie'
        carpeta.mkdir()
        scripts = self.d / 'datos/nautilus/scripts'
        self.assertEqual(self.ejecutar([str(scripts / 'Bajar subtítulos'), 'a.mkv', 'Temporada 1'], cwd=carpeta),
                         ['--menu-subcarpetas', 'a.mkv', 'Temporada 1'])      # la app las hace absolutas
        # Sin nada seleccionado (clic en el fondo): la carpeta abierta.
        self.assertEqual(self.ejecutar([str(scripts / 'Bajar subtítulos (solo esta carpeta)')], cwd=carpeta),
                         ['--menu-carpeta', str(carpeta)])

    def test_sin_la_app_el_menu_se_quita_solo(self):
        """Desinstalada (o borrado el AppImage): al usar el menú, se limpia en vez de dar un error."""
        self.mc.registrar([str(self.prog)])
        self.prog.unlink()
        self.assertIsNone(self.ejecutar([str(self.ml.lanzador()), '--menu-carpeta', '/v']))
        self.assertEqual(self.todos(), [])
        self.assertFalse((self.d / 'datos/bajar-subtitulos-esp').exists())

    def test_desde_el_codigo_fuente(self):
        prog = [sys.executable, '-I', str(Path(__file__).resolve().parent.parent / 'app' / 'main.py')]
        self.mc.registrar(prog)
        self.assertEqual(self.ml._programa_del_lanzador(), prog)
        self.assertEqual(self.mc.programa_registrado(), Path(sys.executable))

    def test_idioma(self):
        self.config.menu_contextual = True
        self.mc.registrar([str(self.prog)])
        self.idioma.poner('en')
        self.assertTrue(self.mc.asegurar(self.config, instalada=False, prog=[str(self.prog)]))
        self.assertEqual(self.mc.texto_registrado(), 'Get subtitles here')
        self.assertIn('nautilus/scripts/Get subtitles', self.todos())
        self.assertNotIn('nautilus/scripts/Bajar subtítulos', self.todos())
        self.assertEqual(self.mc.programa_registrado(), self.prog)

    def test_appimage_movido_se_rehace(self):
        self.config.menu_contextual = True
        self.mc.registrar([str(self.d / 'antes' / 'BajarSubtitulosESP.AppImage')])
        self.assertTrue(self.mc.asegurar(self.config, instalada=False, prog=[str(self.prog)]))
        self.assertEqual(self.mc.programa_registrado(), self.prog)

    def test_paquete_sin_decidir_lo_añade_y_appimage_no(self):
        self.assertFalse(self.mc.asegurar(self.config, instalada=False, prog=[str(self.prog)]))
        self.assertFalse(self.mc.registrado())
        self.assertTrue(self.mc.asegurar(self.config, instalada=True, prog=[str(self.prog)]))
        self.assertTrue(self.mc.registrado())
        self.assertFalse(self.mc.asegurar(self.config, instalada=True, prog=[str(self.prog)]))  # ya al día

    def test_configuracion(self):
        from app.ventana import Ventana
        v = Ventana(self.config)
        self.addCleanup(v.close)
        a = v.ajustes
        self.assertTrue(a.menu.isEnabled())
        self.assertIn('Scripts', a.estado_menu.text())
        self.assertFalse(a.menu.isChecked())
        with mock.patch.object(self.mc, 'programa', lambda: [str(self.prog)]):
            a.menu.click()
        self.assertTrue(self.mc.registrado())
        a.menu.click()
        self.assertFalse(self.mc.registrado())
        a.poner_bandeja_disponible(False)                  # sin icono junto al reloj: siempre con ventana
        self.assertFalse(a.fila_modo_menu.isVisibleTo(a))
        a.poner_bandeja_disponible(True)
        self.assertTrue(a.fila_modo_menu.isVisibleTo(a))


@unittest.skipUnless(LINUX, 'solo en Linux')
class TipoDeInstalacion(unittest.TestCase):
    def test_tipos(self):
        from app import menu_contextual as mc
        self.assertEqual(linux.instalacion(), 'codigo')
        self.assertFalse(mc.instalada_con_paquete())
        with mock.patch.object(sys, 'frozen', True, create=True), \
                mock.patch.dict(os.environ, {'APPIMAGE': '', 'APPDIR': ''}):
            with mock.patch.object(sys, 'executable', '/opt/bajar-subtitulos-esp/bajar-subtitulos-esp'):
                self.assertEqual(linux.instalacion(), 'paquete')
                self.assertTrue(mc.instalada_con_paquete())
            with mock.patch.object(sys, 'executable', '/home/u/BajarSubtitulosESP/bajar-subtitulos-esp'):
                self.assertEqual(linux.instalacion(), 'carpeta')
            with mock.patch.object(sys, 'executable', '/tmp/.mount_Bajar1/usr/lib/bajar-subtitulos-esp/x'), \
                    mock.patch.dict(os.environ, {'APPIMAGE': '/home/u/B.AppImage', 'APPDIR': '/tmp/.mount_Bajar1'}):
                self.assertEqual(linux.instalacion(), 'appimage')
                self.assertEqual(mc.programa(), ['/home/u/B.AppImage'])       # no lo de dentro del montaje
            # Un programa abierto desde un AppImage hereda sus variables: no es el AppImage.
            with mock.patch.object(sys, 'executable', '/opt/bajar-subtitulos-esp/bajar-subtitulos-esp'), \
                    mock.patch.dict(os.environ, {'APPIMAGE': '/home/u/Otro.AppImage', 'APPDIR': '/tmp/.mount_Otro'}):
                self.assertEqual(linux.instalacion(), 'paquete')


@unittest.skipUnless(LINUX, 'solo en Linux')
class MenuDeAplicaciones(unittest.TestCase):
    """La entrada del AppImage, en una carpeta de datos temporal."""
    PLANTILLA = (Path(__file__).resolve().parent.parent / 'packaging' / 'linux' / 'bajar-subtitulos-esp.desktop')

    def setUp(self):
        from app.config import Config
        from app.plataforma import menu_aplicaciones as ma
        self.ma = ma
        self._d = tempfile.TemporaryDirectory()
        self.addCleanup(self._d.cleanup)
        self.d = Path(self._d.name)
        entorno = mock.patch.dict(os.environ, {'XDG_DATA_HOME': str(self.d / 'datos')})
        entorno.start()
        self.addCleanup(entorno.stop)
        self.plantilla = self.PLANTILLA.read_text(encoding='utf-8')
        self.appimage = self.d / 'Mis programas' / 'BajarSubtitulosESP-1.5.0-linux-x86_64.AppImage'
        self.config = Config(self.d / 'config.json')

    def test_anadir_y_quitar(self):
        self.ma.anadir(self.appimage, self.plantilla)
        texto = (self.d / 'datos/applications/bajar-subtitulos-esp.desktop').read_text(encoding='utf-8')
        self.assertIn(f'Exec="{self.appimage}" %F\n', texto)
        self.assertIn(f'TryExec={self.appimage}\n', texto)          # borrado el AppImage, no se ve
        self.assertEqual(texto.count('Exec='), 2)                   # Exec y TryExec, sin el de la plantilla
        self.assertIn('MimeType=video/x-matroska;', texto)          # «Abrir con» en los vídeos
        self.assertTrue((self.d / 'datos/icons/hicolor/scalable/apps/bajar-subtitulos-esp.svg').exists())
        self.assertTrue(self.ma.anadida())
        self.assertEqual(self.ma.appimage_anadido(), self.appimage)
        self.ma.quitar()
        self.assertFalse(self.ma.anadida())
        self.assertEqual([p for p in (self.d / 'datos').rglob('*')                  # (la caché de tipos
                          if p.is_file() and p.name != 'mimeinfo.cache'], [])        # es del escritorio)

    def test_no_quita_una_entrada_que_no_es_suya(self):
        ruta = self.d / 'datos/applications/bajar-subtitulos-esp.desktop'
        ruta.parent.mkdir(parents=True)
        ruta.write_text(self.plantilla)
        self.assertFalse(self.ma.anadida())
        self.ma.quitar()
        self.assertTrue(ruta.exists())

    def test_appimage_movido_se_corrige(self):
        self.config.menu_aplicaciones = True
        self.ma.anadir(self.d / 'antes.AppImage', self.plantilla)
        self.assertTrue(self.ma.asegurar(self.config, self.appimage, self.plantilla))
        self.assertEqual(self.ma.appimage_anadido(), self.appimage)
        self.assertFalse(self.ma.asegurar(self.config, self.appimage, self.plantilla))     # ya al día

    def test_sin_activar_no_se_toca(self):
        for valor in (None, False):
            self.config.menu_aplicaciones = valor
            self.assertFalse(self.ma.asegurar(self.config, self.appimage, self.plantilla))
            self.assertFalse(self.ma.anadida())

    def test_configuracion_se_guarda(self):
        from app.config import Config
        self.config.menu_aplicaciones = True
        self.config.guardar()
        self.assertTrue(Config(self.config.ruta).menu_aplicaciones)

    def test_ajustes_solo_en_el_appimage(self):
        from app.ventana import Ventana
        v = Ventana(self.config)
        self.addCleanup(v.close)
        self.assertFalse(hasattr(v.ajustes, 'menu_apps'))
        with mock.patch.object(linux, 'appimage', return_value=self.appimage), \
                mock.patch.object(self.ma, '_plantilla', return_value=self.plantilla):
            v2 = Ventana(self.config)
            self.addCleanup(v2.close)
            v2.ajustes.menu_apps.click()
            self.assertTrue(self.ma.anadida())
            self.assertTrue(self.config.menu_aplicaciones)
            v2.ajustes.menu_apps.click()
            self.assertFalse(self.ma.anadida())
            self.assertIs(self.config.menu_aplicaciones, False)


@unittest.skipUnless(LINUX, 'solo en Linux')
class AccesosAlDesinstalar(unittest.TestCase):
    """--desinstalar (los .deb y .rpm lo ejecutan para cada usuario): accesos del escritorio, anclado en la
    barra de Plasma y la app oculta a mano del menú. En un $HOME temporal, nunca en el de verdad."""

    # Lo que dejó KDE en un AlmaLinux 10 con Plasma 6 al «borrar» la app del menú (y, abajo, cómo debe quedar).
    KMENUEDIT = """<!DOCTYPE Menu PUBLIC '-//freedesktop//DTD Menu 1.0//EN' 'http://www.freedesktop.org/standards/menu-spec/menu-1.0.dtd'>
<Menu>
 <Menu>
  <Name>Multimedia</Name>
  <Layout>
   <Merge type="menus"/>
   <Menuname>More</Menuname>
   <Merge type="files"/>
   <Filename>org.kde.dragonplayer.desktop</Filename>
   <Filename>org.kde.elisa.desktop</Filename>
  </Layout>
  <Exclude>
   <Filename>bajar-subtitulos-esp.desktop</Filename>
  </Exclude>
 </Menu>
 <Menu>
  <Name>.hidden</Name>
  <Include>
   <Filename>bajar-subtitulos-esp.desktop</Filename>
  </Include>
 </Menu>
</Menu>
"""
    KMENUEDIT_LIMPIO = KMENUEDIT.replace('   <Filename>bajar-subtitulos-esp.desktop</Filename>\n', '')
    SISTEMA = Path(__file__).resolve().parent.parent / 'packaging' / 'linux' / 'bajar-subtitulos-esp.desktop'

    def setUp(self):
        from app.plataforma import accesos_linux as al
        self.al = al
        self._d = tempfile.TemporaryDirectory()
        self.addCleanup(self._d.cleanup)
        self.casa = Path(self._d.name) / 'casa'
        self.config = self.casa / '.config'
        self.datos = self.casa / '.local' / 'share'
        self.escritorio = self.casa / 'Escritorio'
        for c in (self.config / 'menus', self.datos / 'applications', self.escritorio):
            c.mkdir(parents=True)
        (self.config / 'user-dirs.dirs').write_text('# xdg-user-dirs\nXDG_DESKTOP_DIR="$HOME/Escritorio"\n'
                                                     'XDG_DOWNLOAD_DIR="$HOME/Descargas"\n')
        self.entorno = {'HOME': str(self.casa), 'XDG_CONFIG_HOME': str(self.config),
                        'XDG_DATA_HOME': str(self.datos)}
        e = mock.patch.dict(os.environ, self.entorno)
        e.start()
        self.addCleanup(e.stop)
        sin_kde = mock.patch.object(al, '_ejecutar', return_value=True)     # kbuildsycoca, qdbus…
        self.ejecutar = sin_kde.start()
        self.addCleanup(sin_kde.stop)

    def test_carpeta_del_escritorio(self):
        self.assertEqual(self.al.carpeta_escritorio(), self.escritorio)
        (self.config / 'user-dirs.dirs').unlink()
        self.assertEqual(self.al.carpeta_escritorio(), self.casa / 'Desktop')

    def test_vuelve_al_menu_tras_ocultarla_en_kde(self):
        menu = self.config / 'menus' / 'applications-kmenuedit.menu'
        menu.write_text(self.KMENUEDIT)
        self.assertTrue(self.al.mostrar_en_menu())
        self.assertEqual(menu.read_text(), self.KMENUEDIT_LIMPIO)        # lo demás, igual
        self.ejecutar.assert_called_once_with(['kbuildsycoca6'], ['kbuildsycoca5'])
        self.assertFalse(self.al.mostrar_en_menu())                      # ya no hay nada que quitar

    def test_solo_quita_lo_de_la_app(self):
        texto = ('<Menu><Menu><Name>Juegos</Name><Exclude><Filename>otro.desktop</Filename>'
                 '<Filename>bajar-subtitulos-esp.desktop</Filename></Exclude>'
                 '<Layout><Filename>bajar-subtitulos-esp.desktop</Filename></Layout></Menu></Menu>\n')
        self.assertEqual(self.al.sin_ocultar(texto), texto.replace(
            '<Filename>bajar-subtitulos-esp.desktop</Filename></Exclude>', '</Exclude>'))

    def test_copia_que_la_oculta_en_otros_escritorios(self):
        copia = self.datos / 'applications' / 'bajar-subtitulos-esp.desktop'
        copia.write_text(self.SISTEMA.read_text(encoding='utf-8') + 'NoDisplay=true\n', encoding='utf-8')
        self.assertTrue(self.al.mostrar_en_menu())
        self.assertFalse(copia.exists())
        # La entrada del AppImage no es una nota para ocultarla: la quita menu_aplicaciones, si es suya.
        copia.write_text('[Desktop Entry]\nNoDisplay=true\nX-BajarSubtitulosESP-AppImage=true\n')
        self.assertFalse(self.al.mostrar_en_menu())
        self.assertTrue(copia.exists())

    def test_accesos_del_escritorio(self):
        enlace = self.escritorio / 'bajar-subtitulos-esp.desktop'
        enlace.symlink_to('/usr/share/applications/bajar-subtitulos-esp.desktop')    # como KDE (aquí, roto)
        copia = self.escritorio / 'Bajar Subtítulos ESP.desktop'                     # como Cinnamon o GNOME
        copia.write_text(self.SISTEMA.read_text(encoding='utf-8'), encoding='utf-8')
        appimage = self.escritorio / 'subtitulos.desktop'
        appimage.write_text('[Desktop Entry]\nType=Application\nName=Bajar Subtítulos ESP\n'
                            'Exec="/home/x/Apps/BajarSubtitulosESP-1.5.4-linux-x86_64.AppImage" %F\n'
                            'Icon=bajar-subtitulos-esp\n', encoding='utf-8')
        otros = {
            'firefox.desktop': '[Desktop Entry]\nType=Application\nExec=firefox %u\nIcon=firefox\n',
            'parecido.desktop': '[Desktop Entry]\nType=Application\nExec=otro-programa\nIcon=bajar-subtitulos-esp\n',
            'bajar-subtitulos-esp.txt': 'notas',
            'Link.desktop': '[Desktop Entry]\nType=Link\nURL=https://example.com\nIcon=bajar-subtitulos-esp\n',
        }
        for nombre, texto in otros.items():
            (self.escritorio / nombre).write_text(texto, encoding='utf-8')
        (self.escritorio / 'otro-enlace.desktop').symlink_to('/usr/share/applications/firefox.desktop')
        quitados = self.al.quitar_accesos_escritorio()
        self.assertEqual(sorted(p.name for p in quitados), sorted([enlace.name, copia.name, appimage.name]))
        self.assertEqual(sorted(p.name for p in self.escritorio.iterdir()), sorted([*otros, 'otro-enlace.desktop']))

    def test_anclado_con_plasma_cerrado(self):
        archivo = self.config / 'plasma-org.kde.plasma.desktop-appletsrc'
        antes = ('[Containments][2][Applets][5][Configuration][General]\n'
                 'launchers=applications:systemsettings.desktop,preferred://filemanager,'
                 'applications:bajar-subtitulos-esp.desktop,file:///usr/share/applications/bajar-subtitulos-esp.desktop,'
                 'preferred://browser\n\n[Otro]\nclave=applications:bajar-subtitulos-esp.desktop\n')
        archivo.write_text(antes, encoding='utf-8')
        with mock.patch.object(self.al, '_plasma_abierto', return_value=False):
            self.assertTrue(self.al.quitar_anclado())
        self.assertEqual(archivo.read_text(encoding='utf-8'), antes.replace(
            'applications:bajar-subtitulos-esp.desktop,file:///usr/share/applications/bajar-subtitulos-esp.desktop,', '', 1))
        self.ejecutar.assert_not_called()

    def test_anclado_con_plasma_abierto(self):
        archivo = self.config / 'plasma-org.kde.plasma.desktop-appletsrc'
        antes = 'launchers=preferred://browser,applications:bajar-subtitulos-esp.desktop\n'
        archivo.write_text(antes, encoding='utf-8')
        with mock.patch.object(self.al, '_plasma_abierto', return_value=True):
            self.assertTrue(self.al.quitar_anclado())
        self.assertEqual(archivo.read_text(encoding='utf-8'), antes)    # Plasma lo reescribiría: se le pide a él
        qdbus = self.ejecutar.call_args.args[0]
        self.assertEqual(qdbus[:4], ['qdbus6', 'org.kde.plasmashell', '/PlasmaShell',
                                     'org.kde.PlasmaShell.evaluateScript'])
        self.assertIn('"applications:bajar-subtitulos-esp.desktop"', qdbus[4])
        gdbus = self.ejecutar.call_args.args[2]
        self.assertEqual(gdbus[-1], self.al._variant_texto(self.al.SCRIPT_PLASMA))
        self.assertTrue(gdbus[-1].startswith("'") and "\\'" not in self.al.SCRIPT_PLASMA)

    def test_sin_anclado_no_hace_nada(self):
        (self.config / 'plasma-org.kde.plasma.desktop-appletsrc').write_text('launchers=preferred://browser\n')
        with mock.patch.object(self.al, '_plasma_abierto', side_effect=AssertionError('no hace falta mirarlo')):
            self.assertTrue(self.al.quitar_anclado())
        self.ejecutar.assert_not_called()

    def test_la_opcion_desinstalar_sin_pantalla(self):
        """La app con --desinstalar (como la ejecutan los paquetes): sin pantalla ni sesión, lo limpia todo."""
        import subprocess
        (self.config / 'menus' / 'applications-kmenuedit.menu').write_text(self.KMENUEDIT)
        (self.escritorio / 'bajar-subtitulos-esp.desktop').symlink_to('/usr/share/applications/bajar-subtitulos-esp.desktop')
        (self.config / 'plasma-org.kde.plasma.desktop-appletsrc').write_text(
            'launchers=applications:bajar-subtitulos-esp.desktop,preferred://browser\n')
        entorno = {k: v for k, v in os.environ.items() if k not in ('DISPLAY', 'WAYLAND_DISPLAY')}
        entorno.update(self.entorno, PATH='/usr/bin:/bin')           # sin kbuildsycoca ni qdbus de verdad
        raiz = Path(__file__).resolve().parent.parent
        r = subprocess.run([sys.executable, '-m', 'app.main', '--desinstalar', '--config',
                            str(self.casa / 'config.json')], cwd=raiz, env=entorno, timeout=60,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.config / 'menus' / 'applications-kmenuedit.menu').read_text(), self.KMENUEDIT_LIMPIO)
        self.assertEqual(list(self.escritorio.iterdir()), [])
        self.assertEqual((self.config / 'plasma-org.kde.plasma.desktop-appletsrc').read_text(),
                         'launchers=preferred://browser\n')


    def test_con_usuario_sin_ser_root_no_hace_nada(self):
        import subprocess
        if os.geteuid() == 0:
            self.skipTest('como root')
        (self.escritorio / 'bajar-subtitulos-esp.desktop').symlink_to('/usr/share/applications/bajar-subtitulos-esp.desktop')
        entorno = {k: v for k, v in os.environ.items() if k not in ('DISPLAY', 'WAYLAND_DISPLAY')}
        entorno.update(self.entorno)
        r = subprocess.run([sys.executable, '-m', 'app.main', '--desinstalar', '--usuario', 'nadie'],
                           cwd=Path(__file__).resolve().parent.parent, env=entorno, timeout=60,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertTrue((self.escritorio / 'bajar-subtitulos-esp.desktop').is_symlink())

    def test_hacerse_usuario(self):
        import pwd
        casa = self.casa
        pw = pwd.struct_passwd(('ana', 'x', 1234, 1234, '', str(casa), '/bin/sh'))
        ids = {'uid': 0, 'gid': 0}
        hechos = []
        os.environ.update(XDG_RUNTIME_DIR='/run/user/0', DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/0/bus')
        with mock.patch.object(pwd, 'getpwnam', return_value=pw), \
                mock.patch.object(os, 'initgroups', side_effect=lambda n, g: hechos.append(('grupos', n, g))), \
                mock.patch.object(os, 'setgid', side_effect=lambda g: ids.update(gid=g)), \
                mock.patch.object(os, 'setuid', side_effect=lambda u: ids.update(uid=u)), \
                mock.patch.object(os, 'getuid', side_effect=lambda: ids['uid']), \
                mock.patch.object(os, 'geteuid', side_effect=lambda: ids['uid']), \
                mock.patch.object(os, 'getegid', side_effect=lambda: ids['gid']), \
                mock.patch.object(os, 'chdir'):
            linux.hacerse_usuario('ana')
        self.assertEqual(ids, {'uid': 1234, 'gid': 1234})
        self.assertEqual(hechos, [('grupos', 'ana', 1234)])
        self.assertEqual(os.environ['HOME'], str(casa))
        self.assertEqual(os.environ['USER'], 'ana')
        for v in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS'):
            self.assertNotIn(v, os.environ)                       # sin sesión abierta: sin su D-Bus
        root = pwd.struct_passwd(('root', 'x', 0, 0, '', '/root', '/bin/sh'))
        with mock.patch.object(pwd, 'getpwnam', return_value=root), self.assertRaises(OSError):
            linux.hacerse_usuario('root')


if __name__ == '__main__':
    unittest.main(verbosity=2)
