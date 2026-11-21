"""Aviso de versión nueva (arriba de la ventana) y el controlador que consulta y descarga en hilos aparte.

La red nunca bloquea la ventana: los hilos solo emiten señales, que Qt entrega en el hilo de la ventana
porque el receptor es un QObject de ese hilo.
"""
import threading
import time

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from . import actualizar, tema
from .componentes import IconoLabel
from .vista_inicio import boton, etiqueta


class Actualizador(QObject):
    novedad = Signal(object, bool)     # Novedad, manual
    al_dia = Signal(bool)              # manual
    fallo = Signal(str, bool)          # mensaje, manual
    progreso = Signal(int, int)        # bytes descargados, total
    descargado = Signal(object)        # Path del instalador ya verificado
    fallo_descarga = Signal(str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.consultando = False
        self.descargando = False
        self._cancelar = threading.Event()
        # El resultado se apunta en el hilo de la ventana (la configuración no se toca desde otro hilo).
        self.novedad.connect(self._comprobado)
        self.al_dia.connect(self._comprobado)

    def toca(self):
        """La comprobación automática: activada y sin hacer en las últimas horas."""
        return self.config.actualizaciones and time.time() - self.config.ultima_comprobacion >= actualizar.INTERVALO

    def comprobar(self, manual=False):
        if self.consultando:
            return
        self.consultando = True

        def hilo():
            try:
                novedad = actualizar.consultar()
            except actualizar.ErrorActualizacion as e:
                self.consultando = False
                self.fallo.emit(str(e), manual)
                return
            except Exception as e:  # noqa: BLE001 - nunca debe romper la app
                self.consultando = False
                self.fallo.emit(f'Error inesperado ({type(e).__name__}).', manual)
                return
            self.consultando = False
            if novedad:
                self.novedad.emit(novedad, manual)
            else:
                self.al_dia.emit(manual)

        threading.Thread(target=hilo, name='buscar-actualizacion', daemon=True).start()

    def _comprobado(self, *_):
        self.config.ultima_comprobacion = time.time()
        self.config.guardar()

    def descargar(self, novedad):
        if self.descargando or novedad.instalador is None:
            return
        self.descargando = True
        self._cancelar.clear()

        def hilo():
            try:
                ruta = actualizar.descargar(novedad.instalador, progreso=self.progreso.emit,
                                            cancelada=self._cancelar.is_set)
            except actualizar.Cancelada:
                self.descargando = False
                return
            except actualizar.ErrorActualizacion as e:
                self.descargando = False
                self.fallo_descarga.emit(str(e))
                return
            except Exception as e:  # noqa: BLE001
                self.descargando = False
                self.fallo_descarga.emit(f'Error inesperado al descargar ({type(e).__name__}).')
                return
            self.descargando = False
            if not self._cancelar.is_set():
                self.descargado.emit(ruta)

        threading.Thread(target=hilo, name='descargar-actualizacion', daemon=True).start()

    def cancelar(self):
        self._cancelar.set()


class AvisoActualizacion(QFrame):
    """Franja discreta con la versión nueva, sus novedades y los botones para instalarla."""
    actualizar = Signal()
    descargar_pagina = Signal()     # versión portable o sin huella: abrir la página de la Release
    novedades = Signal()            # abrir la página de la versión
    mas_tarde = Signal()
    cancelar = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('bannerInfo')
        self.estado = None
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 10, 12, 10)
        v.setSpacing(8)
        fila = QHBoxLayout()
        fila.setSpacing(12)
        self.icono = IconoLabel('actualizar', 'acento', 20)
        fila.addWidget(self.icono, 0, Qt.AlignTop)
        textos = QVBoxLayout()
        textos.setSpacing(1)
        self.titulo = etiqueta('', 'avisoTitulo')
        self.detalle = etiqueta('', 'ayuda', envolver=True)
        for l in (self.titulo, self.detalle):
            l.setTextFormat(Qt.PlainText)
        textos.addWidget(self.titulo)
        textos.addWidget(self.detalle)
        fila.addLayout(textos, 1)
        self.b_notas = boton('Novedades', nombre='plano')
        self.b_notas.setCheckable(True)
        self.b_notas.toggled.connect(self._ver_notas)
        self.b_pagina = boton('Ver en GitHub', nombre='plano')
        self.b_pagina.clicked.connect(self.novedades)
        self.b_tarde = boton('Más tarde')
        self.b_tarde.clicked.connect(self.mas_tarde)
        self.b_cerrar = boton('Cerrar')
        self.b_cerrar.clicked.connect(self.mas_tarde)
        self.b_cancelar = boton('Cancelar')
        self.b_cancelar.clicked.connect(self.cancelar)
        self.b_accion = boton('Actualizar', nombre='primario')
        self.b_accion.clicked.connect(self._accion)
        for b in (self.b_notas, self.b_pagina, self.b_tarde, self.b_cerrar, self.b_cancelar, self.b_accion):
            fila.addWidget(b, 0, Qt.AlignVCenter)
        v.addLayout(fila)
        self.notas = QLabel()
        self.notas.setObjectName('avisoNotas')
        self.notas.setTextFormat(Qt.PlainText)          # las notas vienen de fuera: nunca como HTML
        self.notas.setWordWrap(True)
        self.notas.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.notas.setContentsMargins(tema.px(32), 0, 0, 0)
        v.addWidget(self.notas)
        self._ocupada = False
        self.hide()

    def poner(self, estado, novedad=None, mensaje=''):
        """Estados: 'disponible', 'portable', 'descargando', 'instalando', 'error', 'actualizada'."""
        self.estado = estado
        v = actualizar.version_corta(novedad.version) if novedad else ''
        botones = {
            'disponible': (self.b_notas, self.b_tarde, self.b_accion),
            'portable': (self.b_notas, self.b_tarde, self.b_accion),
            'descargando': (self.b_cancelar,),
            'instalando': (),
            'error': (self.b_tarde, self.b_accion),
            'actualizada': (self.b_pagina, self.b_cerrar),
        }[estado]
        for b in (self.b_notas, self.b_pagina, self.b_tarde, self.b_cerrar, self.b_cancelar, self.b_accion):
            b.setVisible(b in botones)
        nombre = 'bannerError' if estado == 'error' else 'bannerInfo'
        if self.objectName() != nombre:
            self.setObjectName(nombre)
            self.style().unpolish(self)
            self.style().polish(self)
        self.icono.poner('aviso' if estado == 'error' else 'actualizar')
        if estado == 'disponible':
            self.titulo.setText(f'Hay una versión nueva: {v}')
            self.detalle.setText('Se descarga, se comprueba que es la publicada en GitHub y se instala sola. '
                                 'La app se cerrará y se volverá a abrir.')
            self.b_accion.setText('Actualizar')
        elif estado == 'portable':
            self.titulo.setText(f'Hay una versión nueva: {v}')
            self.detalle.setText(mensaje or 'Descárgala desde su página en GitHub.')
            self.b_accion.setText('Descargar')
        elif estado == 'descargando':
            self.titulo.setText(f'Descargando la versión {v}…')
            self.detalle.setText(mensaje or 'Comprobando la huella SHA-256 mientras se descarga.')
        elif estado == 'instalando':
            self.titulo.setText(f'Instalando la versión {v}…')
            self.detalle.setText('La app se cierra ahora y se volverá a abrir sola en unos segundos.')
        elif estado == 'error':
            self.titulo.setText('No se ha podido actualizar')
            self.detalle.setText(mensaje)
            self.b_accion.setText('Reintentar')
        elif estado == 'actualizada':
            self.titulo.setText(f'Actualizada a la versión {v}')
            self.detalle.setText('Puedes ver qué ha cambiado en la página de esta versión.')
        if novedad is not None:
            self.notas.setText(novedad.notas)
        if estado not in ('disponible', 'portable'):
            self.b_notas.setChecked(False)
        self._ver_notas(self.b_notas.isChecked())
        self.poner_ocupada(self._ocupada)
        self.show()

    def poner_progreso(self, hecho, total):
        if self.estado == 'descargando':
            mb = hecho / 1024 / 1024
            if total:
                self.detalle.setText(f'{hecho * 100 // total} % · {mb:.1f} de {total / 1024 / 1024:.1f} MB')
            else:
                self.detalle.setText(f'{mb:.1f} MB')

    def poner_ocupada(self, ocupada):
        """Durante una búsqueda no se puede actualizar (la app tiene que cerrarse)."""
        self._ocupada = ocupada
        instala = self.estado in ('disponible', 'error')
        self.b_accion.setEnabled(not (ocupada and instala))
        self.b_accion.setToolTip('Disponible cuando termine la búsqueda.' if ocupada and instala else '')

    def _ver_notas(self, ver):
        self.notas.setVisible(bool(ver and self.notas.text()))
        self.b_notas.setText('Ocultar novedades' if ver else 'Novedades')

    def _accion(self):
        if self.estado == 'portable':
            self.descargar_pagina.emit()
        else:
            self.actualizar.emit()

    def refrescar(self):
        self.icono.refrescar()
        self.notas.setContentsMargins(tema.px(32), 0, 0, 0)
