"""Preferencias de una ejecución. Cada campo equivale a un parámetro de la línea de comandos.

Solo usa la biblioteca estándar: la app puede leerlas y guardarlas sin cargar subliminal.
"""
from dataclasses import dataclass

# Límites para no saturar a los proveedores con búsquedas masivas.
MAX_VIDEOS = 40     # vídeos que buscan en internet por ejecución (0 = sin límite)
MAX_DESCARGAS = 5   # candidatos que se descargan por vídeo (0 = sin límite)

# Qué subtítulo se busca:
# - 'castellano': castellano de España; si no hay, latino y, si tampoco, inglés (según las opciones).
# - 'ingles': solo inglés (--solo-ingles).
# - 'traducido': inglés traducido automáticamente al castellano, sin conexión (--traducir).
MODOS = ('castellano', 'ingles', 'traducido')


@dataclass
class Opciones:
    force: bool = False             # --force: rehacer aunque ya haya castellano
    solo_castellano: bool = False   # --solo-castellano: no guardar latino
    sin_ingles: bool = False        # --sin-ingles: no bajar inglés si no hay español
    ingles: bool = False            # --ingles: extraer además la pista inglesa incrustada (.en.srt)
    dry_run: bool = False           # --dry-run: no escribir nada
    max_videos: int = MAX_VIDEOS    # --max-videos N
    max_descargas: int = MAX_DESCARGAS  # --max-descargas N
    modo: str = 'castellano'        # --solo-ingles / --traducir (ver MODOS)

    def __post_init__(self):
        for campo in ('max_videos', 'max_descargas'):
            valor = getattr(self, campo)
            if not isinstance(valor, int) or isinstance(valor, bool) or valor < 0:
                raise ValueError(f'{campo} debe ser 0 (sin límite) o un número positivo')
        if self.modo not in MODOS:
            raise ValueError(f'modo debe ser uno de {", ".join(MODOS)}')
