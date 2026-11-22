"""Pruebas de seguridad del núcleo (paquete subtitulos) con vídeos y textos construidos a mano.

Comprueban que los vídeos válidos se siguen leyendo igual y que los corruptos o manipulados
terminan enseguida con ArchivoInvalido, sin colgarse ni agotar la memoria.

Uso (con el Python del venv de la skill):
    python -I tests/test_seguridad.py
"""
import struct
import sys
import tempfile
import threading
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from subtitulos import nucleo, texto  # noqa: E402
from subtitulos import pistas as pt  # noqa: E402

LIMITE_SEGUNDOS = 10
TEXTO = 'Vale, tío, ¿qué hacéis vosotros aquí?'


# ---------- Construcción de archivos ----------

def _tam_ebml(n):
    return b'\x01' + n.to_bytes(7, 'big')        # tamaño EBML de 8 bytes


def _el(eid, datos):
    return eid.to_bytes((eid.bit_length() + 7) // 8, 'big') + _tam_ebml(len(datos)) + datos


def _cabecera_ebml():
    return _el(0x1A45DFA3, _el(0x4282, b'matroska'))


def mkv_valido():
    pista = _el(0xAE, _el(0xD7, b'\x01') + _el(0x86, b'S_TEXT/UTF8') + _el(0x22B59C, b'spa')
                + _el(0x536E, 'Español (España)'.encode()))
    bloque = b'\x81\x00\x00\x00' + TEXTO.encode()   # pista 1, tiempo 0, sin flags
    cluster = _el(0x1F43B675, _el(0xE7, b'\x00')
                  + _el(0xA0, _el(0xA1, bloque) + _el(0x9B, (2000).to_bytes(2, 'big'))))
    return _cabecera_ebml() + _el(0x18538067, _el(0x1654AE6B, pista) + cluster)


def mkv_cortado():
    """La cabecera de pistas declara más datos de los que hay: antes, bucle infinito."""
    return (_cabecera_ebml() + b'\x18\x53\x80\x67' + _tam_ebml(10 ** 6)
            + b'\x16\x54\xAE\x6B' + _tam_ebml(1000) + b'\xAE' + _tam_ebml(500)
            + b'\x86' + _tam_ebml(10) + b'S_T')


def mkv_bloque_cero():
    """Un bloque que empieza por 0x00 (p. ej. trozo sin descargar): antes, bucle infinito."""
    cluster = _el(0x1F43B675, _el(0xE7, b'\x00') + _el(0xA3, b'\x00' * 5))
    return _cabecera_ebml() + _el(0x18538067, cluster)


def mkv_largo(n_bloques=5000):
    """Una pista de vídeo (2) con muchos bloques y, al final, el subtítulo (1)."""
    pistas = (_el(0xAE, _el(0xD7, b'\x01') + _el(0x86, b'S_TEXT/UTF8') + _el(0x22B59C, b'spa'))
              + _el(0xAE, _el(0xD7, b'\x02') + _el(0x86, b'V_MPEG4/ISO/AVC')))
    video = b''.join(_el(0xA3, b'\x82\x00\x00\x00' + b'\xAA' * 50) for _ in range(n_bloques))
    sub = _el(0xA0, _el(0xA1, b'\x81\x00\x00\x00' + TEXTO.encode()) + _el(0x9B, (2000).to_bytes(2, 'big')))
    cluster = _el(0x1F43B675, _el(0xE7, b'\x00') + video + sub)
    return _cabecera_ebml() + _el(0x18538067, _el(0x1654AE6B, pistas) + cluster)


def _caja(tipo, datos):
    return struct.pack('>I4s', 8 + len(datos), tipo) + datos


def mp4(tam_fijo=0, n_muestras=1, por_trozo=1):
    muestra = struct.pack('>H', len(TEXTO.encode())) + TEXTO.encode()
    mdat = _caja(b'mdat', muestra)
    lang = sum((ord(c) - 0x60) << s for c, s in zip('spa', (10, 5, 0)))
    tkhd = _caja(b'tkhd', b'\0' * 12 + struct.pack('>I', 1) + b'\0' * 68)
    mdhd = _caja(b'mdhd', b'\0' * 12 + struct.pack('>II', 1000, 2000) + struct.pack('>H', lang) + b'\0' * 2)
    hdlr = _caja(b'hdlr', b'\0' * 8 + b'sbtl' + b'\0' * 13)
    stsd = _caja(b'stsd', b'\0' * 4 + struct.pack('>I', 1) + struct.pack('>I4s', 16, b'tx3g') + b'\0' * 8)
    stts = _caja(b'stts', b'\0' * 4 + struct.pack('>III', 1, 1, 2000))
    stsc = _caja(b'stsc', b'\0' * 4 + struct.pack('>IIII', 1, 1, por_trozo, 1))
    if tam_fijo:
        stsz = _caja(b'stsz', b'\0' * 4 + struct.pack('>II', tam_fijo, n_muestras))
    else:
        stsz = _caja(b'stsz', b'\0' * 4 + struct.pack('>III', 0, 1, len(muestra)))
    stco = _caja(b'stco', b'\0' * 4 + struct.pack('>II', 1, 8))     # la muestra va tras la cabecera de mdat
    stbl = _caja(b'stbl', stsd + stts + stsc + stsz + stco)
    trak = _caja(b'trak', tkhd + _caja(b'mdia', mdhd + hdlr + _caja(b'minf', stbl)))
    mvhd = _caja(b'mvhd', b'\0' * 12 + struct.pack('>I', 1000) + b'\0' * 84)
    return mdat + _caja(b'moov', mvhd + trak)


def mp4_moov_enorme():
    """El índice declara 256 MB: antes se intentaba leer entero en memoria."""
    return struct.pack('>I4s', 256 * 1024 * 1024, b'moov') + b'\0' * 64


class RelojFalso:
    """Cada consulta avanza `paso` segundos."""

    def __init__(self, paso):
        self.t, self.paso = 0.0, paso

    def __call__(self):
        self.t += self.paso
        return self.t


# ---------- Ayudas ----------

def sin_colgarse(prueba, funcion, *args):
    """Ejecuta la función en un hilo y falla si no termina a tiempo. Devuelve (resultado, error)."""
    salida = {}

    def ejecutar():
        try:
            salida['resultado'] = funcion(*args)
        except Exception as e:  # noqa: BLE001 - la prueba decide qué error esperaba
            salida['error'] = e

    hilo = threading.Thread(target=ejecutar, daemon=True)
    hilo.start()
    hilo.join(LIMITE_SEGUNDOS)
    prueba.assertFalse(hilo.is_alive(), f'{funcion.__name__} no terminó en {LIMITE_SEGUNDOS} s')
    return salida.get('resultado'), salida.get('error')


class ConArchivos(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.dir = Path(self._dir.name)

    def tearDown(self):
        self._dir.cleanup()

    def archivo(self, nombre, datos):
        ruta = self.dir / nombre
        ruta.write_bytes(datos)
        return ruta


# ---------- Pruebas ----------

class VideosValidos(ConArchivos):
    def test_mkv_valido_sigue_funcionando(self):
        ruta = self.archivo('valido.mkv', mkv_valido())
        pistas = pt.pistas_texto(ruta)
        self.assertEqual([(p['num'], p['lang'], p['name']) for p in pistas], [(1, 'spa', 'Español (España)')])
        srt = pt.extraer_srt(ruta, [1])[1]
        self.assertIn('00:00:00,000 --> 00:00:02,000', srt)
        self.assertIn(TEXTO, srt)
        res, error = sin_colgarse(self, pt.incrustado, ruta)
        self.assertIsNone(error)
        self.assertIsNotNone(res['castellano'])

    def test_mp4_valido_sigue_funcionando(self):
        ruta = self.archivo('valido.mp4', mp4())
        pistas = pt.pistas_texto(ruta)
        self.assertEqual([(p['num'], p['lang'], p['codec']) for p in pistas], [(1, 'spa', 'tx3g')])
        srt = pt.extraer_srt(ruta, [1])[1]
        self.assertIn('00:00:00,000 --> 00:00:02,000', srt)
        self.assertIn(TEXTO, srt)


class VideosManipulados(ConArchivos):
    def test_mkv_cortado_no_se_cuelga(self):
        ruta = self.archivo('cortado.mkv', mkv_cortado())
        _, error = sin_colgarse(self, pt.pistas_mkv, ruta)
        self.assertIsInstance(error, pt.ArchivoInvalido)

    def test_mkv_bloque_cero_no_se_cuelga(self):
        ruta = self.archivo('cero.mkv', mkv_bloque_cero())
        _, error = sin_colgarse(self, pt.extraer_srt_mkv, ruta, [1])
        self.assertIsInstance(error, pt.ArchivoInvalido)

    def test_vint_b_byte_cero(self):
        _, error = sin_colgarse(self, pt._vint_b, b'\x00' * 9, 0)
        self.assertIsInstance(error, pt.ArchivoInvalido)

    def test_mp4_con_miles_de_millones_de_muestras(self):
        ruta = self.archivo('muestras.mp4', mp4(tam_fijo=4, n_muestras=0xFFFFFFFF))
        _, error = sin_colgarse(self, pt.pistas_mp4, ruta)
        self.assertIsInstance(error, pt.ArchivoInvalido)

    def test_mp4_moov_enorme(self):
        ruta = self.archivo('moov.mp4', mp4_moov_enorme())
        _, error = sin_colgarse(self, pt.pistas_mp4, ruta)
        self.assertIsInstance(error, pt.ArchivoInvalido)

    def test_incrustado_devuelve_vacio_sin_error(self):
        for nombre, datos in (('a.mkv', mkv_cortado()), ('pistas.mkv', mkv_bloque_cero()),
                              ('c.mp4', mp4(tam_fijo=4, n_muestras=0xFFFFFFFF)), ('d.mp4', mp4_moov_enorme())):
            with self.subTest(nombre):
                res, error = sin_colgarse(self, pt.incrustado, self.archivo(nombre, datos))
                self.assertIsNone(error)
                self.assertEqual(res, {'castellano': None, 'latino': None, 'ingles': None, 'lento': False})


class TextosDeTerceros(ConArchivos):
    def test_limpiar_texto_quita_controles_y_conserva_saltos(self):
        sucio = 'Hola\x1b[31m‮mundo\x00\x9b​.\r\nAdiós\t!'
        self.assertEqual(texto.limpiar_texto(sucio), 'Hola[31mmundo.\r\nAdiós\t!')

    def test_visible_es_una_sola_linea(self):
        self.assertEqual(texto.visible('pista\nCASTELLANO falso\x1b'), 'pista CASTELLANO falso ')

    def test_guardar_limpia_el_texto(self):
        destino = self.dir / 'video.srt'
        nucleo.guardar('1\r\n00:00:01,000 --> 00:00:02,000\r\nHola\x1b]0;titulo\x07\r\n', destino)
        self.assertEqual(destino.read_bytes().decode('utf-8'),
                         '1\r\n00:00:01,000 --> 00:00:02,000\r\nHola]0;titulo\r\n')


class VideoLento(unittest.TestCase):
    """Si extraer la pista incrustada va a tardar más del límite, se deja (y se dice por qué)."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def escribir(self, nombre, datos):
        ruta = Path(self.dir.name) / nombre
        ruta.write_bytes(datos)
        return ruta

    def test_lectura_rapida_extrae_igual(self):
        ruta = self.escribir('rapido.mkv', mkv_largo())
        srt = pt.extraer_srt(ruta, [1], pt.Plazo(reloj=RelojFalso(0.0001)))[1]
        self.assertIn(TEXTO, srt)

    def test_lectura_lenta_se_corta_con_la_estimacion(self):
        ruta = self.escribir('lento.mkv', mkv_largo())
        with self.assertRaises(pt.Lento) as e:
            pt.extraer_srt(ruta, [1], pt.Plazo(reloj=RelojFalso(1.0)))
        self.assertGreater(e.exception.segundos, pt.LIMITE_EXTRACCION)

    def test_mp4_lento_se_corta(self):
        ruta = self.escribir('lento.mp4', mp4(tam_fijo=3, n_muestras=5000, por_trozo=5000))
        with self.assertRaises(pt.Lento):
            pt.extraer_srt(ruta, [1], pt.Plazo(reloj=RelojFalso(1.0)))

    def test_incrustado_avisa_en_el_detalle(self):
        ruta = self.escribir('Serie.S01E01.mkv', mkv_largo())
        lineas = []
        with unittest.mock.patch.object(pt, 'MUESTRA_EXTRACCION', 0):
            res = pt.incrustado(ruta, detalle=lineas.append, limite=0)
        self.assertTrue(res['lento'])
        self.assertIsNone(res['castellano'])
        self.assertTrue(any('no se han extraído los subtítulos incrustados del propio vídeo porque leerlo '
                            'era muy lento' in l for l in lineas), lineas)

    def test_incrustado_sin_prisa(self):
        res = pt.incrustado(self.escribir('Serie.S01E02.mkv', mkv_largo()))
        self.assertFalse(res['lento'])
        self.assertIn(TEXTO, res['castellano'][0])

    def test_ingles_lento(self):
        datos = mkv_largo().replace(b'spa', b'eng')
        lineas = []
        with unittest.mock.patch.object(pt, 'MUESTRA_EXTRACCION', 0):
            texto, _ = pt.ingles_incrustado(self.escribir('Serie.S01E03.mkv', datos), lineas.append, limite=0)
        self.assertIsNone(texto)
        self.assertIn('subtítulos en inglés', lineas[0])

    def test_duracion_legible(self):
        self.assertEqual(pt.aviso_lento(pt.Lento(40)).split('tardaría ')[1].split(';')[0], 'unos 40 s')
        self.assertIn('unos 3 min', pt.aviso_lento(pt.Lento(185)))
        self.assertIn('más de 15 s', pt.aviso_lento(pt.Lento(None)))


if __name__ == '__main__':
    unittest.main(verbosity=2)
