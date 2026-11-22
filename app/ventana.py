"""Ventana principal: barra lateral (Inicio, Buscando…, Configuración), arrastre en toda la ventana y cola."""
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QGuiApplication, QIcon, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from subtitulos.archivos import es_video

from . import actualizar, iconos, tema
from .componentes import IconoLabel, color
from .credenciales import credenciales_proveedores
from .demo import TrabajadorDemo
from .trabajador import Trabajador
from .vista_actualizacion import Actualizador, AvisoActualizacion
from .vista_ajustes import VistaAjustes, resumen_preferencias
from .vista_inicio import MARGEN, VistaInicio

from . import __version__

NOMBRE_APP = 'Bajar Subtítulos ESP'
VERSION = __version__.removesuffix('.0') if __version__.count('.') == 2 else __version__

INICIO, BUSCANDO, AJUSTES = range(3)


def icono_app():
    """Icono de la app (iconos.ICONO_APP) dibujado a cada tamaño que usa Windows, nítido en todos."""
    ico = QIcon()
    for lado in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        ico.addPixmap(iconos.pixmap_app(lado))
    return ico


def rutas_validas(mime):
    """Rutas locales soltadas que son carpetas o vídeos."""
    if not mime.hasUrls():
        return []
    rutas = [Path(u.toLocalFile()) for u in mime.urls() if u.isLocalFile()]
    return [r for r in rutas if r.is_dir() or (r.is_file() and es_video(r))]


