"""Pruebas de los modos «solo inglés» y «castellano traducido del inglés» (3.0.0): la traducción de un .srt
(subtitulos/traducir.py, con un traductor simulado), la descarga del modelo (subtitulos/modelo.py) y
procesar() en cada modo, con los proveedores simulados de test_nucleo.py.

Uso (con el Python del venv):
    python -I tests/test_traducir.py
"""
import hashlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from subtitulos import modelo, traducir  # noqa: E402
from subtitulos.opciones import Opciones  # noqa: E402
from subtitulos.texto import AVISO_TRADUCCION, idioma_srt  # noqa: E402


def eco(frases):
    """Traductor simulado: devuelve cada frase tal cual."""
    return list(frases)


def marcado(frases):
    """Traductor simulado: marca cada frase, para ver qué se le ha pedido."""
    return [f'[{f}]' for f in frases]


def textos(srt):
    """Las líneas de texto de cada bloque, sin el aviso del principio."""
    return [ls for _, _, ls in traducir.leer_srt(srt)][1:]


class LeerSrt(unittest.TestCase):
    def test_retorno_de_carro_doble_dentro_de_un_bloque(self):
        texto = '1\r\n00:00:01,000 --> 00:00:02,000\r\nHave you got another form\r\r\nof payment?\r\n\r\n'
        self.assertEqual(traducir.leer_srt(texto),
                         [('00:00:01,000', '00:00:02,000', ['Have you got another form', 'of payment?'])])

    def test_bloque_partido_por_una_linea_en_blanco(self):
        """Lo mismo leído convirtiendo los saltos de línea: queda una línea en blanco en medio."""
        texto = '1\n00:00:01,000 --> 00:00:02,000\nHave you got another form\n\nof payment?\n\n2\n00:00:03,000 --> 00:00:04,000\nNo.\n'
        self.assertEqual([ls for _, _, ls in traducir.leer_srt(texto)],
                         [['Have you got another form', 'of payment?'], ['No.']])

    def test_tiempos_con_punto_y_bom(self):
        texto = '﻿1\n00:00:01.500 --> 00:00:02.000\nHi\n'
        self.assertEqual(traducir.leer_srt(texto), [('00:00:01,500', '00:00:02,000', ['Hi'])])


