"""Trabajador de DEMOSTRACIÓN para el prototipo (Fase 2): no busca ni descarga nada.

Emite las mismas señales que tendrá el trabajador real (Fase 3), con resultados inventados
sobre los nombres reales de los vídeos soltados, para probar la interfaz y el arrastre.
"""
import hashlib
import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from subtitulos import eventos as ev
from subtitulos.archivos import buscar_en_varias
from subtitulos.eventos import Resultado
from subtitulos.idioma import N_, tr

# (categoría, estado, origen). Los estados y orígenes, como los escribe el núcleo en cada idioma: una
# pista es (número, nombre) y el resto, un texto para traducir o un dato tal cual (proveedor e id).
_EJEMPLOS = [
    (ev.CASTELLANO, N_('CASTELLANO'), 'addic7ed updated/5/6159/8'),
    (ev.CASTELLANO, N_('CASTELLANO (incrustado)'), (3, 'Español (España)')),
    (ev.CASTELLANO, N_('CASTELLANO'), 'opensubtitles 1955123087'),
    (ev.YA_CASTELLANO, N_('ya tenía castellano'), '-'),
    (ev.YA_CASTELLANO, N_('ya tenía castellano'), N_('renombrado desde {extension}.srt')),
    (ev.CASTELLANO, N_('CASTELLANO'), 'subtitulamos 4821'),
    (ev.LATINO, N_('LATINO'), 'opensubtitles 1955120044'),
    (ev.YA_CASTELLANO, N_('ya tenía castellano'), '-'),
    (ev.CASTELLANO, N_('CASTELLANO'), 'gestdown 7f3a91c2'),
    (ev.INGLES, N_('INGLÉS (incrustado)'), (2, 'English SDH')),
    (ev.CASTELLANO, N_('CASTELLANO (incrustado)'), (4, 'Español (Castellano)')),
    (ev.SIN_CAMBIOS, 'LATINO', '-'),
    (ev.NO_ENCONTRADO, N_('NO ENCONTRADO'), N_('ni español ni inglés')),
    (ev.LATINO, N_('LATINO (incrustado)'), (3, 'Español (Latinoamérica')),
]


def _origen(origen):
    if isinstance(origen, tuple):
        return f"{tr('pista {n}', n=origen[0])} {origen[1]}"
    if origen.startswith('renombrado'):
        return tr(origen, extension='.es')
    return tr(origen) if origen == N_('ni español ni inglés') else origen

NOMBRES_EJEMPLO = [f'Serie.de.Ejemplo.S01E{n:02d}.1080p.WEB-DL.mkv' for n in range(1, 13)] + [
    'Pelicula.de.Ejemplo.2024.2160p.UHD.BluRay.mkv', 'Documental.de.Ejemplo.2023.720p.mp4']


def resultado_demo(path, indice, limite=40):
    if indice > limite:
        return Resultado(path, tr('PENDIENTE (límite)'), tr('máx. {n} por ejecución', n=limite), ev.PENDIENTE)
    semilla = int(hashlib.md5(path.name.encode()).hexdigest(), 16)
    categoria, estado, origen = _EJEMPLOS[(semilla + indice) % len(_EJEMPLOS)]
    if categoria == ev.SIN_CAMBIOS:
        texto = tr('{tipo} (ya tenía .srt)', tipo=tr(estado))
    else:
        texto = tr(estado)
    return Resultado(path, texto, _origen(origen), categoria)



def resultados_demo(carpeta=Path('C:/Series/Ejemplo')):
    return [resultado_demo(carpeta / n, i) for i, n in enumerate(NOMBRES_EJEMPLO, 1)]


def lineas_demo(r):
    """Lo que escribiría el núcleo en Detalles (con los mismos textos, en el idioma de la app)."""
    yield f'\n== {r.nombre}'
    incrustado = r.fuente.startswith(tr('pista {n}', n=''))
    if r.categoria == ev.CASTELLANO and not incrustado:
        proveedor, id_ = r.fuente.split()[0], r.fuente.split()[-1]
        yield tr('  {proveedor:13} id={id} score={score} sincronía={sinc} españa={es} latino={la} '
                 'episodio_ok={ep_ok} duración_ok={dur_ok}', proveedor=proveedor, id=id_, score=918, sinc=0, es=50,
                 la=0, ep_ok=True, dur_ok=True)
    elif incrustado:
        yield tr('  {n} pistas de subtítulos incrustadas', n=3)
        yield f'  {r.fuente}: ' + tr('españa={es} latino={la}', es=41, la=0)


class TrabajadorDemo(QObject):
    inicio = Signal(list)                  # [Path]
    video = Signal(int, int, object)       # índice, total, Path
    detalle = Signal(str)
    resultado = Signal(object)             # Resultado
    terminado = Signal(list, bool, float)  # resultados, cancelado, segundos

    def __init__(self, ruta, parent=None, recursivo=True):
        super().__init__(parent)
        self.recursivo = recursivo
        self.rutas = list(ruta) if isinstance(ruta, (list, tuple)) else [Path(ruta)]
        self._cancelado = False
        self._resultados = []
        self._timer = QTimer(self)
        self._timer.setInterval(260)
        self._timer.timeout.connect(self._paso)

    def empezar(self):
        self._t0 = time.monotonic()
        try:
            self._videos = buscar_en_varias(self.rutas, self.recursivo)[:500]
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
