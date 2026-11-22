"""Componentes propios de la interfaz, pintados a mano para que se vean igual en Windows 10 y 11."""
import re

from PySide6.QtCore import (QAbstractTableModel, QEasingCurve, QModelIndex, QPropertyAnimation, QRectF,
                            QSize, QSortFilterProxyModel, Qt, Property, QVariantAnimation)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractButton, QHBoxLayout, QLabel, QSizePolicy, QStyle,
                               QStyledItemDelegate, QVBoxLayout, QWidget)

from subtitulos import idioma
from subtitulos.idioma import N_, tr

from . import iconos, tema


def color(clave, alfa=None):
    c = QColor(tema.actual()[clave] if not clave.startswith('#') else clave)
    if alfa is not None:
        c.setAlphaF(alfa)
    return c


class IconoLabel(QLabel):
    """QLabel con un icono que se vuelve a pintar al cambiar de tema."""

    def __init__(self, nombre, clave_color='texto2', tam=20, parent=None):
        super().__init__(parent)
        self.nombre, self.clave_color, self.tam_base = nombre, clave_color, tam
        self.refrescar()

    def poner(self, nombre=None, clave_color=None):
        self.nombre = nombre or self.nombre
        self.clave_color = clave_color or self.clave_color
        self.refrescar()

    def refrescar(self):
        tam = tema.px(self.tam_base)
        self.setFixedSize(tam, tam)
        c = self.clave_color if self.clave_color.startswith('#') else tema.actual()[self.clave_color]
        self.setPixmap(iconos.pixmap(self.nombre, c, tam, self.devicePixelRatioF() or 2.0))


# ---------- Interruptor estilo Windows 11 ----------