class TraducirSrt(unittest.TestCase):
    def srt(self, *bloques):
        return ''.join(f'{n}\n{ini} --> {fin}\n' + '\n'.join(ls) + '\n\n'
                       for n, (ini, fin, ls) in enumerate(bloques, 1))

    def test_aviso_al_principio_y_mismos_tiempos(self):
        entrada = self.srt(('00:00:06,180', '00:00:09,357', ['Where is my phone?']),
                           ('00:00:10,000', '00:00:11,000', ['Here.']))
        salida = traducir.traducir_srt(entrada, eco)
        bloques = traducir.leer_srt(salida)
        self.assertEqual(bloques[0], ('00:00:00,000', '00:00:04,000', [AVISO_TRADUCCION]))
        self.assertEqual([(a, b) for a, b, _ in bloques[1:]],
                         [('00:00:06,180', '00:00:09,357'), ('00:00:10,000', '00:00:11,000')])
        self.assertEqual(idioma_srt(salida), 'traducido')
        # Si el primer bloque empieza antes de 4 s, el aviso acaba justo antes.
        bloques = traducir.leer_srt(traducir.traducir_srt(self.srt(('00:00:01,000', '00:00:02,000', ['Hi.'])), eco))
        self.assertEqual(bloques[0][:2], ('00:00:00,000', '00:00:00,950'))

    def test_quita_anotaciones_para_sordos(self):
        entrada = self.srt(('00:00:01,000', '00:00:02,000', ['[phone buzzing]']),
                           ('00:00:03,000', '00:00:04,000', ['["Sick Beat" by Kero Kero', 'playing on speakers]']),
                           ('00:00:05,000', '00:00:06,000', ['[Conrad] Oh, this is not', 'happening.']),
                           ('00:00:07,000', '00:00:08,000', ['MAEVE: Go home.']),
                           ('00:00:09,000', '00:00:10,000', ['- [beeps]', '- Declined again.']))
        self.assertEqual(textos(traducir.traducir_srt(entrada, marcado)),
                         [['[Oh, this is not happening.]'], ['[Go home.]'], ['[Declined again.]']])

    def test_dialogo_cursiva_y_musica(self):
        entrada = self.srt(('00:00:01,000', '00:00:02,000', ['- Are you coming?', '- In a minute.']),
                           ('00:00:03,000', '00:00:04,000', ['<i>As of tonight,</i>']),
                           ('00:00:05,000', '00:00:06,000', ['♪ You can run on ♪']))
        self.assertEqual(textos(traducir.traducir_srt(entrada, marcado)),
                         [['- [Are you coming?]', '- [In a minute.]'], ['<i>[As of tonight,]</i>'],
                          ['♪ [You can run on]']])

    def test_frase_partida_entre_bloques(self):
        """Se traduce entera y se reparte; si el bloque acaba en coma, cada uno por separado."""
        entrada = self.srt(('00:00:01,000', '00:00:02,000', ['I think that']),
                           ('00:00:02,100', '00:00:03,000', ['we should go.']),
                           ('00:00:04,000', '00:00:05,000', ['So, Eddie,']),
                           ('00:00:05,100', '00:00:06,000', ['you are right.']))
        pedidas = []
        salida = traducir.traducir_srt(entrada, lambda fs: pedidas.extend(fs) or list(fs))
        self.assertIn('I think that we should go.', pedidas)
        self.assertIn('So, Eddie,', pedidas)
        self.assertEqual(textos(salida), [['I think that'], ['we should go.'], ['So, Eddie,'], ['you are right.']])

    def test_cada_frase_por_separado_y_frases_hechas(self):
        entrada = self.srt(('00:00:01,000', '00:00:02,000', ['Okay. Where is my computer?', 'Right?']))
        pedidas = []
        salida = traducir.traducir_srt(entrada, lambda fs: pedidas.extend(fs) or ['¿Dónde está mi computadora?'] * len(fs))
        self.assertEqual(pedidas, ['Where is my computer?'])          # «Okay.» y «Right?» no van al modelo
        self.assertEqual(textos(salida), [['Vale. ¿Dónde está mi ordenador? ¿Vale?']])
        largo = traducir.traducir_srt(self.srt(('00:00:01,000', '00:00:02,000', ['x'])), lambda fs: ['a' * 30 + ' ' + 'b' * 30])
        self.assertEqual(textos(largo), [['a' * 30, 'b' * 30]])                    # en dos líneas

    def test_palabras_de_espana(self):
        self.assertEqual(traducir.a_espana('Mi Computadora y mi celular. ¡CELULAR!'),
                         'Mi Ordenador y mi móvil. ¡MÓVIL!')
        self.assertEqual(traducir.a_espana('Autopista'), 'Autopista')

    def test_repartir(self):
        self.assertEqual(traducir.repartir('uno dos tres cuatro', [1, 1]), ['uno dos', 'tres cuatro'])
        self.assertEqual(traducir.repartir('uno dos, tres cuatro cinco', [3, 1]), ['uno dos,', 'tres cuatro cinco'])
        self.assertEqual(traducir.repartir('uno, dos tres cuatro cinco', [3, 1]), ['uno, dos tres cuatro', 'cinco'])
        self.assertEqual(traducir.repartir('uno', [1, 1]), ['uno', ''])


