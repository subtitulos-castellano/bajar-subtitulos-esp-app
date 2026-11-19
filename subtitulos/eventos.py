"""Resultados y eventos de `procesar()`.

Solo usa la biblioteca estándar: la interfaz los usa sin cargar subliminal.
"""
from dataclasses import dataclass
from pathlib import Path

# Categoría de cada resultado (para dar color al resumen en la app).
CASTELLANO = 'castellano'        # CASTELLANO, CASTELLANO (incrustado)
YA_CASTELLANO = 'ya_castellano'  # ya tenía castellano
LATINO = 'latino'                # LATINO, LATINO (incrustado)
INGLES = 'ingles'                # INGLÉS, INGLÉS (incrustado)
SIN_CAMBIOS = 'sin_cambios'      # <TIPO> (ya tenía .srt): no se encontró nada mejor
PENDIENTE = 'pendiente'          # PENDIENTE (límite)
NO_ENCONTRADO = 'no_encontrado'  # NO ENCONTRADO


@dataclass(frozen=True)
class Resultado:
    """Una línea del resumen."""
    video: Path
    estado: str       # texto exacto del resumen de la CLI ('CASTELLANO (incrustado)', ...)
    fuente: str       # proveedor e id, pista incrustada o nota
    categoria: str    # una de las constantes de categoría de arriba

    @property
    def nombre(self):
        return self.video.name


class Eventos:
    """Recibe lo que pasa durante `procesar()`. Por defecto no hace nada: la CLI y la app
    sobrescriben los métodos que necesitan. Se llaman desde el hilo que ejecuta `procesar()`."""

    def inicio(self, videos):
        """Lista (de Path) de los vídeos que se van a revisar."""

    def video(self, indice, total, path):
        """Empieza un vídeo (`indice` va de 1 a `total`)."""

    def detalle(self, linea):
        """Línea informativa, con el mismo formato que imprime la CLI."""

    def resultado(self, resultado):
        """Un vídeo terminado (`Resultado`)."""