class Interruptor(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(44, 22)
        self._avance = 0.0   # 0 = apagado, 1 = encendido (posición de la bolita)
        # Ojo: no llamar 'pos' a esta propiedad: en Qt 'pos' es la posición del widget y la
        # animación movía el interruptor entero.
        self._anim = QPropertyAnimation(self, b'avance', self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animar)

    def _get_avance(self):
        return self._avance

    def _set_avance(self, v):
        self._avance = v
        self.update()

    avance = Property(float, _get_avance, _set_avance)

    def _animar(self, activo):
        self._anim.stop()
        self._anim.setEndValue(1.0 if activo else 0.0)
        self._anim.start()

    def setChecked(self, activo):
        super().setChecked(activo)
        self._anim.stop()
        self._set_avance(1.0 if activo else 0.0)

    def sizeHint(self):
        return QSize(44, 22)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        activo = self.isChecked()
        if activo:
            p.setPen(Qt.NoPen)
            p.setBrush(color('acento') if self.isEnabled() else color('borde_fuerte'))
        else:
            p.setPen(QPen(color('texto2') if self.isEnabled() else color('borde_fuerte'), 1))
            p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = 12 if (self.underMouse() and self.isEnabled()) else 10
        x = r.left() + 5 + self._avance * (r.width() - 10 - d)
        cx = x + d / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#ffffff') if activo else color('texto2'))
        p.drawEllipse(QRectF(cx - d / 2, r.center().y() - d / 2, d, d))

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


class FilaOpcion(QWidget):
    """Título, explicación y un control a la derecha (un Interruptor por defecto)."""

    def __init__(self, titulo, explicacion='', control=None, parent=None):
        super().__init__(parent)
        self.control = control or Interruptor()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(16)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        t = QLabel(titulo)
        t.setWordWrap(True)
        textos.addWidget(t)
        if explicacion:
            e = QLabel(explicacion)
            e.setObjectName('ayuda')
            e.setWordWrap(True)
            textos.addWidget(e)
        lay.addLayout(textos, 1)
        lay.addWidget(self.control, 0, Qt.AlignVCenter)


# ---------- Resumen: tarjetas de contador y barra segmentada ----------

class TarjetaContador(QAbstractButton):
    """Contador de una categoría del resumen. Al pulsarla, filtra la tabla. Crece con el texto."""

    def __init__(self, categoria, parent=None):
        super().__init__(parent)
        self.categoria = categoria
        self.valor = 0
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setToolTip(f'{tema.explicacion_estado(categoria)}.\n' + tr('Pulsa para ver solo estos vídeos.'))
        self.ajustar()

    def ajustar(self):
        """Tamaño según la escala del texto (se llama también al cambiarla)."""
        self.setMinimumSize(tema.px(118), tema.px(78))
        self.setFixedHeight(tema.px(78))
        self.updateGeometry()

    def sizeHint(self):
        return QSize(tema.px(140), tema.px(78))

    def poner(self, valor):
        self.valor = valor
        self.update()

    def paintEvent(self, _):
        px = tema.px
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c_estado = QColor(tema.color_estado(self.categoria))
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        fondo = color('superficie_hover') if self.underMouse() and not self.isChecked() else color('superficie')
        if self.isChecked():
            tinte = QColor(c_estado)
            tinte.setAlphaF(0.12 if tema.oscuro() else 0.08)
            p.setBrush(color('superficie'))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(r, 12, 12)
            fondo = tinte
        p.setBrush(fondo)
        p.setPen(QPen(c_estado if self.isChecked() else color('borde'), 1.5 if self.isChecked() else 1))
        p.drawRoundedRect(r, 12, 12)
        # icono + nombre
        iconos.dibujar(p, tema.icono_estado(self.categoria), c_estado.name(), QRectF(px(14), px(13), px(16), px(16)))
        f = tema.fuente(self.font(), 9)
        p.setFont(f)
        p.setPen(color('texto2'))
        ancho = self.width() - px(46)
        nombre = QFontMetrics(f).elidedText(tema.nombre_estado(self.categoria), Qt.ElideRight, ancho)
        p.drawText(QRectF(px(36), px(10), ancho, px(22)), Qt.AlignVCenter | Qt.AlignLeft, nombre)
        # número
        p.setFont(tema.fuente(self.font(), 19, QFont.DemiBold, titulo=True))
        p.setPen(color('texto'))
        p.drawText(QRectF(px(14), px(32), self.width() - px(28), px(38)), Qt.AlignVCenter | Qt.AlignLeft,
                   str(self.valor))

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


class BarraSegmentada(QWidget):
    """Proporción de cada categoría: una barra fina de 8 px, con huecos de 2 px entre partes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.partes = []
        self.setFixedHeight(8)

    def poner(self, conteos):
        self.partes = [(cat, n) for cat, n in conteos if n]
        self.setToolTip(' · '.join(f'{tema.nombre_estado(c)}: {n}' for c, n in self.partes))
        self.update()

    def paintEvent(self, _):
        total = sum(n for _, n in self.partes)
        if not total:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        hueco = 2
        ancho = self.width() - hueco * (len(self.partes) - 1)
        x = 0.0
        recorte = QPainterPath()
        recorte.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 4, 4)
        p.setClipPath(recorte)
        p.setPen(Qt.NoPen)
        for cat, n in self.partes:
            w = ancho * n / total
            p.setBrush(QColor(tema.color_estado(cat)))
            p.drawRoundedRect(QRectF(x, 0, max(w, 2), self.height()), 2, 2)
            x += w + hueco


class BarraProgreso(QWidget):
    """Barra de progreso fina. En modo 'trabajando' (sin total conocido, o un solo vídeo) un tramo
    se desliza de un lado a otro para que se vea que la app sigue trabajando."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(6)
        self.valor, self.maximo = 0, 1
        self.trabajando = False
        self._fase = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(1400)
        self._anim.setLoopCount(-1)
        self._anim.setEasingCurve(QEasingCurve.InOutSine)
        self._anim.valueChanged.connect(self._mover)

    def _mover(self, v):
        self._fase = v
        self.update()

    def poner_trabajando(self, activo=True):
        self.trabajando = activo
        if activo:
            self._anim.start()
        else:
            self._anim.stop()
        self.update()

    def poner(self, valor, maximo):
        self.valor, self.maximo = valor, max(1, maximo)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        radio = self.height() / 2
        p.setPen(Qt.NoPen)
        p.setBrush(color('pista'))
        p.drawRoundedRect(r, radio, radio)
        p.setBrush(color('acento'))
        if self.trabajando:
            tramo = self.width() * 0.28
            x = -tramo + (self.width() + tramo) * self._fase
            recorte = QPainterPath()
            recorte.addRoundedRect(r, radio, radio)
            p.setClipPath(recorte)
            p.drawRoundedRect(QRectF(x, 0, tramo, self.height()), radio, radio)
        elif self.valor > 0:
            p.drawRoundedRect(QRectF(0, 0, self.width() * min(1.0, self.valor / self.maximo), self.height()),
                              radio, radio)


# ---------- Tabla de vídeos ----------

_IDIOMAS_EN = re.compile(r'\b(spain|spanish|english|latin american)\b', re.IGNORECASE)


def estado_legible(estado):
    """'CASTELLANO (incrustado)' -> 'Castellano (incrustado)'; 'ya tenía castellano' -> 'Ya tenía castellano'.
    En inglés, los nombres de idioma siguen en mayúscula: 'SPANISH FROM SPAIN (embedded)' -> 'Spanish from Spain (embedded)'."""
    texto = estado[:1].upper() + estado[1:].lower()
    if idioma.actual() == 'en':
        texto = _IDIOMAS_EN.sub(lambda m: m.group(0).title(), texto)
        texto = texto[:1].upper() + texto[1:]
    return texto


class Fila:
    """Un vídeo de la tabla: empieza 'En espera', pasa a 'Buscando…' y acaba con su resultado."""
    __slots__ = ('video', 'categoria', 'estado', 'fuente', 'resultado')

    def __init__(self, video):
        self.video = video
        self.categoria = tema.EN_ESPERA
        self.estado = tema.nombre_estado(tema.EN_ESPERA)
        self.fuente = ''
        self.resultado = None

    @property
    def nombre(self):
        return self.video.name


class ModeloResultados(QAbstractTableModel):
    """Todos los vídeos de la búsqueda desde el principio; cada fila cambia de estado al revisarse."""
    COLUMNAS = (N_('Estado'), N_('Vídeo'), N_('Origen'))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.filas = []
        self._indice = {}

    @property
    def resultados(self):
        return [f.resultado for f in self.filas if f.resultado is not None]

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.filas)

    def columnCount(self, parent=QModelIndex()):
        return 3

    def headerData(self, seccion, orientacion, rol=Qt.DisplayRole):
        if orientacion == Qt.Horizontal and rol == Qt.DisplayRole:
            return tr(self.COLUMNAS[seccion]).upper()
        return None

    def data(self, indice, rol=Qt.DisplayRole):
        f = self.filas[indice.row()]
        col = indice.column()
        if rol == Qt.DisplayRole:
            return (f.estado, f.nombre, '' if f.fuente == '-' else f.fuente)[col]
        if rol == Qt.ToolTipRole:
            return str(f.video) if col == 1 else tema.explicacion_estado(f.categoria) if col == 0 else None
        if rol == Qt.UserRole:
            return f.categoria
        return None

    def vaciar(self):
        self.preparar([])

    def preparar(self, videos):
        """Lista completa de vídeos, todos 'En espera'."""
        self.beginResetModel()
        self.filas = [Fila(v) for v in videos]
        self._indice = {v: i for i, v in enumerate(videos)}
        self.endResetModel()

    def _cambiada(self, i):
        self.dataChanged.emit(self.index(i, 0), self.index(i, 2))

    def _fila(self, video):
        i = self._indice.get(video)
        if i is None:                   # no estaba en la lista (no debería pasar): se añade al final
            i = len(self.filas)
            self.beginInsertRows(QModelIndex(), i, i)
            self.filas.append(Fila(video))
            self._indice[video] = i
            self.endInsertRows()
        return i

    def buscando(self, video):
        """Marca el vídeo que se está revisando. Devuelve su número de fila."""
        i = self._fila(video)
        f = self.filas[i]
        f.categoria, f.estado = tema.BUSCANDO, tema.nombre_estado(tema.BUSCANDO)
        self._cambiada(i)
        return i

    def poner_resultado(self, r):
        i = self._fila(r.video)
        f = self.filas[i]
        f.categoria, f.estado, f.fuente, f.resultado = r.categoria, estado_legible(r.estado), r.fuente, r
        self._cambiada(i)
        return i

    def cerrar(self):
        """Al cancelar: lo que no llegó a revisarse queda como 'No revisado'."""
        for i, f in enumerate(self.filas):
            if f.resultado is None:
                f.categoria, f.estado = tema.NO_REVISADO, tr('No revisado')
                self._cambiada(i)