class Modelo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = Path(self._tmp.name)

    def zip(self, nombres):
        ruta = self.d / 'modelo.zip'
        with zipfile.ZipFile(ruta, 'w') as z:
            for n in nombres:
                z.writestr(n, f'contenido de {n}')
            z.writestr('../fuera.txt', 'no se saca')
        return ruta.as_uri(), hashlib.sha256(ruta.read_bytes()).hexdigest()

    def test_descarga_comprobada(self):
        url, sha = self.zip(modelo.ARCHIVOS)
        destino = self.d / 'modelos' / 'traductor'
        avances = []
        self.assertEqual(modelo.descargar(lambda h, t: avances.append(h), url=url, sha256=sha, destino=destino), destino)
        self.assertTrue(modelo.instalado(destino))
        self.assertTrue(avances)
        self.assertEqual(sorted(p.name for p in destino.iterdir()), sorted(modelo.ARCHIVOS + ('.completo',)))
        self.assertFalse((self.d / 'modelos' / 'fuera.txt').exists())
        self.assertEqual(sorted(p.name for p in destino.parent.iterdir()), ['traductor'])   # sin restos

    def test_huella_que_no_coincide(self):
        url, _ = self.zip(modelo.ARCHIVOS)
        destino = self.d / 'm'
        with self.assertRaises(modelo.ErrorModelo):
            modelo.descargar(url=url, sha256='0' * 64, destino=destino)
        self.assertFalse(destino.exists())
        self.assertEqual(list(self.d.glob('.m*')), [])

    def test_zip_incompleto(self):
        url, sha = self.zip(modelo.ARCHIVOS[:-1])
        with self.assertRaises(modelo.ErrorModelo):
            modelo.descargar(url=url, sha256=sha, destino=self.d / 'm')
        self.assertFalse(modelo.instalado(self.d / 'm'))

    def test_sin_modelo_no_hay_motor(self):
        with self.assertRaises(modelo.ErrorModelo):
            modelo.motor(self.d / 'no-existe')

    @unittest.skipIf(modelo.SHA256 == 'PENDIENTE', 'el traductor aún no está publicado (el workflow de la '
                                                   'versión no deja publicar sin él)')
    def test_el_publicado_tiene_huella(self):
        self.assertRegex(modelo.SHA256, r'^[0-9a-f]{64}$')
        self.assertGreater(modelo.TAMANO, 50_000_000)
        self.assertTrue(modelo.URL.startswith(
            'https://github.com/subtitulos-castellano/bajar-subtitulos-esp-app/releases/download/'))


class OpcionesDelModo(unittest.TestCase):
    def test_modos(self):
        self.assertEqual(Opciones().modo, 'castellano')
        for modo in ('castellano', 'ingles', 'traducido'):
            self.assertEqual(Opciones(modo=modo).modo, modo)
        with self.assertRaises(ValueError):
            Opciones(modo='latino')

    def test_cli(self):
        import bajar_subs
        with mock.patch.object(bajar_subs.nucleo, 'procesar', return_value=[]) as procesar:
            bajar_subs.main(['x', '--solo-ingles'])
        self.assertEqual(procesar.call_args.args[1].modo, 'ingles')
        with mock.patch('sys.stderr'), self.assertRaises(SystemExit):
            bajar_subs.main(['x', '--solo-ingles', '--traducir'])


try:
    import test_nucleo
    from test_nucleo import CATALOGO, ENG, Grabadora, nucleo
except ImportError:                 # sin subliminal (solo las pruebas de arriba)
    test_nucleo = None


