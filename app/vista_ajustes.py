"""Pantalla Configuración: las opciones de la CLI convertidas en preferencias.

Prototipo (Fase 2): los cambios se aplican en la sesión, pero todavía no se guardan en disco.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from subtitulos.opciones import MAX_DESCARGAS, MAX_VIDEOS, Opciones

from . import iconos, tema
from .componentes import FilaOpcion, IconoLabel
from .vista_inicio import MARGEN, boton, etiqueta


class Tarjeta(QFrame):
    """Grupo de opciones con título e icono, filas separadas por una línea fina."""

    def __init__(self, icono, titulo, explicacion='', parent=None):
        super().__init__(parent)
        self.setObjectName('tarjeta')
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 14, 0, 6)
        self.lay.setSpacing(0)
        cab = QHBoxLayout()
        cab.setContentsMargins(16, 0, 16, 6)
        cab.setSpacing(10)
        cab.addWidget(IconoLabel(icono, 'acento', 18))
        cab.addWidget(etiqueta(titulo, 'seccion'), 1)
        self.lay.addLayout(cab)
        if explicacion:
            e = etiqueta(explicacion, 'ayuda', envolver=True)
            e.setContentsMargins(44, 0, 16, 6)
            self.lay.addWidget(e)
        self._filas = 0

    def fila(self, widget):
        sep = QFrame()
        sep.setObjectName('separador')
        self.lay.addWidget(sep)
        self.lay.addWidget(widget)
        return widget


class Limite(QWidget):
    """Número con la casilla 'Sin límite'."""
    cambiado = Signal()

    def __init__(self, valor, maximo, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.numero = QSpinBox()
        self.numero.setRange(1, maximo)
        self.numero.setValue(valor)
        self.numero.setFixedWidth(84)
        self.numero.setAlignment(Qt.AlignRight)
        self.numero.setButtonSymbols(QSpinBox.NoButtons)
        self.sin = QCheckBox('Sin límite')
        lay.addWidget(self.numero)
        lay.addWidget(self.sin)
        self.sin.toggled.connect(lambda v: self.numero.setEnabled(not v))
        self.numero.valueChanged.connect(self.cambiado)
        self.sin.toggled.connect(self.cambiado)

    def valor(self):
        return 0 if self.sin.isChecked() else self.numero.value()

    def poner(self, valor):
        self.sin.setChecked(valor == 0)
        if valor:
            self.numero.setValue(valor)


class VistaAjustes(QWidget):
    cambiado = Signal()            # opciones o tema
    tema_elegido = Signal(str)     # 'sistema' | 'claro' | 'oscuro'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('pagina')
        exterior = QVBoxLayout(self)
        exterior.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        exterior.addWidget(scroll)
        cuerpo = QWidget()
        cuerpo.setObjectName('pagina')
        scroll.setWidget(cuerpo)
        lay = QVBoxLayout(cuerpo)
        lay.setContentsMargins(MARGEN, MARGEN - 4, MARGEN, MARGEN)
        lay.setSpacing(6)
        lay.addWidget(etiqueta('Configuración', 'titulo'))
        lay.addWidget(etiqueta('Los cambios se aplican al momento.', 'subtitulo'))
        lay.addSpacing(16)

        # Qué guardar
        t = Tarjeta('subtitulos', 'Qué subtítulos guardar',
                    'Siempre se prefiere castellano de España. Nunca se sustituye un subtítulo por otro peor.')
        self.latino = t.fila(FilaOpcion('Si no hay castellano, guardar latino',
                                        'El resumen lo marca como Latino para que sepas que no es castellano.')).control
        self.ingles = t.fila(FilaOpcion('Si no hay nada en español, guardar inglés',
                                        'Primero la pista inglesa del propio vídeo (mejor si es SDH); si no hay, '
                                        'de los proveedores.')).control
        self.ingles_extra = t.fila(FilaOpcion('Extraer también la pista inglesa incrustada',
                                              'Se guarda aparte como <vídeo>.en.srt, además del subtítulo '
                                              'principal.')).control
        lay.addWidget(t)
        lay.addSpacing(12)

        # Cómo trabajar
        t = Tarjeta('ajustes', 'Cómo trabajar')
        self.force = t.fila(FilaOpcion('Rehacer aunque ya haya castellano',
                                       'Vuelve a buscar en todos los vídeos. El subtítulo anterior se copia a la '
                                       'carpeta de copias de seguridad.')).control
        self.simulacion = t.fila(FilaOpcion('Modo simulación',
                                            'Muestra qué se haría, sin escribir ni renombrar ningún archivo.')).control
        lay.addWidget(t)
        lay.addSpacing(12)

        # Límites
        t = Tarjeta('escudo', 'Límites para no saturar a los proveedores',
                    'Los proveedores de subtítulos son servicios gratuitos. Sube estos límites solo si lo '
                    'necesitas: los vídeos que pasen del límite quedan como Pendientes para la siguiente vez.')
        self.max_videos = Limite(MAX_VIDEOS, 1000)
        t.fila(FilaOpcion('Vídeos que buscan en internet en cada tanda',
                          f'Por defecto, {MAX_VIDEOS}. Los que ya tienen castellano o lo traen dentro no cuentan.',
                          self.max_videos))
        self.max_descargas = Limite(MAX_DESCARGAS, 50)
        t.fila(FilaOpcion('Candidatos que se descargan por vídeo',
                          f'Por defecto, {MAX_DESCARGAS}. Se eligen los mejores, alternando proveedores.',
                          self.max_descargas))
        lay.addWidget(t)
        lay.addSpacing(12)

        # OpenSubtitles
        t = Tarjeta('usuario', 'Cuenta de OpenSubtitles',
                    'Opcional, pero da más resultados. Es una cuenta de opensubtitles.org (no de .com). '
                    'La contraseña se guardará en el Administrador de credenciales de Windows.')
        cuenta = QWidget()
        cl = QHBoxLayout(cuenta)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(10)
        self.usuario = QLineEdit()
        self.usuario.setPlaceholderText('Usuario')
        self.clave = QLineEdit()
        self.clave.setPlaceholderText('Contraseña')
        self.clave.setEchoMode(QLineEdit.Password)
        for e in (self.usuario, self.clave):
            e.setAcceptDrops(False)
            cl.addWidget(e, 1)
        self.b_probar = boton('Probar conexión')
        self.b_probar.setEnabled(False)
        self.b_probar.setToolTip('Disponible en la siguiente fase')
        cl.addWidget(self.b_probar)
        t.fila(cuenta)
        lay.addWidget(t)
        lay.addSpacing(12)

        # Apariencia y copias
        t = Tarjeta('restaurar', 'Apariencia y copias de seguridad')
        temas = QWidget()
        tl = QHBoxLayout(temas)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)
        self.grupo_tema = QButtonGroup(self)
        for i, (clave, texto) in enumerate((('sistema', 'Sistema'), ('claro', 'Claro'), ('oscuro', 'Oscuro'))):
            b = QPushButton(texto)
            b.setCheckable(True)
            b.setObjectName('segmento')
            b.setProperty('pos', ('ini', 'medio', 'fin')[i])
            b.setCursor(Qt.PointingHandCursor)
            b.clave = clave
            self.grupo_tema.addButton(b)
            tl.addWidget(b)
            if clave == 'sistema':
                b.setChecked(True)
        self.grupo_tema.buttonClicked.connect(lambda b: self.tema_elegido.emit(b.clave))
        t.fila(FilaOpcion('Tema', 'Claro, oscuro o el mismo que Windows.', temas))
        copias = QWidget()
        b_copias = boton('Abrir carpeta')
        b_copias.setEnabled(False)
        b_copias.setToolTip('Disponible en la siguiente fase')
        t.fila(FilaOpcion('Copias de seguridad',
                          'Copia de cada subtítulo sustituido, en %USERPROFILE%\\.subtitulos-esp\\backup '
                          '(la misma carpeta que usa la skill).', b_copias))
        del copias
        lay.addWidget(t)
        lay.addSpacing(16)

        pie = QHBoxLayout()
        self.b_restaurar = boton('  Restaurar valores por defecto', 'restaurar')
        self.b_restaurar.clicked.connect(self.restaurar)
        pie.addWidget(self.b_restaurar)
        pie.addStretch()
        lay.addLayout(pie)
        lay.addStretch()

        self.restaurar()
        for c in (self.latino, self.ingles, self.ingles_extra, self.force, self.simulacion):
            c.toggled.connect(self.cambiado)
        self.max_videos.cambiado.connect(self.cambiado)
        self.max_descargas.cambiado.connect(self.cambiado)

    def restaurar(self):
        o = Opciones()
        self.latino.setChecked(not o.solo_castellano)
        self.ingles.setChecked(not o.sin_ingles)
        self.ingles_extra.setChecked(o.ingles)
        self.force.setChecked(o.force)
        self.simulacion.setChecked(o.dry_run)
        self.max_videos.poner(o.max_videos)
        self.max_descargas.poner(o.max_descargas)
        self.cambiado.emit()

    def opciones(self):
        return Opciones(force=self.force.isChecked(), solo_castellano=not self.latino.isChecked(),
                        sin_ingles=not self.ingles.isChecked(), ingles=self.ingles_extra.isChecked(),
                        dry_run=self.simulacion.isChecked(), max_videos=self.max_videos.valor(),
                        max_descargas=self.max_descargas.valor())

    def refrescar(self):
        t = tema.actual()
        for ic in self.findChildren(IconoLabel):
            ic.refrescar()
        self.b_restaurar.setIcon(iconos.icono('restaurar', t['texto2'], 16))
        self.setStyleSheet(f'''
            QPushButton#segmento {{ border-radius: 0; padding: 6px 16px; margin: 0; }}
            QPushButton#segmento[pos="ini"] {{ border-top-left-radius: 6px; border-bottom-left-radius: 6px; }}
            QPushButton#segmento[pos="medio"] {{ border-left: none; border-right: none; }}
            QPushButton#segmento[pos="fin"] {{ border-top-right-radius: 6px; border-bottom-right-radius: 6px; }}
            QPushButton#segmento:checked {{ background: {t['acento']}; color: {t['acento_texto']};
                                            border-color: {t['acento']}; font-weight: 600; }}
        ''')


def resumen_preferencias(o):
    """Texto corto con las preferencias activas, para la pantalla Inicio."""
    partes = ['Latino si no hay castellano' if not o.solo_castellano else 'Solo castellano',
              'inglés como último recurso' if not o.sin_ingles else 'sin inglés']
    if o.ingles:
        partes.append('también .en.srt')
    if o.force:
        partes.append('rehacer todo')
    partes.append(f'máx. {o.max_videos} vídeos por tanda' if o.max_videos else 'sin límite de vídeos')
    return 'Preferencias: ' + ' · '.join(partes)
