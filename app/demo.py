"""Trabajador de DEMOSTRACIÓN para el prototipo (Fase 2): no busca ni descarga nada.

Emite las mismas señales que tendrá el trabajador real (Fase 3), con resultados inventados
sobre los nombres reales de los vídeos soltados, para probar la interfaz y el arrastre.
"""
import hashlib
import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from subtitulos import eventos as ev
from subtitulos.archivos import buscar_videos
from subtitulos.eventos import Resultado

_EJEMPLOS = [
    (ev.CASTELLANO, 'CASTELLANO', 'addic7ed updated/5/6159/8'),
    (ev.CASTELLANO, 'CASTELLANO (incrustado)', 'pista 3 Español (España)'),
    (ev.CASTELLANO, 'CASTELLANO', 'opensubtitles 1955123087'),
    (ev.YA_CASTELLANO, 'ya tenía castellano', '-'),
    (ev.YA_CASTELLANO, 'ya tenía castellano', 'renombrado desde .es.srt'),
    (ev.CASTELLANO, 'CASTELLANO', 'subtitulamos 4821'),
    (ev.LATINO, 'LATINO', 'opensubtitles 1955120044'),
    (ev.YA_CASTELLANO, 'ya tenía castellano', '-'),
    (ev.CASTELLANO, 'CASTELLANO', 'gestdown 7f3a91c2'),
    (ev.INGLES, 'INGLÉS (incrustado)', 'pista 2 English SDH'),
    (ev.CASTELLANO, 'CASTELLANO (incrustado)', 'pista 4 Español (Castellano)'),
    (ev.SIN_CAMBIOS, 'LATINO (ya tenía .srt)', '-'),
    (ev.NO_ENCONTRADO, 'NO ENCONTRADO', 'ni español ni inglés'),
    (ev.LATINO, 'LATINO (incrustado)', 'pista 3 Español (Latinoamérica'),
]

NOMBRES_EJEMPLO = [f'Serie.de.Ejemplo.S01E{n:02d}.1080p.WEB-DL.mkv' for n in range(1, 13)] + [
    'Pelicula.de.Ejemplo.2024.2160p.UHD.BluRay.mkv', 'Documental.de.Ejemplo.2023.720p.mp4']


def resultado_demo(path, indice, limite=40):
    if indice > limite:
        return Resultado(path, 'PENDIENTE (límite)', f'máx. {limite} por ejecución', ev.PENDIENTE)
    semilla = int(hashlib.md5(path.name.encode()).hexdigest(), 16)
    categoria, estado, fuente = _EJEMPLOS[(semilla + indice) % len(_EJEMPLOS)]
    return Resultado(path, estado, fuente, categoria)


def resultados_demo(carpeta=Path('C:/Series/Ejemplo')):
    return [resultado_demo(carpeta / n, i) for i, n in enumerate(NOMBRES_EJEMPLO, 1)]


def lineas_demo(r):
    yield f'\n== {r.nombre}'
    if r.categoria == ev.CASTELLANO and 'incrustado' not in r.estado:
        yield f'  {r.fuente.split()[0]:13} id={r.fuente.split()[-1]} score=918 sincronía=0 españa=50 latino=0 ' \
              f'episodio_ok=True duración_ok=True'
    elif 'incrustado' in r.estado:
        yield '  3 pistas de subtítulos incrustadas'
        yield f'  {r.fuente}: españa=41 latino=0'


class TrabajadorDemo(QObject):
    inicio = Signal(list)                  # [Path]
    video = Signal(int, int, object)       # índice, total, Path
    detalle = Signal(str)
    resultado = Signal(object)             # Resultado
    terminado = Signal(list, bool, float)  # resultados, cancelado, segundos

    def __init__(self, ruta, parent=None):
        super().__init__(parent)
        self.ruta = Path(ruta)
        self._cancelado = False
        self._resultados = []
        self._timer = QTimer(self)
        self._timer.setInterval(260)
        self._timer.timeout.connect(self._paso)

    def empezar(self):
        self._t0 = time.monotonic()
        try:
            self._videos = buscar_videos(self.ruta)[:500]
        except OSError:
            self._videos = []
        self._i = 0
        self.inicio.emit(self._videos)
        self._timer.start()

    def cancelar(self):
        self._cancelado = True

    def _paso(self):
        if self._cancelado or self._i >= len(self._videos):
            self._timer.stop()
            self.terminado.emit(self._resultados, self._cancelado, time.monotonic() - self._t0)
            return
        path = self._videos[self._i]
        self._i += 1
        self.video.emit(self._i, len(self._videos), path)
        r = resultado_demo(path, self._i)
        if r.categoria != ev.YA_CASTELLANO:
            for linea in lineas_demo(r):
                self.detalle.emit(linea)
        self._resultados.append(r)
        self.resultado.emit(r)
