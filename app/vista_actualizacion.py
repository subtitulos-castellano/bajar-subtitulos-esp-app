"""Aviso de versión nueva (arriba de la ventana) y el controlador que consulta y descarga en hilos aparte.

La red nunca bloquea la ventana: los hilos solo emiten señales, que Qt entrega en el hilo de la ventana
porque el receptor es un QObject de ese hilo.
"""
import threading
import time

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout

from subtitulos.idioma import tr

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
    instalado = Signal(object)         # Linux: la orden con la que volver a abrir la app ya actualizada
    instalacion_cancelada = Signal()   # Linux: se ha cerrado la ventana de la contraseña
    fallo_instalacion = Signal(str)

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
                self.fallo.emit(tr('Error inesperado ({error}).', error=type(e).__name__), manual)
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
                self.fallo_descarga.emit(tr('Error inesperado al descargar ({error}).', error=type(e).__name__))
                return
            self.descargando = False
            if not self._cancelar.is_set():
                self.descargado.emit(ruta)

        threading.Thread(target=hilo, name='descargar-actualizacion', daemon=True).start()

    def instalar_linux(self, ruta, version):
        """Linux: instala en un hilo (el gestor de paquetes espera a la contraseña y tarda un poco)."""
        def hilo():
            try:
                orden = actualizar.instalar_linux(ruta, version)
            except actualizar.Cancelada:
                self.instalacion_cancelada.emit()
                return
            except actualizar.ErrorActualizacion as e:
                self.fallo_instalacion.emit(str(e))
                return
            except Exception as e:  # noqa: BLE001
                self.fallo_instalacion.emit(tr('Error inesperado al instalar ({error}).', error=type(e).__name__))
                return
            self.instalado.emit(orden)

        threading.Thread(target=hilo, name='instalar-actualizacion', daemon=True).start()

    def cancelar(self):
        self._cancelar.set()


