"""Ventana principal: barra lateral, Inicio y Configuración, arrastre en toda la ventana y cola."""
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from subtitulos.archivos import es_video

from . import iconos, tema
from .componentes import IconoLabel, color
from .demo import TrabajadorDemo
from .vista_ajustes import VistaAjustes, resumen_preferencias
from .vista_inicio import VistaInicio

NOMBRE_APP = 'Bajar Subtítulos ESP'
VERSION = '0.2 · prototipo'


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
    """Capa semitransparente sobre toda la ventana mientras se arrastra algo encima."""

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
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), color('fondo', 0.96))
        r = QRectF(self.rect()).adjusted(20, 20, -20, -20)
        p.setPen(QPen(color('acento'), 2, Qt.DashLine))
        p.setBrush(color('acento_suave'))
        p.drawRoundedRect(r, 18, 18)
        c = r.center()
        p.setPen(Qt.NoPen)
        p.setBrush(color('acento'))
        p.drawEllipse(QRectF(c.x() - 42, c.y() - 90, 84, 84))
        iconos.dibujar(p, 'soltar', '#ffffff', QRectF(c.x() - 22, c.y() - 70, 44, 44))
        f = QFont(self.font())
        f.setFamilies(['Segoe UI Variable Display', 'Segoe UI'])
        f.setPointSizeF(17)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(color('texto'))
        p.drawText(QRectF(r.left(), c.y() + 10, r.width(), 36), Qt.AlignCenter, self.texto)
        f.setPointSizeF(10.5)
        f.setWeight(QFont.Normal)
        p.setFont(f)
        p.setPen(color('texto2'))
        p.drawText(QRectF(r.left(), c.y() + 48, r.width(), 26), Qt.AlignCenter, self.detalle)


class Ventana(QMainWindow):
    def __init__(self, preferencia_tema='sistema'):
        super().__init__()
        self.setWindowTitle(NOMBRE_APP)
        self.setWindowIcon(icono_app())
        self.setMinimumSize(880, 600)
        self.resize(1080, 720)
        self.setAcceptDrops(True)
        self.preferencia_tema = preferencia_tema
        self.cola = []
        self.trabajador = None

        raiz = QWidget()
        raiz.setObjectName('raiz')
        self.setCentralWidget(raiz)
        h = QHBoxLayout(raiz)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self._lateral())
        self.paginas = QStackedWidget()
        self.inicio = VistaInicio()
        self.ajustes = VistaAjustes()
        self.paginas.addWidget(self.inicio)
        self.paginas.addWidget(self.ajustes)
        h.addWidget(self.paginas, 1)
        self.capa = CapaArrastre(raiz)

        self.inicio.elegido.connect(self.procesar)
        self.inicio.cancelar.connect(self._cancelar)
        self.inicio.ir_ajustes.connect(lambda: self.ir(1))
        self.ajustes.cambiado.connect(self._preferencias_cambiadas)
        self.ajustes.tema_elegido.connect(self.cambiar_tema)
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._tema_sistema_cambiado)
        self._preferencias_cambiadas()
        self.refrescar()

    # ---------- Barra lateral ----------

    def _lateral(self):
        lat = QFrame()
        lat.setObjectName('lateral')
        lat.setFixedWidth(232)
        v = QVBoxLayout(lat)
        v.setContentsMargins(14, 18, 14, 14)
        v.setSpacing(4)
        marca = QHBoxLayout()
        marca.setContentsMargins(6, 0, 0, 0)
        marca.setSpacing(10)
        self.logo = QLabel()
        self.logo.setPixmap(icono_app().pixmap(34, 34))
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
        for i, (texto, ico) in enumerate((('Inicio', 'inicio'), ('Configuración', 'ajustes'))):
            b = QPushButton('  ' + texto)
            b.setObjectName('nav')
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b._icono = ico
            self.nav.addButton(b, i)
            self.nav_botones.append(b)
            v.addWidget(b)
        self.nav_botones[0].setChecked(True)
        self.nav.idClicked.connect(self.ir)
        v.addStretch()
        ver = QLabel(f'Versión {VERSION}')
        ver.setObjectName('version')
        v.addWidget(ver)
        return lat

    def ir(self, indice):
        self.nav_botones[indice].setChecked(True)
        self.paginas.setCurrentIndex(indice)

    # ---------- Tema ----------

    def cambiar_tema(self, preferencia):
        self.preferencia_tema = preferencia
        tema.aplicar(QApplication.instance(), preferencia)
        self.refrescar()

    def _tema_sistema_cambiado(self):
        if self.preferencia_tema == 'sistema':
            self.cambiar_tema('sistema')

    def refrescar(self):
        t = tema.actual()
        for b in self.nav_botones:
            b.setIcon(iconos.icono(b._icono, t['texto2'], 18))
        for ic in self.findChildren(IconoLabel):
            ic.refrescar()
        self.inicio.refrescar()
        self.ajustes.refrescar()
        self.update()
        for w in self.findChildren(QWidget):
            w.update()

    def _preferencias_cambiadas(self):
        o = self.ajustes.opciones()
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
        if self.capa.isVisible():
            self.capa.setGeometry(self.centralWidget().rect())

    # ---------- Cola y trabajo ----------

    def procesar(self, rutas):
        """Añade rutas a la cola y empieza si no hay nada en marcha. Sin preguntas."""
        self.cola.extend(rutas)
        self.ir(0)
        if self.trabajador is None:
            self._siguiente()
        else:
            self.inicio.poner_cola(len(self.cola))

    def _siguiente(self):
        if not self.cola:
            self.trabajador = None
            return
        ruta = self.cola.pop(0)
        self.inicio.poner_cola(len(self.cola))
        self.trabajador = TrabajadorDemo(ruta, self)
        self.trabajador.inicio.connect(self.inicio.al_iniciar)
        self.trabajador.video.connect(self.inicio.al_video)
        self.trabajador.detalle.connect(self.inicio.al_detalle)
        self.trabajador.resultado.connect(self.inicio.al_resultado)
        self.trabajador.terminado.connect(self._terminado)
        self.inicio.empezar(ruta, demo=True)
        self.trabajador.empezar()

    def _terminado(self, resultados, cancelado, segundos):
        self.inicio.terminar(resultados, cancelado, segundos)
        self.trabajador.deleteLater()
        self.trabajador = None
        if cancelado:
            self.cola.clear()
            self.inicio.poner_cola(0)
        self._siguiente()

    def _cancelar(self):
        if self.trabajador:
            self.trabajador.cancelar()
