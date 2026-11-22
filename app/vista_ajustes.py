"""Pantalla Configuración: las opciones de la CLI convertidas en preferencias que se guardan solas."""
import threading

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QFontMetrics
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from subtitulos.archivos import HOME
from subtitulos.opciones import MAX_DESCARGAS, MAX_VIDEOS, Opciones

from . import __version__, actualizar, credenciales, iconos, menu_contextual, tema
from .config import TAMANO_MAX, TAMANO_MIN
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


class _Prueba(QObject):
    """Recibe en el hilo de la ventana el resultado de 'Probar conexión' (que usa la red)."""
    hecha = Signal(bool, str)


class VistaAjustes(QWidget):
    cambiado = Signal()            # cambiaron las opciones (ya guardadas)
    tema_elegido = Signal(str)     # 'sistema' | 'claro' | 'oscuro'
    tamano_elegido = Signal()      # cambió el tamaño del texto (ya guardado)
    buscar_actualizacion = Signal()  # 'Buscar ahora'

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
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
        lay.addWidget(etiqueta('Los cambios se guardan al momento y se usan en la siguiente búsqueda.',
                               'subtitulo'))
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
        lay.addWidget(self._cuenta())
        lay.addSpacing(12)

        # Apariencia y copias
        t = Tarjeta('restaurar', 'Apariencia y copias de seguridad')
        temas = QWidget()
        tl = QHBoxLayout(temas)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)
        self.grupo_tema = QButtonGroup(self)
        self.botones_tema = {}
        for i, (clave, texto) in enumerate((('sistema', 'Sistema'), ('claro', 'Claro'), ('oscuro', 'Oscuro'))):
            b = QPushButton(texto)
            b.setCheckable(True)
            b.setObjectName('segmento')
            b.setProperty('pos', ('ini', 'medio', 'fin')[i])
            b.setCursor(Qt.PointingHandCursor)
            b.clave = clave
            self.grupo_tema.addButton(b)
            self.botones_tema[clave] = b
            tl.addWidget(b)
        self.grupo_tema.buttonClicked.connect(self._tema)
        t.fila(FilaOpcion('Tema', 'Claro, oscuro o el mismo que Windows.', temas))
        t.fila(self._fila_tamano())
        b_copias = boton('Abrir carpeta')
        b_copias.clicked.connect(self._abrir_copias)
        t.fila(FilaOpcion('Copias de seguridad',
                          f'Copia de cada subtítulo sustituido, en {HOME / "backup"} '
                          '(la misma carpeta que usa la skill).', b_copias))
        lay.addWidget(t)
        lay.addSpacing(12)

        # Menú contextual del Explorador
        lay.addWidget(self._menu_contextual())
        lay.addSpacing(12)

        # Actualizaciones
        lay.addWidget(self._actualizaciones())
        lay.addSpacing(16)

        pie = QHBoxLayout()
        self.b_restaurar = boton('  Restaurar valores por defecto', 'restaurar')
        self.b_restaurar.clicked.connect(self.restaurar)
        pie.addWidget(self.b_restaurar)
        pie.addStretch()
        lay.addLayout(pie)
        lay.addStretch()

        self._poner_opciones(config.opciones)
        self.botones_tema.get(config.tema, self.botones_tema['sistema']).setChecked(True)
        for c in (self.latino, self.ingles, self.ingles_extra, self.force, self.simulacion):
            c.toggled.connect(self._opciones_cambiadas)
        self.max_videos.cambiado.connect(self._opciones_cambiadas)
        self.max_descargas.cambiado.connect(self._opciones_cambiadas)

    # ---------- Opciones ----------

    def _poner_opciones(self, o):
        self._cargando = True
        self.latino.setChecked(not o.solo_castellano)
        self.ingles.setChecked(not o.sin_ingles)
        self.ingles_extra.setChecked(o.ingles)
        self.force.setChecked(o.force)
        self.simulacion.setChecked(o.dry_run)
        self.max_videos.poner(o.max_videos)
        self.max_descargas.poner(o.max_descargas)
        self._cargando = False

    def opciones(self):
        return Opciones(force=self.force.isChecked(), solo_castellano=not self.latino.isChecked(),
                        sin_ingles=not self.ingles.isChecked(), ingles=self.ingles_extra.isChecked(),
                        dry_run=self.simulacion.isChecked(), max_videos=self.max_videos.valor(),
                        max_descargas=self.max_descargas.valor())

    def _opciones_cambiadas(self):
        if self._cargando:
            return
        self.config.opciones = self.opciones()
        self.config.guardar()
        self.cambiado.emit()

    def restaurar(self):
        self._poner_opciones(Opciones())
        self._opciones_cambiadas()

    def _tema(self, b):
        self.config.tema = b.clave
        self.config.guardar()
        self.tema_elegido.emit(b.clave)

    # ---------- Tamaño del texto ----------

    def _fila_tamano(self):
        control = QWidget()
        cl = QHBoxLayout(control)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(12)
        segmentos = QWidget()
        sl = QHBoxLayout(segmentos)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)
        self.grupo_tamano = QButtonGroup(self)
        self.b_tamano_windows = QPushButton('Como Windows')
        self.b_tamano_propio = QPushButton('Personalizado')
        for i, b in enumerate((self.b_tamano_windows, self.b_tamano_propio)):
            b.setCheckable(True)
            b.setObjectName('segmento')
            b.setProperty('pos', ('ini', 'fin')[i])
            b.setCursor(Qt.PointingHandCursor)
            self.grupo_tamano.addButton(b, i)
            sl.addWidget(b)
        cl.addWidget(segmentos)
        self.tamano = QSpinBox()
        self.tamano.setRange(TAMANO_MIN, TAMANO_MAX)
        self.tamano.setSingleStep(5)
        self.tamano.setSuffix(' %')
        self.tamano.setAlignment(Qt.AlignRight)
        self.tamano.setFixedWidth(tema.px(84))
        cl.addWidget(self.tamano)
        propio = self.config.tamano_texto
        (self.b_tamano_propio if propio else self.b_tamano_windows).setChecked(True)
        self.tamano.setValue(propio or tema.escala_windows())
        self.tamano.setEnabled(bool(propio))
        # Se aplica un instante después de dejar de teclear o girar la rueda (rehacer estilos cuesta algo).
        self._espera_tamano = QTimer(self)
        self._espera_tamano.setSingleShot(True)
        self._espera_tamano.setInterval(400)
        self._espera_tamano.timeout.connect(self._aplicar_tamano)
        self.grupo_tamano.idClicked.connect(self._modo_tamano)
        self.tamano.valueChanged.connect(lambda _: self._espera_tamano.start())
        self.fila_tamano = FilaOpcion('Tamaño del texto',
                                      'Como Windows: el de Configuración de Windows › Accesibilidad › Tamaño '
                                      'del texto. Si lo cambias allí, la app se ajusta al volver a ella.',
                                      control)
        return self.fila_tamano

    def _modo_tamano(self, i):
        propio = i == 1
        self.tamano.setEnabled(propio)
        if not propio:
            self.tamano.blockSignals(True)
            self.tamano.setValue(tema.escala_windows())
            self.tamano.blockSignals(False)
        self._aplicar_tamano()

    def _aplicar_tamano(self):
        nuevo = self.tamano.value() if self.b_tamano_propio.isChecked() else 0
        if nuevo != self.config.tamano_texto:
            self.config.tamano_texto = nuevo
            self.config.guardar()
            self.tamano_elegido.emit()

    def _texto_tamano(self):
        windows = tema.escala_windows()
        self.b_tamano_windows.setText(f'Como Windows ({windows} %)')
        if not self.b_tamano_propio.isChecked():
            self.tamano.blockSignals(True)
            self.tamano.setValue(windows)
            self.tamano.blockSignals(False)
        self.tamano.setFixedWidth(tema.px(84))

    def _abrir_copias(self):
        carpeta = HOME / 'backup'
        carpeta.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(carpeta)))

    # ---------- Menú contextual ----------

    def _menu_contextual(self):
        t = Tarjeta('menu', 'Menú contextual del Explorador',
                    'Busca subtítulos con el botón derecho del ratón, sin abrir antes la app. En Windows 11 '
                    'está dentro de «Mostrar más opciones».')
        fila = t.fila(FilaOpcion('Mostrar «Bajar subtítulos» en el menú contextual',
                                 'En una carpeta: «Bajar subtítulos aquí», solo en esa carpeta o también en sus '
                                 'subcarpetas. En uno o varios vídeos: «Bajar subtítulos».'))
        self.menu = fila.control
        self.estado_menu = fila.findChild(QLabel, 'ayuda')
        self._texto_menu = self.estado_menu.text()
        modos = QWidget()
        ml = QHBoxLayout(modos)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)
        self.grupo_modo_menu = QButtonGroup(self)
        self.b_menu_ventana = QPushButton('Mostrar la ventana')
        self.b_menu_fondo = QPushButton('En segundo plano')
        for i, b in enumerate((self.b_menu_ventana, self.b_menu_fondo)):
            b.setCheckable(True)
            b.setObjectName('segmento')
            b.setProperty('pos', ('ini', 'fin')[i])
            b.setCursor(Qt.PointingHandCursor)
            self.grupo_modo_menu.addButton(b, i)
            ml.addWidget(b)
        self.fila_modo_menu = t.fila(FilaOpcion(
            'Al usarlo',
            'Mostrar la ventana: como al arrastrar a la app. En segundo plano: sin ventana; solo un icono junto '
            'al reloj mientras busca (para ver el progreso o cancelar) y un aviso con el resumen al terminar.',
            modos))
        (self.b_menu_fondo if self.config.menu_segundo_plano else self.b_menu_ventana).setChecked(True)
        self.grupo_modo_menu.idClicked.connect(self._modo_menu)
        if menu_contextual.disponible():
            self.menu.setChecked(menu_contextual.registrado())
        else:
            self.menu.setEnabled(False)
            self.estado_menu.setText('Solo en Windows.')
        self.menu.toggled.connect(self._menu)
        return t

    def _menu(self, activo):
        try:
            menu_contextual.registrar() if activo else menu_contextual.quitar()
        except OSError as e:
            self.menu.blockSignals(True)
            self.menu.setChecked(not activo)
            self.menu.blockSignals(False)
            self.estado_menu.setText(f'No se ha podido cambiar el menú contextual ({e.strerror or e}).')
            return
        self.estado_menu.setText(self._texto_menu)
        self.config.menu_contextual = activo
        self.config.guardar()

    def _modo_menu(self, i):
        self.config.menu_segundo_plano = i == 1
        self.config.guardar()

    # ---------- Actualizaciones ----------

    def _actualizaciones(self):
        t = Tarjeta('actualizar', 'Actualizaciones')
        fila = t.fila(FilaOpcion('Buscar actualizaciones automáticamente',
                                 'Al abrir la app, como mucho una vez al día, mira en GitHub si hay una versión '
                                 'nueva. Antes de instalar nada siempre te pregunta.'))
        self.auto_actualizar = fila.control
        self.auto_actualizar.setChecked(self.config.actualizaciones)
        self.auto_actualizar.toggled.connect(self._auto_actualizar)
        self.b_buscar_version = boton('Buscar ahora')
        self.b_buscar_version.clicked.connect(self._buscar_version)
        fila = t.fila(FilaOpcion(f'Versión instalada: {actualizar.version_corta(__version__)}',
                                 'Comprueba ahora si hay una versión nueva.', self.b_buscar_version))
        self.estado_version = fila.findChild(QLabel, 'ayuda')
        self.estado_version.setTextFormat(Qt.PlainText)
        return t

    def _auto_actualizar(self, activo):
        self.config.actualizaciones = activo
        self.config.guardar()

    def _buscar_version(self):
        self.b_buscar_version.setEnabled(False)
        self.estado_version.setText('Buscando en GitHub…')
        self.buscar_actualizacion.emit()

    def poner_estado_version(self, texto):
        self.b_buscar_version.setEnabled(True)
        self.estado_version.setText(texto)

    # ---------- Cuenta de OpenSubtitles ----------

    def _cuenta(self):
        t = Tarjeta('usuario', 'Cuenta de OpenSubtitles',
                    'Opcional, pero da más resultados. Es una cuenta de opensubtitles.org (no de .com). '
                    'La contraseña se guarda en el Administrador de credenciales de Windows, nunca en un archivo.')
        cuenta = QWidget()
        v = QVBoxLayout(cuenta)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        fila = QHBoxLayout()
        fila.setSpacing(10)
        self.usuario = QLineEdit(self.config.usuario_opensubtitles)
        self.usuario.setPlaceholderText('Usuario')
        self.clave = QLineEdit(credenciales.leer_clave(self.config.usuario_opensubtitles))
        self.clave.setPlaceholderText('Contraseña')
        self.clave.setEchoMode(QLineEdit.Password)
        for e in (self.usuario, self.clave):
            e.setAcceptDrops(False)
            e.textEdited.connect(self._cuenta_editada)
            fila.addWidget(e, 1)
        self.b_guardar = boton('Guardar', nombre='primario')
        self.b_guardar.clicked.connect(self._guardar_cuenta)
        self.b_probar = boton('Probar conexión')
        self.b_probar.clicked.connect(self._probar)
        fila.addWidget(self.b_guardar)
        fila.addWidget(self.b_probar)
        v.addLayout(fila)
        abajo = QHBoxLayout()
        self.estado_cuenta = etiqueta('', 'ayuda', envolver=True)
        abajo.addWidget(self.estado_cuenta, 1)
        self.b_importar = boton('Usar la cuenta de la skill', nombre='plano')
        self.b_importar.setToolTip(f'Importa {HOME / "credenciales.json"}')
        self.b_importar.clicked.connect(self._importar)
        abajo.addWidget(self.b_importar)
        v.addLayout(abajo)
        t.fila(cuenta)
        self._prueba = _Prueba(self)
        self._prueba.hecha.connect(self._prueba_hecha)
        self._actualizar_cuenta()
        return t

    def _actualizar_cuenta(self, mensaje=None):
        guardado = self.config.usuario_opensubtitles
        cambios = (self.usuario.text().strip() != guardado
                   or self.clave.text() != credenciales.leer_clave(guardado))
        self.b_guardar.setEnabled(cambios)
        self.b_probar.setEnabled(bool(self.usuario.text().strip() and self.clave.text()))
        skill = credenciales.credenciales_skill()
        self.b_importar.setVisible(bool(skill) and skill[0] != guardado)
        if mensaje is None:
            if cambios:
                mensaje = 'Hay cambios sin guardar.'
            elif guardado and credenciales.leer_clave(guardado):
                mensaje = f'Se usará la cuenta «{guardado}» en las búsquedas.'
            else:
                mensaje = 'Sin cuenta: se busca en Addic7ed, Gestdown y Subtitulamos.'
        self.estado_cuenta.setText(mensaje)

    def _cuenta_editada(self):
        self._actualizar_cuenta()

    def _guardar_cuenta(self):
        usuario, clave = self.usuario.text().strip(), self.clave.text()
        if not credenciales.guardar_clave(usuario, clave, self.config.usuario_opensubtitles):
            self._actualizar_cuenta('No se pudo guardar la contraseña en el Administrador de credenciales.')
            return
        self.config.usuario_opensubtitles = usuario if clave else ''
        self.config.guardar()
        self._actualizar_cuenta()

    def _importar(self):
        skill = credenciales.credenciales_skill()
        if skill:
            self.usuario.setText(skill[0])
            self.clave.setText(skill[1])
            self._guardar_cuenta()

    def _probar(self):
        usuario, clave = self.usuario.text().strip(), self.clave.text()
        self.b_probar.setEnabled(False)
        self.estado_cuenta.setText('Comprobando la conexión con opensubtitles.org…')

        def comprobar():
            ok, mensaje = credenciales.probar(usuario, clave)
            self._prueba.hecha.emit(ok, mensaje)

        threading.Thread(target=comprobar, name='probar-opensubtitles', daemon=True).start()

    def _prueba_hecha(self, ok, mensaje):
        self.b_probar.setEnabled(True)
        self.estado_cuenta.setText(('✓ ' if ok else '✗ ') + mensaje)

    # ---------- Tema ----------

    def refrescar(self):
        t = tema.actual()
        for ic in self.findChildren(IconoLabel):
            ic.refrescar()
        self.b_restaurar.setIcon(iconos.icono('restaurar', t['texto2'], tema.px(16)))
        self._texto_tamano()
        for lim in (self.max_videos, self.max_descargas):
            lim.numero.setFixedWidth(tema.px(84))
        # El segmento marcado va en negrita y Qt no lo tiene en cuenta al calcular el ancho: se reserva.
        negrita = tema.fuente(self.font(), 10, QFont.DemiBold)
        fm = QFontMetrics(negrita)
        for b in self.findChildren(QPushButton, 'segmento'):
            b.setMinimumWidth(fm.horizontalAdvance(b.text()) + tema.px(36))


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
