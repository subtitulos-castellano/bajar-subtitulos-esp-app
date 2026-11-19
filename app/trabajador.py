"""Ejecuta procesar() en un hilo aparte y avisa a la interfaz con señales de Qt.

La interfaz nunca se bloquea: el hilo de la ventana solo recibe señales. El núcleo (que
importa subliminal) se carga la primera vez que hace falta, o antes con precargar().

Cancelar es inmediato para la interfaz: `terminado` se emite al momento con lo hecho hasta
entonces, y el hilo se queda terminando en segundo plano la consulta a internet que tenga en
curso (no se puede cortar a medias). En cuanto vuelve, el núcleo ve la cancelación y para
sin escribir nada más. Lo que emita después se descarta.
"""
import logging
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal

_carga = threading.Lock()


def nucleo():
    """Importa el núcleo (subliminal, guessit...): ~1-2 s la primera vez."""
    with _carga:
        from subtitulos import nucleo as n
        _preparar_avisos(n)
        return n


def precargar():
    """Carga el núcleo en segundo plano tras abrir la ventana, para que el primer arrastre sea rápido."""
    threading.Thread(target=nucleo, name='precarga-nucleo', daemon=True).start()


class _Avisos(logging.Handler):
    """Lleva los avisos de subliminal a 'Detalles' de la búsqueda que los produce (como la CLI a stderr).

    Puede haber dos búsquedas a la vez durante unos segundos (una cancelada que termina su consulta
    y la nueva): cada aviso va a la de su hilo."""
    destinos = {}

    def emit(self, record):
        destino = _Avisos.destinos.get(threading.get_ident())
        if destino is not None:
            try:
                destino(self.format(record))
            except Exception:  # noqa: BLE001 - un aviso nunca debe romper la búsqueda
                pass


_manejador = None


def _preparar_avisos(n):
    global _manejador
    if _manejador is None:
        _manejador = _Avisos()
        _manejador.setFormatter(logging.Formatter('  aviso (%(name)s): %(message)s'))
        _manejador.addFilter(n.SinRuido())
        raiz = logging.getLogger()
        raiz.addHandler(_manejador)
        raiz.setLevel(logging.WARNING)


class Trabajador(QObject):
    inicio = Signal(list)                  # [Path]
    video = Signal(int, int, object)       # índice, total, Path
    detalle = Signal(str)
    resultado = Signal(object)             # Resultado
    error = Signal(str)
    terminado = Signal(list, bool, float)  # resultados, cancelado, segundos

    def __init__(self, ruta, opciones, credenciales, parent=None):
        super().__init__(parent)
        # Una ruta, o una lista (vídeos sueltos y carpetas soltados a la vez: una sola búsqueda).
        self.ruta = [Path(r) for r in ruta] if isinstance(ruta, (list, tuple)) else Path(ruta)
        self.opciones = opciones
        self.credenciales = credenciales
        self.resultados = []
        self._cancelar = threading.Event()
        self._cerrado = threading.Event()    # tras cancelar, la interfaz ya no escucha
        self._candado = threading.Lock()
        self._hilo = None
        self._t0 = 0.0

    def empezar(self):
        self._t0 = time.monotonic()
        # Hilo 'daemon': si se cierra la app mientras espera una respuesta de internet, no la retiene.
        self._hilo = threading.Thread(target=self._ejecutar, name='busqueda', daemon=True)
        self._hilo.start()

    def cancelar(self):
        """Para la búsqueda. La interfaz recibe `terminado` en este mismo instante."""
        self._cancelar.set()
        if self._cerrar():
            self.terminado.emit(list(self.resultados), True, time.monotonic() - self._t0)

    def _cerrar(self):
        """Marca el final una sola vez (cancelar y terminar pueden coincidir). True si lo ha marcado."""
        with self._candado:
            if self._cerrado.is_set():
                return False
            self._cerrado.set()
            return True

    def activo(self):
        return self._hilo is not None and self._hilo.is_alive()

    def esperar(self, segundos=10):
        if self._hilo is not None:
            self._hilo.join(segundos)

    def _emitir(self, senal, *args):
        if not self._cerrado.is_set():
            senal.emit(*args)

    def _ejecutar(self):
        trabajador = self
        try:
            n = nucleo()

            class Puente(n.Eventos):
                def inicio(self, videos):
                    trabajador._emitir(trabajador.inicio, list(videos))

                def video(self, indice, total, path):
                    trabajador._emitir(trabajador.video, indice, total, path)

                def detalle(self, linea):
                    trabajador._emitir(trabajador.detalle, linea)

                def resultado(self, r):
                    with trabajador._candado:
                        if trabajador._cerrado.is_set():
                            return
                        trabajador.resultados.append(r)
                    trabajador.resultado.emit(r)

            _Avisos.destinos[threading.get_ident()] = lambda linea: self._emitir(self.detalle, linea)
            n.procesar(self.ruta, self.opciones, Puente(), self._cancelar.is_set, self.credenciales)
        except Exception as e:  # noqa: BLE001 - se muestra en la interfaz; lo ya guardado se queda
            self._emitir(self.error, f'{type(e).__name__}: {e}')
        finally:
            _Avisos.destinos.pop(threading.get_ident(), None)
        if self._cerrar():
            self.terminado.emit(list(self.resultados), False, time.monotonic() - self._t0)