class FiltroCategorias(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.categorias = set()

    def poner(self, categorias):
        if hasattr(self, 'beginFilterChange'):     # Qt >= 6.10 (invalidateFilter está obsoleto)
            self.beginFilterChange()
            self.categorias = set(categorias)
            self.endFilterChange()
        else:
            self.categorias = set(categorias)
            self.invalidateFilter()

    def filterAcceptsRow(self, fila, padre):
        if not self.categorias:
            return True
        return self.sourceModel().index(fila, 0, padre).data(Qt.UserRole) in self.categorias


class DelegadoEstado(QStyledItemDelegate):
    """Etiqueta de estado: fondo tenue del color del estado, icono en color y texto en tinta normal."""

    def paint(self, p, opcion, indice):
        px = tema.px
        self.initStyleOption(opcion, indice)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        if opcion.state & QStyle.StateFlag.State_Selected:
            p.fillRect(opcion.rect, color('acento_suave'))
        categoria = indice.data(Qt.UserRole)
        c = QColor(tema.color_estado(categoria))
        texto = indice.data(Qt.DisplayRole)
        f = tema.fuente(opcion.font, 9)
        if categoria in (tema.EN_ESPERA, tema.NO_REVISADO):
            f.setItalic(True)
        fm = QFontMetrics(f)
        icono, hueco = px(14), px(8)
        ancho = min(fm.horizontalAdvance(texto) + icono + 3 * hueco + px(2), opcion.rect.width() - px(12))
        alto = px(24)
        r = QRectF(opcion.rect.left() + px(10), opcion.rect.center().y() - alto / 2 + 0.5, ancho, alto)
        tinte = QColor(c)
        tinte.setAlphaF(0.16 if tema.oscuro() else 0.11)
        p.setPen(Qt.NoPen)
        p.setBrush(tinte)
        p.drawRoundedRect(r, alto / 2, alto / 2)
        iconos.dibujar(p, tema.icono_estado(categoria), c.name(),
                       QRectF(r.left() + hueco, r.center().y() - icono / 2, icono, icono), 2.4)
        p.setFont(f)
        p.setPen(color('texto3') if categoria in (tema.EN_ESPERA, tema.NO_REVISADO) else color('texto'))
        izquierda = hueco + icono + px(5)
        p.drawText(r.adjusted(izquierda, 0, -hueco, 0), Qt.AlignVCenter | Qt.AlignLeft,
                   fm.elidedText(texto, Qt.ElideRight, int(r.width() - izquierda - hueco)))
        p.setPen(QPen(color('borde'), 1))
        p.drawLine(opcion.rect.bottomLeft(), opcion.rect.bottomRight())
        p.restore()

    def sizeHint(self, opcion, indice):
        s = super().sizeHint(opcion, indice)
        return QSize(s.width() + tema.px(40), tema.px(40))
