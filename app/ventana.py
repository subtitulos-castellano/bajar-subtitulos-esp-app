"""Ventana principal: barra lateral (Inicio, Buscando…, Configuración), arrastre en toda la ventana y cola."""
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from subtitulos.archivos import es_video

from . import iconos, tema
from .componentes import IconoLabel, color
from .credenciales import credenciales_proveedores
from .demo import TrabajadorDemo
from .trabajador import Trabajador
from .vista_ajustes import VistaAjustes, resumen_preferencias
from .vista_inicio import VistaInicio

NOMBRE_APP = 'Bajar Subtítulos ESP'
VERSION = '0.4'

INICIO, BUSCANDO, AJUSTES = range(3)


def icono_app():
    """Icono de la app: subtítulos blancos sobre un cuadrado redondeado azul."""
    ico = QIcon()
    for lado in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(lado, lado)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#2a78d6'))
        p.drawRoundedRect(QRectF(0, 0, lado, lado), lado * 0.22, lado * 0.22)
        m = lado * 0.18
        iconos.dibujar(p, 'subtitulos', '#ffffff', QRectF(m, m, lado - 2 * m, lado - 2 * m), 2.2)
        p.end()
        ico.addPixmap(pm)
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

        raiz = QWidget()
        raiz.setObjectName('raiz')
        self.setCentralWidget(raiz)
        h = QHBoxLayout(raiz)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self._lateral())
        self.paginas = QStackedWidget()
        self.inicio = VistaInicio()
        self.ajustes = VistaAjustes(config)
        self.paginas.addWidget(self.inicio)
        self.paginas.addWidget(self.ajustes)
        h.addWidget(self.paginas, 1)
        self.capa = CapaArrastre(raiz)

        self.inicio.elegido.connect(self.procesar)
        self.inicio.cancelar.connect(self._cancelar)
        self.inicio.ir_ajustes.connect(lambda: self.ir(AJUSTES))
        self.inicio.repetir.connect(self.procesar)
        self.ajustes.cambiado.connect(self._preferencias_cambiadas)
        self.ajustes.tema_elegido.connect(self.cambiar_tema)
        self.ajustes.tamano_elegido.connect(lambda: self.cambiar_tema(self.preferencia_tema))
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._tema_sistema_cambiado)
        self._preferencias_cambiadas()
        self.refrescar()
        self._restaurar_ventana()
        self._actualizar_nav()

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

    def _anotar_normal(self):
        if self.isVisible() and not (self.isMaximized() or self.isMinimized() or self.isFullScreen()):
            f = self.frameGeometry()
            self._normal = (f.x(), f.y(), self.width(), self.height())

    def moveEvent(self, e):
        super().moveEvent(e)
        self._anotar_normal()

    def _guardar_ventana(self):
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
        self.logo.setPixmap(icono_app().pixmap(px(34), px(34)))
        for b in self.nav_botones:
            b.setIcon(iconos.icono(b._icono, t['texto2'], px(18)))
        for ic in self.findChildren(IconoLabel):
            ic.refrescar()
        self.inicio.refrescar()
        self.ajustes.refrescar()
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

    def procesar(self, rutas):
        """Lo soltado de una vez (vídeos sueltos, carpetas o ambos) es una sola búsqueda, como si todo
        estuviera en la misma carpeta. Va a la cola y empieza si no hay nada en marcha. Sin preguntas."""
        self.cola.append(list(rutas))
        if self.trabajador is None:
            self._siguiente()
        else:
            self.inicio.poner_cola(len(self.cola))

    def _siguiente(self):
        if not self.cola:
            self.trabajador = None
            self._actualizar_nav()
            return
        lote = self.cola.pop(0)
        ruta = lote[0] if len(lote) == 1 else lote
        self.inicio.poner_cola(len(self.cola))
        opciones = self.config.opciones       # las preferencias de este momento valen para toda la tanda
        if self.demo:
            t = TrabajadorDemo(ruta, self)
        else:
            t = Trabajador(ruta, opciones, credenciales_proveedores(self.config.usuario_opensubtitles))
        self.trabajador = t

        # Solo se atiende a la búsqueda en curso: tras cancelar, pueden llegar avisos que el hilo envió
        # justo antes y que no deben tocar el resumen ni la búsqueda siguiente.
        def de_esta(funcion):
            return lambda *args: funcion(*args) if self.trabajador is t else None
        if not self.demo:
            t.error.connect(de_esta(self.inicio.al_error))
        t.inicio.connect(de_esta(self.inicio.al_iniciar))
        t.video.connect(de_esta(self.inicio.al_video))
        t.detalle.connect(de_esta(self.inicio.al_detalle))
        t.resultado.connect(de_esta(self.inicio.al_resultado))
        t.terminado.connect(de_esta(self._terminado))
        self.inicio.empezar(lote, demo=self.demo, simulacion=opciones.dry_run)
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
        self._siguiente()

    def _cancelar(self):
        if self.trabajador:
            self.trabajador.cancelar()

    def closeEvent(self, e):
        self._guardar_ventana()
        self.config.guardar()
        if self.trabajador:
            self.cola.clear()
            trabajador = self.trabajador
            trabajador.cancelar()
            if not self.demo:
                trabajador.esperar(2)    # un momento para que pare limpio; si no, se cierra igualmente
        super().closeEvent(e)
