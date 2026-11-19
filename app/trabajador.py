"""Ejecuta procesar() en un hilo aparte y avisa a la interfaz con señales de Qt.

La interfaz nunca se bloquea: el hilo de la ventana solo recibe señales. El núcleo (que
importa subliminal) se carga la primera vez que hace falta, o antes con precargar().
"""
import logging
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

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
    """Lleva los avisos de subliminal a 'Detalles' del trabajo en marcha (como la CLI a stderr)."""
    destino = None

    def emit(self, record):
        destino = _Avisos.destino
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
        self.ruta = Path(ruta)
        self.opciones = opciones
        self.credenciales = credenciales
        self._cancelar = threading.Event()
        self._hilo = None

    def empezar(self):
        self._hilo = QThread()
        self._hilo.setObjectName('trabajo')
        self.moveToThread(self._hilo)
        self._hilo.started.connect(self._ejecutar)
        self.terminado.connect(self._hilo.quit)
        self._hilo.start()

    def cancelar(self):
        self._cancelar.set()

    def esperar(self, ms=10000):
        if self._hilo is not None:
            self._hilo.wait(ms)

    def _ejecutar(self):
        t0 = time.monotonic()
        resultados = []
        trabajador = self

        try:
            n = nucleo()

            class Puente(n.Eventos):
                def inicio(self, videos):
                    trabajador.inicio.emit(list(videos))

                def video(self, indice, total, path):
                    trabajador.video.emit(indice, total, path)

                def detalle(self, linea):
                    trabajador.detalle.emit(linea)

                def resultado(self, r):
                    resultados.append(r)
                    trabajador.resultado.emit(r)

            _Avisos.destino = self.detalle.emit
            n.procesar(self.ruta, self.opciones, Puente(), self._cancelar.is_set, self.credenciales)
        except Exception as e:  # noqa: BLE001 - se muestra en la interfaz; lo ya guardado se queda
            self.error.emit(f'{type(e).__name__}: {e}')
        finally:
            _Avisos.destino = None
        self.terminado.emit(resultados, self._cancelar.is_set(), time.monotonic() - t0)
