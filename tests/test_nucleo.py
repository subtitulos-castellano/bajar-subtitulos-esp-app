"""Pruebas de procesar() y de la CLI con proveedores de subtítulos simulados (sin internet).

La carpeta de prueba cubre todos los casos del resumen:
- castellano ya presente o renombrado desde .es.srt;
- pistas incrustadas (castellano, latino, inglés SDH);
- castellano, latino e inglés de los proveedores;
- subtítulos descartados por tamaño, duplicados o sin nada;
- un .srt en inglés que se mejora (copia de seguridad);
- el límite de vídeos con búsqueda en internet.

`tests/esperado/cli_*.json` contiene la salida y los archivos que produjo el script original
de la skill (antes de separar el núcleo) en los mismos escenarios: la CLI debe seguir dando
exactamente lo mismo.

Uso (con el Python del venv):
    python -I tests/test_nucleo.py
"""
import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import bajar_subs  # noqa: E402
from babelfish import Language  # noqa: E402
from subliminal.subtitle import Subtitle  # noqa: E402
from subliminal.video import Movie  # noqa: E402
from subtitulos import nucleo  # noqa: E402
from subtitulos.opciones import Opciones  # noqa: E402

ESPERADO = Path(__file__).resolve().parent / 'esperado'

# ---------- Subtítulos y proveedores simulados ----------

CAST = ('1\r\n00:00:01,000 --> 00:00:03,000\r\nVale, tío, ¿qué hacéis vosotros aquí? '
        'Os lo dije, chaval.\r\n\r\n')
CAST2 = ('1\r\n00:00:01,000 --> 00:00:03,000\r\nVale, tío, ¿qué hacéis vosotros aquí? Os lo dije, '
         'chaval. Joder, qué guay, vosotras sabéis.\r\n\r\n')
LAT = ('1\r\n00:00:01,000 --> 00:00:03,000\r\nUstedes no saben, ahorita vamos en el carro, '
       'que lindo es para los dos.\r\n\r\n')
ENG = '1\r\n00:00:01,000 --> 00:00:03,000\r\nYou know what this is, and you are with me.\r\n\r\n'
GRANDE = 'x' * (2 * 1024 * 1024 + 10)

# (vídeo, idioma) -> [(proveedor, id, texto, coincidencias)]
CATALOGO = {
    ('d_red_cast', 'spa'): [('addic7ed', 'lat1', LAT, set()),
                            ('opensubtitles', 'cast1', CAST, {'release_group'}),
                            ('gestdown', 'cast2', CAST2, set()),
                            ('subtitulamos', 'dup', CAST, set())],
    ('e_red_lat', 'spa'): [('opensubtitles', 'grande', GRANDE, set()),
                           ('addic7ed', 'lat2', LAT, set())],
    ('f_red_eng', 'eng'): [('gestdown', 'en1', ENG, set())],
    ('i_mejora', 'spa'): [('opensubtitles', 'cast5', CAST2, set())],
    ('z_pend', 'spa'): [('opensubtitles', 'cast9', CAST, set())],
}


class SubFalso(Subtitle):
    def __init__(self, proveedor, sid, texto, coincidencias, idioma):
        super().__init__(Language(idioma), sid, encoding='utf-8')
        self.provider_name = proveedor
        self._bytes = texto.encode('utf-8')
        self._coinc = coincidencias

    def get_matches(self, video):
        return set(self._coinc)


