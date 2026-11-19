"""Pantalla Inicio: zona de arrastre (reposo), progreso y resumen con colores."""
from collections import Counter
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QFontMetrics, QGuiApplication
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QPlainTextEdit,
                               QProgressBar, QPushButton, QStackedLayout, QTableView, QVBoxLayout, QWidget)

from subtitulos import eventos as ev
from subtitulos.texto import visible

from . import iconos, tema
from .componentes import (BarraSegmentada, DelegadoEstado, FiltroCategorias, IconoLabel, ModeloResultados,
                          TarjetaContador)

MARGEN = 32


def etiqueta(texto, nombre=None, envolver=False):
    l = QLabel(texto)
    if nombre:
        l.setObjectName(nombre)
    l.setWordWrap(envolver)
    return l


def boton(texto, icono=None, nombre=None):
    b = QPushButton(texto)
    if nombre:
        b.setObjectName(nombre)
    b.setCursor(Qt.PointingHandCursor)
    b._icono = icono
    return b


class Banner(QFrame):
    """Aviso discreto (simulación, prototipo)."""

    def __init__(self, icono, texto, parent=None):
        super().__init__(parent)
        self.setObjectName('banner')
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)
        self.icono = IconoLabel(icono, '#b07800', 16)
        lay.addWidget(self.icono)
        self.texto = etiqueta(texto, envolver=True)
        lay.addWidget(self.texto, 1)

    def refrescar(self):
        self.icono.poner(clave_color='#fab219' if tema.oscuro() else '#a86f00')


def tabla_resultados(modelo):
    t = QTableView()
    t.setModel(modelo)
    t.setItemDelegateForColumn(0, DelegadoEstado(t))
    t.setShowGrid(False)
    t.setSelectionBehavior(QTableView.SelectRows)
    t.setSelectionMode(QTableView.SingleSelection)
    t.verticalHeader().hide()
    t.verticalHeader().setDefaultSectionSize(40)
    t.setFocusPolicy(Qt.NoFocus)
    t.setWordWrap(False)
    t.setTextElideMode(Qt.ElideMiddle)
    h = t.horizontalHeader()
    h.setHighlightSections(False)
    h.setSectionResizeMode(0, QHeaderView.Fixed)
    h.setSectionResizeMode(1, QHeaderView.Stretch)
    h.setSectionResizeMode(2, QHeaderView.Interactive)
    t.setColumnWidth(0, 230)
    t.setColumnWidth(2, 230)
    h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    return t


