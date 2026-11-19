"""Descarga subtítulos en castellano (español de España) para los vídeos de una carpeta.

Uso:
    python -I bajar_subs.py <carpeta_o_video> [--force] [--solo-castellano] [--sin-ingles]
                            [--ingles] [--dry-run] [--max-videos N] [--max-descargas N]

El subtítulo principal se guarda como <video>.srt (mismo nombre que el vídeo), para que
cualquier reproductor lo cargue solo. Orden de preferencia: castellano > latino > inglés.
Nunca se sustituye un .srt por otro de un tipo peor.

La lógica está en el paquete `subtitulos` (compartido con la app); este archivo solo lee
los parámetros e imprime el progreso y el resumen.

Credenciales de opensubtitles.org en %USERPROFILE%\\.subtitulos-esp\\credenciales.json:
    {"opensubtitles": {"username": "...", "password": "..."}}
"""
import argparse
import logging
import sys
from pathlib import Path

# Con -I, Python no añade la carpeta del script a sys.path: se añade a mano (solo esta
# carpeta, nunca la carpeta actual, que puede ser la de los vídeos).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from subtitulos import nucleo  # noqa: E402
from subtitulos.opciones import MAX_DESCARGAS, MAX_VIDEOS, Opciones  # noqa: E402
from subtitulos.texto import visible  # noqa: E402


class SalidaConsola(nucleo.Eventos):
    def detalle(self, linea):
        print(linea, flush=True)


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    aviso = logging.StreamHandler()
    aviso.setFormatter(logging.Formatter('  aviso (%(name)s): %(message)s'))
    aviso.addFilter(nucleo.SinRuido())
    logging.basicConfig(level=logging.WARNING, handlers=[aviso])
    ap = argparse.ArgumentParser()
    ap.add_argument('ruta', type=Path)
    ap.add_argument('--force', action='store_true',
                    help='rehacer aunque ya haya un .srt castellano (nunca se baja a un tipo peor)')
    ap.add_argument('--solo-castellano', action='store_true',
                    help='no guardar latino aunque no haya castellano (por defecto, si solo hay '
                         'latino, se guarda como .srt y el resumen lo marca como LATINO)')
    ap.add_argument('--sin-ingles', action='store_true',
                    help='no bajar inglés cuando no haya ningún subtítulo en español '
                         '(por defecto se guarda como .srt y el resumen lo marca como INGLÉS)')
    ap.add_argument('--dry-run', action='store_true', help='no escribir nada, solo mostrar qué haría')
    ap.add_argument('--ingles', action='store_true',
                    help='además, extraer la pista inglesa incrustada en el vídeo como .en.srt')
    ap.add_argument('--max-videos', type=int, default=MAX_VIDEOS, metavar='N',
                    help=f'máximo de vídeos que buscan en internet por ejecución (por defecto '
                         f'{MAX_VIDEOS}; 0 = sin límite). Los que ya tienen castellano o lo traen '
                         f'incrustado no cuentan. El resto queda como PENDIENTE (límite)')
    ap.add_argument('--max-descargas', type=int, default=MAX_DESCARGAS, metavar='N',
                    help=f'máximo de candidatos que se descargan por vídeo (por defecto '
                         f'{MAX_DESCARGAS}; 0 = sin límite), elegidos por sincronía y '
                         f'puntuación alternando proveedores')
    args = ap.parse_args(argv)
    for opcion in ('max_videos', 'max_descargas'):
        if getattr(args, opcion) < 0:
            ap.error(f"--{opcion.replace('_', '-')} debe ser 0 (sin límite) o un número positivo")
    ruta = args.ruta
    opciones = Opciones(**{k: v for k, v in vars(args).items() if k != 'ruta'})

    resumen = nucleo.procesar(ruta, opciones, SalidaConsola())

    print('\n==== RESUMEN ====')
    for r in resumen:
        print(f'{visible(r.estado):28} {visible(r.fuente):30} {visible(r.nombre)}')


if __name__ == '__main__':
    sys.exit(main())