class PoolFalso:
    def __init__(self, providers=None, provider_configs=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def list_subtitles(self, video, languages):
        idioma = next(iter(languages)).alpha3
        return [SubFalso(p, i, t, c, idioma)
                for p, i, t, c in CATALOGO.get((Path(video.name).stem, idioma), [])]

    def download_subtitle(self, sub):
        sub.content = sub._bytes
        return True


# ---------- Carpeta de vídeos de prueba ----------

def _tam(n):
    return b'\x01' + n.to_bytes(7, 'big')


def _el(eid, datos):
    return eid.to_bytes((eid.bit_length() + 7) // 8, 'big') + _tam(len(datos)) + datos


def mkv(pistas):
    """MKV mínimo con pistas de texto: [(num, idioma, nombre, texto)]."""
    cab = _el(0x1A45DFA3, _el(0x4282, b'matroska'))
    tracks = b''.join(_el(0xAE, _el(0xD7, bytes([n])) + _el(0x86, b'S_TEXT/UTF8') + _el(0x22B59C, lang.encode())
                          + _el(0x536E, nombre.encode())) for n, lang, nombre, _ in pistas)
    bloques = b''.join(_el(0xA0, _el(0xA1, bytes([0x80 | n]) + b'\x00\x00\x00' + texto.encode())
                           + _el(0x9B, (2000).to_bytes(2, 'big'))) for n, _, _, texto in pistas)
    return cab + _el(0x18538067, _el(0x1654AE6B, tracks) + _el(0x1F43B675, _el(0xE7, b'\x00') + bloques))


FRASE_ES = 'Vale, tío, ¿qué hacéis vosotros aquí? Os lo dije.'
FRASE_LA = 'Ustedes no saben, ahorita vamos en el carro.'
FRASE_EN = 'You know what this is, and you are with me.'


def preparar(d):
    basura = b'\0' * 2048
    (d / 'a_ya.mkv').write_bytes(basura)
    (d / 'a_ya.srt').write_text(CAST, encoding='utf-8', newline='')
    (d / 'b_renombra.mp4').write_bytes(basura)
    (d / 'b_renombra.es.srt').write_text(CAST, encoding='utf-8', newline='')
    (d / 'c_incrustado.mkv').write_bytes(mkv([(1, 'spa', 'Español (España)', FRASE_ES),
                                              (2, 'eng', 'English SDH', FRASE_EN)]))
    for n in ('d_red_cast', 'e_red_lat', 'f_red_eng', 'g_nada', 'z_pend'):
        (d / f'{n}.avi').write_bytes(basura)
    (d / 'h_latino_previo.avi').write_bytes(basura)
    (d / 'h_latino_previo.srt').write_text(LAT, encoding='utf-8', newline='')
    (d / 'i_mejora.avi').write_bytes(basura)
    (d / 'i_mejora.srt').write_text(ENG, encoding='utf-8', newline='')
    (d / 'sub').mkdir()
    (d / 'sub' / 'k_lat_incrustado.mkv').write_bytes(mkv([(1, 'spa', 'Español (Latinoamérica)', FRASE_LA)]))
    (d / 'sample-x.avi').write_bytes(basura)


ESCENARIOS = {
    'S1': ['--max-videos', '7'],
    'S2': ['--dry-run', '--max-videos', '7'],
    'S3': ['--solo-castellano', '--sin-ingles', '--max-videos', '7'],
    'S4': ['--force', '--ingles', '--max-descargas', '2', '--max-videos', '0'],
    'S5': ['--force', '--dry-run', '--ingles'],
}


class ConSimulacion(unittest.TestCase):
    """Carpeta de vídeos nueva y proveedores simulados en cada prueba."""

    pausa = 0

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.videos = tmp / 'videos'
        self.videos.mkdir()
        preparar(self.videos)
        self.home = tmp / 'home'
        for nombre, valor in (('ProviderPool', PoolFalso),
                              ('scan_video', lambda p: Movie(p, Path(p).stem)),
                              ('refine', lambda *a, **k: None),
                              ('PAUSA', self.pausa),
                              ('HOME', self.home)):
            parche = mock.patch.object(nucleo, nombre, valor)
            parche.start()
            self.addCleanup(parche.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def arbol(self):
        return {str(p.relative_to(self.videos)): hashlib.sha256(p.read_bytes()).hexdigest()[:16]
                for p in sorted(self.videos.rglob('*')) if p.is_file()}

    def backups(self):
        carpeta = self.home / 'backup'
        return sorted(p.name.split('_', 1)[1] for p in carpeta.glob('*')) if carpeta.exists() else []


# ---------- Pruebas ----------

class CliIgualQueLaSkill(ConSimulacion):
    def test_misma_salida_y_mismos_archivos(self):
        for esc, args in ESCENARIOS.items():
            with self.subTest(esc):
                if esc != 'S1':
                    self.tearDown()
                    self.setUp()
                esperado = json.loads((ESPERADO / f'cli_{esc}.json').read_text(encoding='utf-8'))
                buf = io.BytesIO()
                salida = io.TextIOWrapper(buf, encoding='utf-8')
                with contextlib.redirect_stdout(salida):
                    bajar_subs.main([str(self.videos)] + args)
                salida.flush()
                self.assertEqual(buf.getvalue().decode('utf-8'), esperado['stdout'])
                self.assertEqual(self.arbol(), esperado['arbol'])
                self.assertEqual(self.backups(), esperado['backups'])


class Grabadora(nucleo.Eventos):
    def __init__(self, cancelar_tras=None):
        self.videos, self.progreso, self.lineas, self.resultados = None, [], [], []
        self.cancelar_tras = cancelar_tras

    def inicio(self, videos):
        self.videos = videos

    def video(self, indice, total, path):
        self.progreso.append((indice, total, path.name))

    def detalle(self, linea):
        self.lineas.append(linea)

    def resultado(self, resultado):
        self.resultados.append(resultado)

    def cancelado(self):
        return self.cancelar_tras is not None and len(self.resultados) >= self.cancelar_tras


class Eventos(ConSimulacion):
    def test_progreso_resultados_y_categorias(self):
        g = Grabadora()
        resumen = nucleo.procesar(self.videos, Opciones(max_videos=7), g, credenciales={})
        nombres = ['a_ya.mkv', 'b_renombra.mp4', 'c_incrustado.mkv', 'd_red_cast.avi', 'e_red_lat.avi',
                   'f_red_eng.avi', 'g_nada.avi', 'h_latino_previo.avi', 'i_mejora.avi',
                   'k_lat_incrustado.mkv', 'z_pend.avi']
        self.assertEqual([p.name for p in g.videos], nombres)        # sin 'sample-x.avi'
        self.assertEqual(g.progreso, [(i, 11, n) for i, n in enumerate(nombres, 1)])
        self.assertEqual(g.resultados, resumen)
        self.assertEqual([r.categoria for r in resumen], [
            nucleo.YA_CASTELLANO, nucleo.YA_CASTELLANO, nucleo.CASTELLANO, nucleo.CASTELLANO,
            nucleo.LATINO, nucleo.INGLES, nucleo.NO_ENCONTRADO, nucleo.SIN_CAMBIOS,
            nucleo.CASTELLANO, nucleo.LATINO, nucleo.PENDIENTE])
        self.assertEqual(resumen[3].estado, 'CASTELLANO')
        self.assertEqual(resumen[3].fuente, 'opensubtitles cast1')
        self.assertEqual(resumen[9].video, self.videos / 'sub' / 'k_lat_incrustado.mkv')
        self.assertIn('\n== d_red_cast.avi', g.lineas)

    def test_un_solo_video(self):
        g = Grabadora()
        resumen = nucleo.procesar(self.videos / 'c_incrustado.mkv', eventos=g, credenciales={})
        self.assertEqual([(r.nombre, r.estado) for r in resumen], [('c_incrustado.mkv', 'CASTELLANO (incrustado)')])
        self.assertEqual(g.progreso, [(1, 1, 'c_incrustado.mkv')])

    def test_se_puede_procesar_varias_veces(self):
        """La app procesa muchas carpetas en la misma sesión (la caché de subliminal se configura una vez)."""
        for _ in range(2):
            resumen = nucleo.procesar(self.videos, Opciones(dry_run=True), credenciales={})
            self.assertEqual(len(resumen), 11)

    def test_dry_run_no_escribe_nada(self):
        antes = self.arbol()
        nucleo.procesar(self.videos, Opciones(dry_run=True, force=True, ingles=True), credenciales={})
        self.assertEqual(self.arbol(), antes)
        self.assertEqual(self.backups(), [])


class Cancelar(ConSimulacion):
    def test_cancelar_entre_videos(self):
        g = Grabadora(cancelar_tras=3)
        resumen = nucleo.procesar(self.videos, eventos=g, cancelado=g.cancelado, credenciales={})
        self.assertEqual([r.nombre for r in resumen], ['a_ya.mkv', 'b_renombra.mp4', 'c_incrustado.mkv'])
        self.assertFalse((self.videos / 'd_red_cast.srt').exists())


class CancelarDuranteLaPausa(ConSimulacion):
    pausa = 30

    def test_la_pausa_entre_videos_se_interrumpe(self):
        g = Grabadora(cancelar_tras=4)      # tras el primer vídeo que busca en internet
        inicio = time.monotonic()
        resumen = nucleo.procesar(self.videos, eventos=g, cancelado=g.cancelado, credenciales={})
        self.assertLess(time.monotonic() - inicio, 5)
        self.assertEqual(resumen[-1].nombre, 'd_red_cast.avi')
        self.assertEqual(len(resumen), 4)


class OpcionesValidas(unittest.TestCase):
    def test_por_defecto_iguales_que_la_cli(self):
        o = Opciones()
        self.assertEqual((o.max_videos, o.max_descargas), (40, 5))
        self.assertFalse(any((o.force, o.solo_castellano, o.sin_ingles, o.ingles, o.dry_run)))

    def test_limites_no_validos(self):
        for campos in ({'max_videos': -1}, {'max_descargas': -3}, {'max_videos': '5'}, {'max_videos': True}):
            with self.subTest(campos), self.assertRaises(ValueError):
                Opciones(**campos)


class Arranque(unittest.TestCase):
    def ejecutar(self, *args):
        return subprocess.run([sys.executable, '-I', *args], capture_output=True, text=True,
                              encoding='utf-8', cwd=tempfile.gettempdir(), timeout=60)

    def test_modulos_ligeros_no_cargan_subliminal(self):
        """La app muestra la ventana antes de cargar subliminal: estos módulos no deben importarlo."""
        r = self.ejecutar('-c', f'import sys; sys.path.insert(0, {str(RAIZ)!r}); '
                                'import subtitulos.opciones, subtitulos.texto, subtitulos.pistas, subtitulos.eventos, subtitulos.archivos; '
                                'print(sorted(m for m in ("subliminal", "guessit", "babelfish") if m in sys.modules))')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), '[]')

    def test_cli_funciona_con_menos_i_desde_otra_carpeta(self):
        r = self.ejecutar(str(RAIZ / 'bajar_subs.py'), '--help')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('--max-descargas', r.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