ALTO_NOTAS = 0.25     # parte del alto de la ventana que pueden ocupar las notas, como mucho (el resto, la página)


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
        fila = self._fila = QHBoxLayout()
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
        self.b_notas = boton(tr('Novedades'), nombre='plano')
        self.b_notas.setCheckable(True)
        self.b_notas.toggled.connect(self._ver_notas)
        self.b_pagina = boton(tr('Ver en GitHub'), nombre='plano')
        self.b_pagina.clicked.connect(self.novedades)
        self.b_tarde = boton(tr('Más tarde'))
        self.b_tarde.clicked.connect(self.mas_tarde)
        self.b_cerrar = boton(tr('Cerrar'))
        self.b_cerrar.clicked.connect(self.mas_tarde)
        self.b_cancelar = boton(tr('Cancelar'))
        self.b_cancelar.clicked.connect(self.cancelar)
        self.b_accion = boton(tr('Actualizar'), nombre='primario')
        self.b_accion.clicked.connect(self._accion)
        for b in (self.b_notas, self.b_pagina, self.b_tarde, self.b_cerrar, self.b_cancelar, self.b_accion):
            fila.addWidget(b, 0, Qt.AlignVCenter)
        v.addLayout(fila)
        self.notas = QLabel()
        self.notas.setObjectName('avisoNotas')
        self.notas.setTextFormat(Qt.PlainText)          # las notas vienen de fuera: nunca como HTML
        self.notas.setWordWrap(True)
        self.notas.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # Las notas largas no caben: van en un marco con barra de desplazamiento (también con la rueda),
        # tan alto como el texto, pero como mucho ALTO_NOTAS de la ventana.
        self.marco_notas = QScrollArea()
        self.marco_notas.setObjectName('avisoNotasMarco')
        self.marco_notas.viewport().setObjectName('avisoNotasVista')
        self.marco_notas.setFrameShape(QFrame.NoFrame)
        self.marco_notas.setWidgetResizable(True)
        self.marco_notas.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.marco_notas.setWidget(self.notas)
        self.marco_notas.hide()
        self._margenes_notas()
        v.addWidget(self.marco_notas)
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
            self.titulo.setText(tr('Hay una versión nueva: {version}', version=v))
            self.detalle.setText(mensaje or tr('Se descarga, se comprueba que es la publicada en GitHub y se '
                                               'instala sola. La app se cerrará y se volverá a abrir.'))
            self.b_accion.setText(tr('Actualizar'))
        elif estado == 'portable':
            self.titulo.setText(tr('Hay una versión nueva: {version}', version=v))
            self.detalle.setText(mensaje or tr('Descárgala desde su página en GitHub.'))
            self.b_accion.setText(tr('Descargar'))
        elif estado == 'descargando':
            self.titulo.setText(tr('Descargando la versión {version}…', version=v))
            self.detalle.setText(mensaje or tr('Comprobando la huella SHA-256 mientras se descarga.'))
        elif estado == 'instalando':
            self.titulo.setText(tr('Instalando la versión {version}…', version=v))
            self.detalle.setText(mensaje or tr('La app se cierra ahora y se volverá a abrir sola en unos segundos.'))
        elif estado == 'error':
            self.titulo.setText(tr('No se ha podido actualizar'))
            self.detalle.setText(mensaje)
            self.b_accion.setText(tr('Reintentar'))
        elif estado == 'actualizada':
            self.titulo.setText(tr('Actualizada a la versión {version}', version=v))
            self.detalle.setText(tr('Puedes ver qué ha cambiado en la página de esta versión.'))
        if novedad is not None:
            self.notas.setText(novedad.notas)
            self.marco_notas.verticalScrollBar().setValue(0)
        if estado not in ('disponible', 'portable'):
            self.b_notas.setChecked(False)
        self._ver_notas(self.b_notas.isChecked())
        self.poner_ocupada(self._ocupada)
        self.show()

    def poner_progreso(self, hecho, total):
        if self.estado == 'descargando':
            mb = hecho / 1024 / 1024
            if total:
                self.detalle.setText(tr('{porcentaje} % · {hecho:.1f} de {total:.1f} MB', porcentaje=hecho * 100 // total,
                                        hecho=mb, total=total / 1024 / 1024))
            else:
                self.detalle.setText(f'{mb:.1f} MB')

    def poner_ocupada(self, ocupada):
        """Durante una búsqueda no se puede actualizar (la app tiene que cerrarse)."""
        self._ocupada = ocupada
        instala = self.estado in ('disponible', 'error')
        self.b_accion.setEnabled(not (ocupada and instala))
        self.b_accion.setToolTip(tr('Disponible cuando termine la búsqueda.') if ocupada and instala else '')

    def _ver_notas(self, ver):
        self.marco_notas.setVisible(bool(ver and self.notas.text()))
        self.b_notas.setText(tr('Ocultar novedades') if ver else tr('Novedades'))
        self.ajustar_notas()
        QTimer.singleShot(0, self.ajustar_notas)      # cuando ya tiene su ancho definitivo

    def alto_maximo_notas(self):
        """ALTO_NOTAS de la ventana, y menos si no, la página de debajo no cabría (ventana pequeña)."""
        ventana = self.window()
        if ventana is self:
            return tema.px(150)
        tope = max(tema.px(120), int(ventana.height() * ALTO_NOTAS))
        paginas = getattr(ventana, 'paginas', None)
        if paginas is not None and paginas.currentWidget() is not None and self.marco_notas.isVisible():
            # El aviso sin las notas (márgenes, título y botones), con su ancho: no depende del alto actual.
            m = self.layout().contentsMargins()
            ancho = self.width() - m.left() - m.right()
            cabecera = self._fila.heightForWidth(ancho) if self._fila.hasHeightForWidth() else -1
            if cabecera < 0:
                cabecera = self._fila.sizeHint().height()
            resto_aviso = m.top() + m.bottom() + cabecera + self.layout().spacing()
            libre = (ventana.centralWidget().height() - resto_aviso - tema.px(16)
                     - paginas.currentWidget().minimumSizeHint().height())
            tope = min(tope, max(tema.px(60), libre))
        return tope

    def ajustar_notas(self):
        """Alto del marco de las notas: el del texto con el ancho que tiene, sin pasar del máximo."""
        if not self.marco_notas.isVisible():
            return
        ancho = self.marco_notas.viewport().width()
        alto = self.notas.heightForWidth(ancho) if ancho > 0 else -1
        if alto < 0:
            alto = self.notas.sizeHint().height()
        self.marco_notas.setFixedHeight(min(alto, self.alto_maximo_notas()))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if e.size().width() != e.oldSize().width():   # cambia el ajuste de línea
            self.ajustar_notas()

    def _margenes_notas(self):
        # A la izquierda, alineadas con el título; a la derecha, sitio para la barra.
        self.notas.setContentsMargins(tema.px(32), 0, tema.px(12), 0)

    def _accion(self):
        if self.estado == 'portable':
            self.descargar_pagina.emit()
        else:
            self.actualizar.emit()

    def refrescar(self):
        self.icono.refrescar()
        self._margenes_notas()
        self.ajustar_notas()
