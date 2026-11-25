"""Prepara el traductor inglés → español que la app descarga la primera vez que traduce (subtitulos/modelo.py).
Lo ejecuta el workflow .github/workflows/traductor.yml, que lo publica en la Release `traductor-en-es-1`:

    python3 -I packaging/traductor.py CARPETA

Pasos:
1. Convierte el modelo Opus-MT «Helsinki-NLP/opus-mt-tc-big-en-es» (revisión fijada en REVISION) a
   CTranslate2, cuantizado a int8 (ocupa unos 230 MB y traduce un episodio en segundos sin tarjeta gráfica).
2. Añade sus vocabularios (source.spm y target.spm), la licencia y un LEEME con la procedencia.
3. Comprueba que traduce.
4. Lo comprime en CARPETA/<NOMBRE>.zip con fechas fijas (mismo contenido, mismo .zip).

Necesita ctranslate2, sentencepiece, transformers y torch (solo para convertirlo; la app no los usa).
"""
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from subtitulos import modelo  # noqa: E402

ORIGEN = 'Helsinki-NLP/opus-mt-tc-big-en-es'
REVISION = '8f4d4924189681076e9c642b2fd85278d793fd4d'      # 2023-10-10

LICENCIA = f"""Opus-MT: {ORIGEN}
https://huggingface.co/{ORIGEN} (revision {REVISION})

Copyright (c) Language Technology Research Group at the University of Helsinki (Helsinki-NLP), OPUS-MT project.
Licensed under the Creative Commons Attribution 4.0 International license (CC BY 4.0):
https://creativecommons.org/licenses/by/4.0/

Modifications: converted to the CTranslate2 format with int8 quantization for Bajar Subtítulos ESP
(https://github.com/subtitulos-castellano/bajar-subtitulos-esp-app). See LEEME.txt.

Reference: Jörg Tiedemann and Santhosh Thottingal. 2020. OPUS-MT - Building open translation services for
the World. In Proceedings of the 22nd Annual Conference of the European Association for Machine Translation
(EAMT), Lisbon, Portugal.
"""

LEEME = f"""Traductor de inglés a español de Bajar Subtítulos ESP ({modelo.NOMBRE})
=====================================================================

Lo descarga la app la primera vez que traduce un subtítulo (Configuración > Idioma de los subtítulos >
Castellano traducido automáticamente del inglés) y lo usa sin conexión: nada sale del ordenador.

Es el modelo Opus-MT {ORIGEN} (Universidad de Helsinki, licencia CC BY 4.0, ver LICENSE.txt),
revisión {REVISION}, convertido a CTranslate2 y cuantizado a int8 con:

    ct2-transformers-converter --model {ORIGEN} --revision {REVISION} --quantization int8

Lo prepara y lo publica el workflow .github/workflows/traductor.yml del repositorio, con su suma SHA-256
y su atestación de procedencia.

Para borrarlo: Configuración > Borrar, o borra esta carpeta.
"""


def convertir(salida):
    subprocess.run(['ct2-transformers-converter', '--model', ORIGEN, '--revision', REVISION, '--output_dir',
                    str(salida), '--quantization', 'int8', '--copy_files', 'source.spm', 'target.spm'],
                   check=True)
    (salida / 'LICENSE.txt').write_text(LICENCIA, encoding='utf-8', newline='\n')
    (salida / 'LEEME.txt').write_text(LEEME, encoding='utf-8', newline='\n')


def probar(carpeta):
    from subtitulos.traducir import Motor
    frases = ['Where is my phone? I left it on the desk.', 'Thank you so much.']
    traducidas = Motor(carpeta)(frases)
    print('\n'.join(f'{a} -> {b}' for a, b in zip(frases, traducidas)))
    if 'teléfono' not in traducidas[0].lower() or 'gracias' not in traducidas[1].lower():
        raise SystemExit('El traductor no traduce bien: no se publica.')


def comprimir(carpeta, destino):
    with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for nombre in sorted(modelo.ARCHIVOS):
            info = zipfile.ZipInfo(nombre, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(carpeta / nombre, 'rb') as origen, z.open(info, 'w') as salida:
                while bloque := origen.read(1024 * 1024):
                    salida.write(bloque)


def main(argv):
    destino = Path(argv[0])
    destino.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        carpeta = Path(d) / modelo.NOMBRE
        convertir(carpeta)
        faltan = [a for a in modelo.ARCHIVOS if not (carpeta / a).is_file()]
        if faltan:
            raise SystemExit(f'Faltan {faltan}')
        probar(carpeta)
        archivo = destino / f'{modelo.NOMBRE}.zip'
        comprimir(carpeta, archivo)
    print(f'{archivo}: {archivo.stat().st_size} bytes')


if __name__ == '__main__':
    main(sys.argv[1:])
