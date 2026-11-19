"""Componentes propios de la interfaz, pintados a mano para que se vean igual en Windows 10 y 11."""
from PySide6.QtCore import (QAbstractTableModel, QEasingCurve, QModelIndex, QPropertyAnimation, QRectF,
                            QSize, QSortFilterProxyModel, Qt, Property)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractButton, QHBoxLayout, QLabel, QSizePolicy, QStyle,
                               QStyledItemDelegate, QVBoxLayout, QWidget)

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
        self.nombre, self.clave_color, self.tam = nombre, clave_color, tam
        self.setFixedSize(tam, tam)
        self.refrescar()

    def poner(self, nombre=None, clave_color=None):
        self.nombre = nombre or self.nombre
        self.clave_color = clave_color or self.clave_color
        self.refrescar()

    def refrescar(self):
        c = self.clave_color if self.clave_color.startswith('#') else tema.actual()[self.clave_color]
        self.setPixmap(iconos.pixmap(self.nombre, c, self.tam, self.devicePixelRatioF() or 2.0))


# ---------- Interruptor estilo Windows 11 ----------

class Interruptor(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(44, 22)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b'pos', self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animar)

    def _get_pos(self):
        return self._pos

    def _set_pos(self, v):
        self._pos = v
        self.update()

    pos = Property(float, _get_pos, _set_pos)

    def _animar(self, activo):
        self._anim.stop()
        self._anim.setEndValue(1.0 if activo else 0.0)
        self._anim.start()

    def setChecked(self, activo):
        super().setChecked(activo)
        self._anim.stop()
        self._set_pos(1.0 if activo else 0.0)

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
        x = r.left() + 5 + self._pos * (r.width() - 10 - d) + (10 - d) / 2 + (d - 10) / 2
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
    """Contador de una categoría del resumen. Al pulsarla, filtra la tabla."""

    def __init__(self, categoria, parent=None):
        super().__init__(parent)
        self.categoria = categoria
        self.valor = 0
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(118, 78)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setToolTip(f'{tema.explicacion_estado(categoria)}.\nPulsa para ver solo estos vídeos.')

    def sizeHint(self):
        return QSize(140, 78)

    def poner(self, valor):
        self.valor = valor
        self.update()

    def paintEvent(self, _):
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
        iconos.dibujar(p, tema.icono_estado(self.categoria), c_estado.name(), QRectF(14, 13, 16, 16))
        f = QFont(self.font())
        f.setPointSizeF(9)
        p.setFont(f)
        p.setPen(color('texto2'))
        nombre = QFontMetrics(f).elidedText(tema.nombre_estado(self.categoria), Qt.ElideRight, self.width() - 46)
        p.drawText(QRectF(36, 10, self.width() - 46, 22), Qt.AlignVCenter | Qt.AlignLeft, nombre)
        # número
        f2 = QFont(self.font())
        f2.setFamilies(['Segoe UI Variable Display', 'Segoe UI'])
        f2.setPointSizeF(19)
        f2.setWeight(QFont.DemiBold)
        p.setFont(f2)
        p.setPen(color('texto'))
        p.drawText(QRectF(14, 32, self.width() - 28, 38), Qt.AlignVCenter | Qt.AlignLeft, str(self.valor))

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
        for i, (cat, n) in enumerate(self.partes):
            w = ancho * n / total
            p.setBrush(QColor(tema.color_estado(cat)))
            p.drawRoundedRect(QRectF(x, 0, max(w, 2), self.height()), 2, 2)
            x += w + hueco


# ---------- Tabla de resultados ----------

def estado_legible(estado):
    """'CASTELLANO (incrustado)' -> 'Castellano (incrustado)'; 'ya tenía castellano' -> 'Ya tenía castellano'."""
    return estado[:1].upper() + estado[1:].lower()


class ModeloResultados(QAbstractTableModel):
    COLUMNAS = ('Estado', 'Vídeo', 'Origen')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.filas = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.filas)

    def columnCount(self, parent=QModelIndex()):
        return 3

    def headerData(self, seccion, orientacion, rol=Qt.DisplayRole):
        if orientacion == Qt.Horizontal and rol == Qt.DisplayRole:
            return self.COLUMNAS[seccion].upper()
        return None

    def data(self, indice, rol=Qt.DisplayRole):
        r = self.filas[indice.row()]
        col = indice.column()
        if rol == Qt.DisplayRole:
            return (estado_legible(r.estado), r.nombre, '' if r.fuente == '-' else r.fuente)[col]
        if rol == Qt.ToolTipRole:
            return str(r.video) if col == 1 else None
        if rol == Qt.UserRole:
            return r.categoria
        if rol == Qt.UserRole + 1:
            return r
        return None

    def vaciar(self):
        self.beginResetModel()
        self.filas = []
        self.endResetModel()

    def anadir(self, resultado):
        self.beginInsertRows(QModelIndex(), len(self.filas), len(self.filas))
        self.filas.append(resultado)
        self.endInsertRows()


class FiltroCategorias(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.categorias = set()

    def poner(self, categorias):
        self.categorias = set(categorias)
        self.invalidateFilter()

    def filterAcceptsRow(self, fila, padre):
        if not self.categorias:
            return True
        return self.sourceModel().index(fila, 0, padre).data(Qt.UserRole) in self.categorias


class DelegadoEstado(QStyledItemDelegate):
    """Etiqueta de estado: fondo tenue del color del estado, icono en color y texto en tinta normal."""

    def paint(self, p, opcion, indice):
        self.initStyleOption(opcion, indice)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        if opcion.state & QStyle.StateFlag.State_Selected:
            p.fillRect(opcion.rect, color('acento_suave'))
        categoria = indice.data(Qt.UserRole)
        c = QColor(tema.color_estado(categoria))
        texto = indice.data(Qt.DisplayRole)
        f = QFont(opcion.font)
        f.setPointSizeF(9)
        fm = QFontMetrics(f)
        ancho = min(fm.horizontalAdvance(texto) + 36, opcion.rect.width() - 12)
        alto = 24
        r = QRectF(opcion.rect.left() + 10, opcion.rect.center().y() - alto / 2 + 0.5, ancho, alto)
        tinte = QColor(c)
        tinte.setAlphaF(0.16 if tema.oscuro() else 0.11)
        p.setPen(Qt.NoPen)
        p.setBrush(tinte)
        p.drawRoundedRect(r, alto / 2, alto / 2)
        iconos.dibujar(p, tema.icono_estado(categoria), c.name(), QRectF(r.left() + 8, r.top() + 5, 14, 14), 2.4)
        p.setFont(f)
        p.setPen(color('texto'))
        p.drawText(r.adjusted(27, 0, -8, 0), Qt.AlignVCenter | Qt.AlignLeft,
                   fm.elidedText(texto, Qt.ElideRight, int(r.width() - 35)))
        p.setPen(QPen(color('borde'), 1))
        p.drawLine(opcion.rect.bottomLeft(), opcion.rect.bottomRight())
        p.restore()

    def sizeHint(self, opcion, indice):
        s = super().sizeHint(opcion, indice)
        return QSize(s.width() + 40, 40)