class CapaArrastre(QWidget):
    """Capa sobre toda la ventana mientras se arrastra algo encima."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.texto, self.detalle = '', ''
        self.hide()

    def mostrar(self, texto, detalle):
        self.texto, self.detalle = texto, detalle
        self.setGeometry(self.parent().rect())
        self.raise_()
        self.show()
        self.update()

    def paintEvent(self, _):
        px = tema.px
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), color('fondo', 0.96))
        r = QRectF(self.rect()).adjusted(20, 20, -20, -20)
        p.setPen(QPen(color('acento'), 2, Qt.DashLine))
        p.setBrush(color('acento_suave'))
        p.drawRoundedRect(r, 18, 18)
        c = r.center()
        d = px(84)
        p.setPen(Qt.NoPen)
        p.setBrush(color('acento'))
        p.drawEllipse(QRectF(c.x() - d / 2, c.y() - px(90), d, d))
        i = px(44)
        iconos.dibujar(p, 'soltar', '#ffffff', QRectF(c.x() - i / 2, c.y() - px(90) + (d - i) / 2, i, i))
        p.setFont(tema.fuente(self.font(), 17, QFont.DemiBold, titulo=True))
        p.setPen(color('texto'))
        p.drawText(QRectF(r.left(), c.y() + px(10), r.width(), px(36)), Qt.AlignCenter, self.texto)
        p.setFont(tema.fuente(self.font(), 10.5))
        p.setPen(color('texto2'))
        p.drawText(QRectF(r.left(), c.y() + px(50), r.width(), px(26)), Qt.AlignCenter, self.detalle)


class Ventana(QMainWindow):
    # Para el icono junto al reloj (búsquedas en segundo plano, ver bandeja.py).
    progreso = Signal(int, int)               # vídeo, total
    lote_terminado = Signal(list, bool, list)  # resultados, cancelado, errores
    en_reposo = Signal()                      # no queda nada en marcha ni en la cola

    def __init__(self, config, demo=False):
        super().__init__()
        self.config = config
        self.demo = demo
        self.setWindowTitle(NOMBRE_APP)
        self.setWindowIcon(icono_app())
        self.setAcceptDrops(True)
        self.preferencia_tema = config.tema
        self.cola = []
        self.trabajador = None
        self.hay_busqueda = False       # hay una búsqueda (en marcha o su resumen) a la que volver
        self._normal = None             # posición y tamaño sin maximizar, para recordarlos
        self.mostrada = False           # se ha llegado a ver (en segundo plano puede no verse nunca)
        self.ocultar_al_cerrar = False  # en segundo plano: cerrar con una búsqueda en marcha la oculta

        raiz = QWidget()
        raiz.setObjectName('raiz')
        self.setCentralWidget(raiz)
        h = QHBoxLayout(raiz)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self._lateral())
        derecha = QVBoxLayout()
        derecha.setContentsMargins(0, 0, 0, 0)
        derecha.setSpacing(0)
        self.aviso = AvisoActualizacion()
        self.marco_aviso = QWidget()
        self.marco_aviso.setObjectName('pagina')
        ma = QVBoxLayout(self.marco_aviso)
        ma.setContentsMargins(MARGEN, 16, MARGEN, 0)
        ma.addWidget(self.aviso)
        self.marco_aviso.hide()
        derecha.addWidget(self.marco_aviso)
        self.paginas = QStackedWidget()
        self.inicio = VistaInicio()
        self.ajustes = VistaAjustes(config)
        self.paginas.addWidget(self.inicio)
        self.paginas.addWidget(self.ajustes)
        derecha.addWidget(self.paginas, 1)
        h.addLayout(derecha, 1)
        self.capa = CapaArrastre(raiz)
        self.actualizador = Actualizador(config, self)
        self.novedad = None             # versión nueva encontrada en GitHub

        self.inicio.elegido.connect(self.procesar)
        self.inicio.cancelar.connect(self._cancelar)
        self.inicio.ir_ajustes.connect(lambda: self.ir(AJUSTES))
        self.inicio.repetir.connect(lambda rutas: self.procesar(rutas, self.inicio.recursivo))
        self.ajustes.cambiado.connect(self._preferencias_cambiadas)
        self.ajustes.tema_elegido.connect(self.cambiar_tema)
        self.ajustes.tamano_elegido.connect(lambda: self.cambiar_tema(self.preferencia_tema))
        self.ajustes.buscar_actualizacion.connect(lambda: self.actualizador.comprobar(manual=True))
        self.actualizador.novedad.connect(self._novedad)
        self.actualizador.al_dia.connect(self._al_dia)
        self.actualizador.fallo.connect(self._fallo_consulta)
        self.actualizador.progreso.connect(self.aviso.poner_progreso)
        self.actualizador.descargado.connect(self._instalar)
        self.actualizador.fallo_descarga.connect(self._fallo_descarga)
        self.aviso.actualizar.connect(self._actualizar)
        self.aviso.descargar_pagina.connect(self._abrir_pagina_novedad)
        self.aviso.novedades.connect(self._abrir_pagina_version)
        self.aviso.mas_tarde.connect(self._ocultar_aviso)
        self.aviso.cancelar.connect(self._cancelar_descarga)
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._tema_sistema_cambiado)
        self._preferencias_cambiadas()
        self.refrescar()
        self._restaurar_ventana()
        self._actualizar_nav()
        self._aviso_actualizada()

    # ---------- Posición y tamaño ----------

    def _restaurar_ventana(self):
        """Posición y tamaño guardados. restoreGeometry() de Qt desplazaba la ventana unos píxeles en
        cada apertura con el escalado de Windows, así que se guardan y aplican a mano."""
        pantalla = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(min(tema.px(1080), int(pantalla.width() * 0.92)),
                    min(tema.px(720), int(pantalla.height() * 0.92)))
        v = self.config.ventana
        if not v:
            return
        self.resize(max(v['ancho'], self.minimumWidth()), max(v['alto'], self.minimumHeight()))
        # Solo si la esquina superior sigue dentro de alguna pantalla (pudo desconectarse un monitor).
        if QGuiApplication.screenAt(QPoint(v['x'] + 80, v['y'] + 10)) is not None:
            self.move(v['x'], v['y'])
        self._normal = (v['x'], v['y'], v['ancho'], v['alto'])

    def mostrar(self):
        if self.config.ventana and self.config.ventana.get('maximizada'):
            self.showMaximized()
        else:
            self.show()

    def showEvent(self, e):
        super().showEvent(e)
        self.mostrada = True

    def traer_al_frente(self):
        """La muestra (si estaba oculta o minimizada) y la pone delante."""
        if not self.isVisible():
            self.mostrar()
        elif self.isMinimized():
            self.showMaximized() if self.config.ventana.get('maximizada') else self.showNormal()
        self.raise_()
        self.activateWindow()

    def _anotar_normal(self):
        if self.isVisible() and not (self.isMaximized() or self.isMinimized() or self.isFullScreen()):
            f = self.frameGeometry()
            self._normal = (f.x(), f.y(), self.width(), self.height())

    def moveEvent(self, e):
        super().moveEvent(e)
        self._anotar_normal()

    def _guardar_ventana(self):
        if not self.mostrada:                     # sin verse, la posición guardada sigue valiendo
            return
        self._anotar_normal()
        if self._normal:
            x, y, ancho, alto = self._normal
            self.config.ventana = {'x': x, 'y': y, 'ancho': ancho, 'alto': alto, 'maximizada': self.isMaximized()}

    # ---------- Barra lateral ----------

    def _lateral(self):
        self.lateral = QFrame()
        self.lateral.setObjectName('lateral')
        v = QVBoxLayout(self.lateral)
        v.setContentsMargins(14, 18, 14, 14)
        v.setSpacing(4)
        marca = QHBoxLayout()
        marca.setContentsMargins(6, 0, 0, 0)
        marca.setSpacing(10)
        self.logo = QLabel()
        marca.addWidget(self.logo)
        textos = QVBoxLayout()
        textos.setSpacing(0)
        t1 = QLabel('Bajar Subtítulos')
        t1.setObjectName('marca')
        t2 = QLabel('Castellano de España')
        t2.setObjectName('marcaSub')
        textos.addWidget(t1)
        textos.addWidget(t2)
        marca.addLayout(textos, 1)
        v.addLayout(marca)
        v.addSpacing(22)
        self.nav = QButtonGroup(self)
        self.nav_botones = []
        for i, (texto, ico, ayuda) in enumerate((
                ('Inicio', 'inicio', 'Pantalla para arrastrar vídeos o carpetas'),
                ('Buscando…', 'buscar', 'La búsqueda en marcha o la última que se hizo'),
                ('Configuración', 'ajustes', 'Preferencias de la búsqueda y de la app'))):
            b = QPushButton('  ' + texto)
            b.setObjectName('nav')
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(ayuda)
            b._icono = ico
            self.nav.addButton(b, i)
            self.nav_botones.append(b)
            v.addWidget(b)
        self.nav_botones[INICIO].setChecked(True)
        self.nav.idClicked.connect(self.ir)
        v.addStretch()
        ver = QLabel(f'Versión {VERSION}')
        ver.setObjectName('version')
        v.addWidget(ver)
        return self.lateral

    def ir(self, destino):
        if destino == INICIO:
            self.hay_busqueda = False             # la búsqueda anterior se da por cerrada
            self.inicio.mostrar_reposo()
            self.paginas.setCurrentIndex(0)
        elif destino == BUSCANDO:
            self.inicio.mostrar_busqueda()
            self.paginas.setCurrentIndex(0)
        else:
            self.paginas.setCurrentIndex(1)
        self.nav_botones[destino].setChecked(True)
        self._actualizar_nav()

    def _actualizar_nav(self):
        """Mientras se busca, solo 'Buscando…' (marcado, sin poder pulsarlo). Después, todo disponible.
        'Buscando…' solo se puede pulsar si hay una búsqueda a la que volver."""
        buscando = self.trabajador is not None
        self.nav_botones[INICIO].setEnabled(not buscando)
        self.nav_botones[AJUSTES].setEnabled(not buscando)
        self.nav_botones[BUSCANDO].setEnabled(self.hay_busqueda and not buscando)
        self.inicio.b_cambiar_preferencias.setEnabled(not buscando)
        self.aviso.poner_ocupada(buscando)

    # ---------- Tema y tamaño del texto ----------

    def cambiar_tema(self, preferencia):
        self.preferencia_tema = preferencia
        tema.aplicar(QApplication.instance(), preferencia, self.config.tamano_texto)
        self.refrescar()

    def _tema_sistema_cambiado(self):
        if self.preferencia_tema == 'sistema':
            self.cambiar_tema('sistema')

    def changeEvent(self, e):
        super().changeEvent(e)
        # Al volver a la app, por si se ha cambiado el tamaño del texto en Windows (como el Explorador).
        if e.type() == QEvent.ActivationChange and self.isActiveWindow() and not self.config.tamano_texto:
            if abs(tema.escala_windows() / 100 - tema.escala()) > 0.001:
                self.cambiar_tema(self.preferencia_tema)

    def refrescar(self):
        t = tema.actual()
        px = tema.px
        self.setMinimumSize(px(640) + px(232), px(560))
        self.lateral.setFixedWidth(px(232))
        # Dibujado a la resolución real de la pantalla (nítido con cualquier escalado de Windows).
        escala = self.devicePixelRatioF() or 1.0
        logo = iconos.pixmap_app(round(px(40) * escala))
        logo.setDevicePixelRatio(escala)
        self.logo.setPixmap(logo)
        for b in self.nav_botones:
            b.setIcon(iconos.icono(b._icono, t['texto2'], px(18)))
        for ic in self.findChildren(IconoLabel):
            ic.refrescar()
        self.inicio.refrescar()
        self.ajustes.refrescar()
        self.aviso.refrescar()
        self.update()
        for w in self.findChildren(QWidget):
            w.update()

    def _preferencias_cambiadas(self):
        o = self.config.opciones
        self.inicio.poner_preferencias(resumen_preferencias(o), o.dry_run)

    # ---------- Arrastrar y soltar ----------

    def dragEnterEvent(self, e):
        rutas = rutas_validas(e.mimeData())
        if not rutas:
            e.ignore()
            return
        e.acceptProposedAction()
        n = len(rutas)
        if self.trabajador:
            texto = 'Suelta para añadir a la cola'
            detalle = 'Se procesará en cuanto termine lo que está en marcha.'
        else:
            texto = 'Suelta para buscar subtítulos'
            detalle = (f'{n} elementos' if n > 1 else rutas[0].name)
        self.capa.mostrar(texto, detalle)

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.capa.hide()

    def dropEvent(self, e):
        self.capa.hide()
        rutas = rutas_validas(e.mimeData())
        if rutas:
            e.acceptProposedAction()
            self.procesar(rutas)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._anotar_normal()
        if self.capa.isVisible():
            self.capa.setGeometry(self.centralWidget().rect())

    # ---------- Cola y trabajo ----------

    def procesar(self, rutas, recursivo=True):
        """Lo soltado de una vez (vídeos sueltos, carpetas o ambos) es una sola búsqueda, como si todo
        estuviera en la misma carpeta. Va a la cola y empieza si no hay nada en marcha. Sin preguntas.
        Con `recursivo=False` (menú contextual › Solo esta carpeta), sin entrar en las subcarpetas."""
        self.cola.append((list(rutas), recursivo))
        if self.trabajador is None:
            self._siguiente()
        else:
            self.inicio.poner_cola(len(self.cola))

    def _siguiente(self):
        if not self.cola:
            self.trabajador = None
            self._actualizar_nav()
            self.en_reposo.emit()
            return
        lote, recursivo = self.cola.pop(0)
        ruta = lote[0] if len(lote) == 1 else lote
        self.inicio.poner_cola(len(self.cola))
        opciones = self.config.opciones       # las preferencias de este momento valen para toda la tanda
        if self.demo:
            t = TrabajadorDemo(ruta, self, recursivo=recursivo)
        else:
            t = Trabajador(ruta, opciones, credenciales_proveedores(self.config.usuario_opensubtitles),
                           recursivo=recursivo)
        self.trabajador = t

        # Solo se atiende a la búsqueda en curso: tras cancelar, pueden llegar avisos que el hilo envió
        # justo antes y que no deben tocar el resumen ni la búsqueda siguiente.
        def de_esta(funcion):
            return lambda *args: funcion(*args) if self.trabajador is t else None
        if not self.demo:
            t.error.connect(de_esta(self.inicio.al_error))
        t.inicio.connect(de_esta(self.inicio.al_iniciar))
        t.video.connect(de_esta(self.inicio.al_video))
        t.video.connect(de_esta(lambda i, total, _: self.progreso.emit(i, total)))
        t.detalle.connect(de_esta(self.inicio.al_detalle))
        t.resultado.connect(de_esta(self.inicio.al_resultado))
        t.terminado.connect(de_esta(self._terminado))
        self.inicio.empezar(lote, demo=self.demo, simulacion=opciones.dry_run, recursivo=recursivo)
        self.hay_busqueda = True
        self.paginas.setCurrentIndex(0)
        self.nav_botones[BUSCANDO].setChecked(True)
        self._actualizar_nav()
        self.trabajador.empezar()

    def _terminado(self, resultados, cancelado, segundos):
        anterior, self.trabajador = self.trabajador, None
        if self.demo and anterior is not None:
            anterior.deleteLater()
        # Con la búsqueda real, si se ha cancelado, el hilo puede seguir unos segundos terminando su
        # consulta a internet: ya no escribe nada ni avisa a la interfaz, y se cierra solo.
        self.inicio.terminar(resultados, cancelado, segundos)
        if cancelado:
            self.cola.clear()
            self.inicio.poner_cola(0)
        self.lote_terminado.emit(list(resultados), cancelado, list(self.inicio.errores))
        self._siguiente()

    def _cancelar(self):
        if self.trabajador:
            self.trabajador.cancelar()

    # ---------- Actualizaciones ----------

    def comprobar_actualizaciones(self):
        """Al arrancar: limpia descargas antiguas y, si toca, mira si hay una versión nueva."""
        actualizar.limpiar_descargas()
        if self.actualizador.toca():
            self.actualizador.comprobar()

    def _aviso_actualizada(self):
        """Si la app se acaba de actualizar, lo dice (una sola vez)."""
        previa, actual = actualizar.version(self.config.version), actualizar.version(__version__)
        if previa and actual and previa < actual:
            self._mostrar_aviso('actualizada', actualizar.Novedad(__version__, self._pagina_version(), ''))
        if self.config.version != __version__:
            self.config.version = __version__
            self.config.guardar()

    @staticmethod
    def _pagina_version():
        return f'{actualizar.PREFIJO_PAGINA}tag/v{__version__}'

    def _mostrar_aviso(self, estado, novedad=None, mensaje=''):
        self.aviso.poner(estado, novedad, mensaje)
        self.marco_aviso.show()

    def _ocultar_aviso(self):
        self.marco_aviso.hide()
        self.aviso.hide()

    def _novedad(self, novedad, manual):
        self.novedad = novedad
        v = actualizar.version_corta(novedad.version)
        self.ajustes.poner_estado_version(f'Hay una versión nueva: {v}.')
        if self.actualizador.descargando or self.aviso.estado == 'instalando':
            return
        if novedad.instalador and actualizar.instalada():
            self._mostrar_aviso('disponible', novedad)
        elif novedad.instalador:
            self._mostrar_aviso('portable', novedad, 'Estás usando la versión portable: descarga la nueva '
                                                     'desde su página en GitHub.')
        else:
            self._mostrar_aviso('portable', novedad)

    def _al_dia(self, manual):
        self.ajustes.poner_estado_version(f'Tienes la última versión ({VERSION}).')

    def _fallo_consulta(self, mensaje, manual):
        # La comprobación automática falla en silencio (sin internet, por ejemplo): ya se intentará otro día.
        self.ajustes.poner_estado_version(f'No se ha podido comprobar: {mensaje}' if manual
                                          else 'Comprueba ahora si hay una versión nueva.')

    def _actualizar(self):
        if self.novedad is None or self.trabajador is not None:
            return
        self._mostrar_aviso('descargando', self.novedad)
        self.actualizador.descargar(self.novedad)

    def _cancelar_descarga(self):
        self.actualizador.cancelar()
        if self.novedad:
            self._mostrar_aviso('disponible', self.novedad)

    def _fallo_descarga(self, mensaje):
        self._mostrar_aviso('error', self.novedad, mensaje)

    def _instalar(self, ruta):
        if self.trabajador is not None:        # no debería pasar: durante una búsqueda no se puede pulsar
            self._mostrar_aviso('disponible', self.novedad)
            return
        self._mostrar_aviso('instalando', self.novedad)
        try:
            actualizar.lanzar_instalador(ruta)
        except OSError as e:
            self._mostrar_aviso('error', self.novedad, f'No se ha podido abrir el instalador ({e.strerror or e}).')
            return
        self.close()                            # guarda la configuración; el instalador espera a que termine

    def _abrir_pagina_novedad(self):
        if self.novedad:
            QDesktopServices.openUrl(QUrl(self.novedad.pagina))

    def _abrir_pagina_version(self):
        QDesktopServices.openUrl(QUrl(self._pagina_version()))

    def closeEvent(self, e):
        if self.ocultar_al_cerrar and self.trabajador is not None:
            # Búsqueda en segundo plano: se vuelve al icono junto al reloj y sigue buscando.
            self._guardar_ventana()
            self.config.guardar()
            e.ignore()
            self.hide()
            return
        self.actualizador.cancelar()
        self._guardar_ventana()
        self.config.guardar()
        if self.trabajador:
            self.cola.clear()
            trabajador = self.trabajador
            trabajador.cancelar()
            if not self.demo:
                trabajador.esperar(2)    # un momento para que pare limpio; si no, se cierra igualmente
        super().closeEvent(e)