@unittest.skipIf(test_nucleo is None, 'sin subliminal')
class ModoIngles(test_nucleo.ConSimulacion if test_nucleo else unittest.TestCase):
    def estados(self, resumen):
        return {r.nombre: (r.estado, r.categoria) for r in resumen}

    def test_solo_ingles(self):
        (self.videos / 'd_red_cast.en.srt').write_text(ENG, encoding='utf-8', newline='')
        with mock.patch.dict(CATALOGO, {('a_ya', 'eng'): [('gestdown', 'en9', ENG, set())]}):
            resumen = nucleo.procesar(self.videos, Opciones(modo='ingles', max_videos=0), Grabadora(),
                                      credenciales={})
        e = self.estados(resumen)
        self.assertEqual(e['a_ya.mkv'], ('INGLÉS', 'solo_ingles'))                 # sustituye el castellano
        self.assertEqual(e['c_incrustado.mkv'], ('INGLÉS (incrustado)', 'solo_ingles'))
        self.assertEqual(e['d_red_cast.avi'], ('INGLÉS (de .en.srt)', 'solo_ingles'))
        self.assertEqual(e['f_red_eng.avi'], ('INGLÉS', 'solo_ingles'))
        self.assertEqual(e['i_mejora.avi'], ('ya tenía inglés', 'ya_ingles'))
        self.assertEqual(e['g_nada.avi'], ('NO ENCONTRADO', 'no_encontrado'))
        for v in ('a_ya', 'c_incrustado', 'd_red_cast', 'f_red_eng'):
            self.assertEqual(idioma_srt((self.videos / f'{v}.srt').read_text(encoding='utf-8')), 'ingles', v)
        self.assertIn('a_ya.srt', self.backups())                                   # copia del castellano
        self.assertNotIn('latino', {c for _, c in e.values()})

    def test_rehacer_y_simulacion(self):
        resumen = nucleo.procesar(self.videos / 'i_mejora.avi', Opciones(modo='ingles', force=True, dry_run=True),
                                  credenciales={})
        self.assertEqual(resumen[0].estado, 'NO ENCONTRADO')        # vuelve a buscar (y no hay nada)
        self.assertEqual((self.videos / 'i_mejora.srt').read_bytes(), ENG.encode())


@unittest.skipIf(test_nucleo is None, 'sin subliminal')
class ModoTraducido(test_nucleo.ConSimulacion if test_nucleo else unittest.TestCase):
    def procesar(self, ruta, **opciones):
        return {r.nombre: (r.estado, r.categoria)
                for r in nucleo.procesar(ruta, Opciones(max_videos=0, **opciones), Grabadora(), credenciales={},
                                         traductor=marcado)}

    def test_traduce_y_guarda_el_ingles(self):
        e = self.procesar(self.videos, modo='traducido')
        self.assertEqual(e['f_red_eng.avi'], ('TRADUCIDO', 'traducido'))
        self.assertEqual(e['c_incrustado.mkv'], ('TRADUCIDO (incrustado)', 'traducido'))
        self.assertEqual(e['i_mejora.avi'], ('TRADUCIDO (de su .srt)', 'traducido'))
        self.assertEqual(e['g_nada.avi'], ('NO ENCONTRADO', 'no_encontrado'))
        srt = (self.videos / 'f_red_eng.srt').read_text(encoding='utf-8')
        self.assertEqual(idioma_srt(srt), 'traducido')
        self.assertIn('[You know what this is, and you are with me.]', srt.replace(',\n', ', '))
        for v in ('f_red_eng', 'i_mejora'):
            self.assertEqual((self.videos / f'{v}.en.srt').read_text(encoding='utf-8'), ENG.replace('\r\n', '\n'), v)
        self.assertIn('i_mejora.srt', self.backups())
        # Otra vez: ya están.
        e = self.procesar(self.videos, modo='traducido')
        self.assertEqual(e['f_red_eng.avi'], ('ya tenía traducido', 'ya_traducido'))
        # En el modo castellano, una traducción se cambia por castellano o latino, pero no por inglés.
        e = self.procesar(self.videos, modo='castellano')
        self.assertEqual(e['i_mejora.avi'], ('CASTELLANO', 'castellano'))
        self.assertEqual(e['f_red_eng.avi'], ('TRADUCIDO (ya tenía .srt)', 'sin_cambios'))

    def test_sin_traductor_descargado(self):
        with mock.patch.object(modelo, 'carpeta', return_value=Path(self.home) / 'no-existe'), \
                self.assertRaises(modelo.ErrorModelo):
            nucleo.procesar(self.videos, Opciones(modo='traducido'), credenciales={})


if __name__ == '__main__':
    unittest.main(verbosity=2)