class Detalles(QWidget):
    """Botón 'Detalles' plegable con el registro técnico (lo mismo que imprime la CLI)."""

    def __init__(self, documento=None, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.boton = boton('  Detalles', nombre='plano')
        self.boton.setCheckable(True)
        self.boton.toggled.connect(self._cambiar)
        fila = QHBoxLayout()
        fila.addWidget(self.boton)
        fila.addStretch()
        lay.addLayout(fila)
        self.log = QPlainTextEdit()
        self.log.setObjectName('log')
        self.log.setReadOnly(True)
        self.log.setAcceptDrops(False)
        self.log.setMaximumBlockCount(5000)
        self.log.setFixedHeight(170)
        if documento is not None:
            self.log.setDocument(documento)
        self.log.hide()
        lay.addWidget(self.log)
        self.refrescar()

    def _cambiar(self, abierto):
        self.log.setVisible(abierto)
        self.refrescar()

    def refrescar(self):
        self.boton.setIcon(iconos.icono('abajo' if self.boton.isChecked() else 'derecha', tema.actual()['texto2'], 16))


class VistaInicio(QWidget):
    elegido = Signal(list)       # rutas elegidas con los botones
    cancelar = Signal()
    ir_ajustes = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('pagina')
        self.modelo = ModeloResultados(self)
        self.filtro = FiltroCategorias(self)
        self.filtro.setSourceModel(self.modelo)
        self.pila = QStackedLayout(self)
        self.pila.addWidget(self._reposo())
        self.pila.addWidget(self._progreso())
        self.pila.addWidget(self._resumen())
        self.ruta_actual = None
        self.demo = False

    # ---------- Reposo ----------

    def _reposo(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(MARGEN, MARGEN - 4, MARGEN, MARGEN)
        lay.setSpacing(6)
        lay.addWidget(etiqueta('Bajar subtítulos', 'titulo'))
        lay.addWidget(etiqueta('Subtítulos en castellano de España para tus series y películas.', 'subtitulo'))
        lay.addSpacing(14)
        self.banner_sim = Banner('simulacion', 'Modo simulación activado: se mostrará qué se haría, '
                                               'pero no se escribirá ningún archivo.')
        self.banner_sim.hide()
        lay.addWidget(self.banner_sim)

        self.zona = QFrame()
        self.zona.setObjectName('zona')
        self.zona.setProperty('activa', False)
        z = QVBoxLayout(self.zona)
        z.setContentsMargins(24, 24, 24, 24)
        z.setSpacing(0)
        z.addStretch(3)
        self.zona_icono = IconoLabel('soltar', 'acento', 44)
        circulo = QFrame()
        circulo.setObjectName('circulo')
        circulo.setFixedSize(84, 84)
        cl = QVBoxLayout(circulo)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(self.zona_icono, 0, Qt.AlignCenter)
        z.addWidget(circulo, 0, Qt.AlignHCenter)
        z.addSpacing(18)
        self.zona_titulo = etiqueta('Arrastra aquí un vídeo o una carpeta', 'zonaTitulo')
        z.addWidget(self.zona_titulo, 0, Qt.AlignHCenter)
        z.addSpacing(6)
        self.zona_texto = etiqueta('Se buscan los subtítulos nada más soltarlo, sin preguntas. '
                                   'Las carpetas se revisan con todas sus subcarpetas.', 'zonaTexto')
        self.zona_texto.setAlignment(Qt.AlignCenter)
        z.addWidget(self.zona_texto, 0, Qt.AlignHCenter)
        z.addSpacing(20)
        botones = QHBoxLayout()
        botones.setSpacing(10)
        botones.addStretch()
        self.b_carpeta = boton('  Elegir carpeta…', 'carpeta')
        self.b_video = boton('  Elegir vídeo…', 'video')
        self.b_carpeta.clicked.connect(self._elegir_carpeta)
        self.b_video.clicked.connect(self._elegir_video)
        botones.addWidget(self.b_carpeta)
        botones.addWidget(self.b_video)
        botones.addStretch()
        z.addLayout(botones)
        z.addStretch(4)
        lay.addWidget(self.zona, 1)
        lay.addSpacing(12)

        fila = QHBoxLayout()
        fila.setSpacing(6)
        self.resumen_opciones = etiqueta('', 'resumenOpciones')
        fila.addWidget(self.resumen_opciones, 1)
        b = boton('Cambiar preferencias', nombre='plano')
        b.clicked.connect(self.ir_ajustes)
        fila.addWidget(b)
        lay.addLayout(fila)
        return w

    def poner_arrastrando(self, activo):
        self.zona.setProperty('activa', activo)
        self.zona.style().unpolish(self.zona)
        self.zona.style().polish(self.zona)
        self.zona_titulo.setText('Suelta para buscar subtítulos' if activo else 'Arrastra aquí un vídeo o una carpeta')

    def poner_preferencias(self, texto, simulacion):
        self.resumen_opciones.setText(texto)
        self.banner_sim.setVisible(simulacion)
        self.banner_sim_resumen.setVisible(simulacion)

    def _elegir_carpeta(self):
        ruta = QFileDialog.getExistingDirectory(self, 'Elegir carpeta con vídeos')
        if ruta:
            self.elegido.emit([Path(ruta)])

    def _elegir_video(self):
        rutas, _ = QFileDialog.getOpenFileNames(
            self, 'Elegir vídeos', '', 'Vídeos (*.mkv *.mp4 *.avi *.m4v *.mov *.wmv *.ts)')
        if rutas:
            self.elegido.emit([Path(r) for r in rutas])

    # ---------- Progreso ----------

    def _progreso(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(MARGEN, MARGEN - 4, MARGEN, MARGEN)
        lay.setSpacing(6)
        cab = QHBoxLayout()
        cab.addWidget(etiqueta('Buscando subtítulos…', 'titulo'), 1)
        self.b_cancelar = boton('  Cancelar', 'cerrar')
        self.b_cancelar.clicked.connect(self._pedir_cancelar)
        cab.addWidget(self.b_cancelar, 0, Qt.AlignVCenter)
        lay.addLayout(cab)
        self.p_ruta = etiqueta('', 'subtitulo')
        lay.addWidget(self.p_ruta)
        lay.addSpacing(14)
        self.banner_demo_p = Banner('simulacion', 'Prototipo: resultados de demostración. '
                                                  'Todavía no se busca ni se descarga nada.')
        lay.addWidget(self.banner_demo_p)
        lay.addSpacing(4)
        self.barra = QProgressBar()
        self.barra.setTextVisible(False)
        lay.addWidget(self.barra)
        fila = QHBoxLayout()
        self.p_estado = etiqueta('', 'secundario')
        fila.addWidget(self.p_estado, 1)
        self.p_cola_icono = IconoLabel('cola', 'texto3', 16)
        self.p_cola = etiqueta('', 'ayuda')
        fila.addWidget(self.p_cola_icono)
        fila.addWidget(self.p_cola)
        lay.addLayout(fila)
        lay.addSpacing(10)
        self.tabla_p = tabla_resultados(self.modelo)
        lay.addWidget(self.tabla_p, 1)
        lay.addSpacing(6)
        self.detalles_p = Detalles()
        lay.addWidget(self.detalles_p)
        self.poner_cola(0)
        return w

    def _pedir_cancelar(self):
        self.b_cancelar.setEnabled(False)
        self.b_cancelar.setText('  Cancelando…')
        self.cancelar.emit()

    def empezar(self, ruta, demo=False):
        self.ruta_actual = Path(ruta)
        self.demo = demo
        self.modelo.vaciar()
        self.detalles_p.log.clear()
        self.barra.setRange(0, 0)
        self.b_cancelar.setEnabled(True)
        self.b_cancelar.setText('  Cancelar')
        self.banner_demo_p.setVisible(demo)
        self.p_ruta.setText(self._ruta_corta(self.ruta_actual))
        self.p_estado.setText('Buscando vídeos…')
        self.pila.setCurrentIndex(1)

    def _ruta_corta(self, ruta):
        fm = QFontMetrics(self.p_ruta.font())
        return fm.elidedText(str(ruta), Qt.ElideMiddle, max(300, self.width() - 2 * MARGEN))

    def al_iniciar(self, videos):
        self.barra.setRange(0, max(1, len(videos)))
        self.barra.setValue(0)
        if not videos:
            self.p_estado.setText('No se ha encontrado ningún vídeo.')

    def al_video(self, indice, total, path):
        self.barra.setValue(indice - 1)
        self.p_estado.setText(f'Vídeo {indice} de {total}  ·  {visible(path.name)}')

    def al_detalle(self, linea):
        self.detalles_p.log.appendPlainText(linea[1:] if linea.startswith('\n') else linea)

    def al_resultado(self, r):
        self.modelo.anadir(r)
        self.tabla_p.scrollToBottom()

    def poner_cola(self, n):
        self.p_cola.setText(f'En cola: {n}')
        self.p_cola.setVisible(n > 0)
        self.p_cola_icono.setVisible(n > 0)

    # ---------- Resumen ----------

    def _resumen(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(MARGEN, MARGEN - 4, MARGEN, MARGEN)
        lay.setSpacing(6)
        cab = QHBoxLayout()
        cab.setSpacing(10)
        self.r_icono = IconoLabel('ok', tema.color_estado('castellano'), 30)
        cab.addWidget(self.r_icono, 0, Qt.AlignVCenter)
        self.r_titulo = etiqueta('Listo', 'titulo')
        cab.addWidget(self.r_titulo, 1)
        self.b_copiar = boton('  Copiar resumen', 'copiar')
        self.b_copiar.clicked.connect(self._copiar)
        self.b_abrir = boton('  Abrir carpeta', 'carpeta', 'primario')
        self.b_abrir.clicked.connect(self._abrir_carpeta)
        cab.addWidget(self.b_copiar, 0, Qt.AlignVCenter)
        cab.addWidget(self.b_abrir, 0, Qt.AlignVCenter)
        lay.addLayout(cab)
        self.r_sub = etiqueta('', 'subtitulo')
        lay.addWidget(self.r_sub)
        lay.addSpacing(14)
        self.banner_sim_resumen = Banner('simulacion', 'Simulación: no se ha escrito ningún archivo.')
        self.banner_sim_resumen.hide()
        lay.addWidget(self.banner_sim_resumen)
        self.banner_demo_r = Banner('simulacion', 'Prototipo: resultados de demostración. '
                                                  'Todavía no se busca ni se descarga nada.')
        lay.addWidget(self.banner_demo_r)
        lay.addSpacing(4)
        self.tarjetas_lay = QHBoxLayout()
        self.tarjetas_lay.setSpacing(10)
        self.tarjetas = {}
        for cat in tema.ORDEN_ESTADOS:
            t = TarjetaContador(cat)
            t.toggled.connect(self._filtrar)
            self.tarjetas[cat] = t
            self.tarjetas_lay.addWidget(t)
        lay.addLayout(self.tarjetas_lay)
        lay.addSpacing(10)
        self.segmentos = BarraSegmentada()
        lay.addWidget(self.segmentos)
        lay.addSpacing(14)
        self.tabla_r = tabla_resultados(self.filtro)
        lay.addWidget(self.tabla_r, 1)
        lay.addSpacing(6)
        pie = QHBoxLayout()
        self.detalles_r = Detalles(self.detalles_p.log.document())
        pie.addWidget(self.detalles_r, 1)
        self.r_pista = etiqueta('Arrastra otro vídeo o carpeta para seguir.', 'ayuda')
        pie.addWidget(self.r_pista, 0, Qt.AlignTop | Qt.AlignRight)
        lay.addLayout(pie)
        return w

    def terminar(self, resultados, cancelado, segundos):
        n = len(resultados)
        conteo = Counter(r.categoria for r in resultados)
        for cat, t in self.tarjetas.items():
            t.blockSignals(True)
            t.setChecked(False)
            t.blockSignals(False)
            t.poner(conteo.get(cat, 0))
            t.setVisible(conteo.get(cat, 0) > 0)
        self.filtro.poner([])
        self.segmentos.poner([(c, conteo.get(c, 0)) for c in tema.ORDEN_ESTADOS])
        self.segmentos.setVisible(n > 0)
        if cancelado:
            self.r_titulo.setText('Cancelado')
            self.r_icono.poner('igual', 'texto3')
        elif n == 0:
            self.r_titulo.setText('No hay vídeos')
            self.r_icono.poner('igual', 'texto3')
        else:
            buenos = conteo[ev.CASTELLANO] + conteo[ev.YA_CASTELLANO]
            self.r_titulo.setText('Listo' if buenos == n else 'Listo, con avisos')
            self.r_icono.poner('ok' if buenos == n else 'aviso',
                               tema.color_estado(ev.CASTELLANO if buenos == n else ev.LATINO))
        videos = f'{n} vídeo{"s" if n != 1 else ""} revisado{"s" if n != 1 else ""}'
        self.r_sub.setText(f'{videos} en {_duracion(segundos)}  ·  {self._ruta_corta(self.ruta_actual)}')
        self.banner_demo_r.setVisible(self.demo)
        self.b_abrir.setEnabled(n > 0)
        self.b_copiar.setEnabled(n > 0)
        self.pila.setCurrentIndex(2)

    def _filtrar(self):
        self.filtro.poner([c for c, t in self.tarjetas.items() if t.isChecked()])

    def _texto_resumen(self):
        filas = [f'{visible(r.estado):28} {visible(r.fuente):30} {visible(r.nombre)}' for r in self.modelo.filas]
        return '==== RESUMEN ====\n' + '\n'.join(filas)

    def _copiar(self):
        QGuiApplication.clipboard().setText(self._texto_resumen())
        self.b_copiar.setText('  Copiado')

    def _abrir_carpeta(self):
        if self.ruta_actual:
            carpeta = self.ruta_actual if self.ruta_actual.is_dir() else self.ruta_actual.parent
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(carpeta)))

    def mostrar_reposo(self):
        self.pila.setCurrentIndex(0)

    # ---------- Tema ----------

    def refrescar(self):
        for b in self.findChildren(QPushButton):
            if getattr(b, '_icono', None):
                clave = 'acento_texto' if b.objectName() == 'primario' else 'texto2'
                b.setIcon(iconos.icono(b._icono, tema.actual()[clave], 16))
        for d in (self.detalles_p, self.detalles_r):
            d.refrescar()
        for b in self.findChildren(Banner):
            b.refrescar()
        self.b_copiar.setText('  Copiar resumen')
        circulo = self.zona.findChild(QFrame, 'circulo')
        circulo.setStyleSheet(f'#circulo {{ background: {tema.actual()["acento_suave"]}; border-radius: 42px; }}')


def _duracion(segundos):
    segundos = int(round(segundos))
    if segundos < 60:
        return f'{segundos} s'
    m, s = divmod(segundos, 60)
    return f'{m} min {s} s' if s else f'{m} min'
