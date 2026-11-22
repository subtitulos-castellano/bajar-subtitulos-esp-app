"""Icono junto al reloj: búsquedas en segundo plano y app que sigue abierta al cerrar la ventana.

- Segundo plano (menú contextual con «En segundo plano» en Configuración): la ventana no se abre;
  mientras busca hay un icono junto al reloj (desde él se ve el progreso o se cancela) y, al terminar,
  un aviso de Windows con el resumen. Pulsar el aviso abre el resumen. Si no se pulsa, la app se cierra
  sola un minuto después (el icono hace falta para que el aviso responda).
- «Al cerrar la ventana, seguir junto al reloj» (Configuración): el icono está siempre; cerrar la
  ventana solo la oculta y la app sigue abierta hasta que se elige *Salir* en el icono. Si se cierra
  durante una búsqueda, sigue buscando y avisa al terminar, como en segundo plano.
"""
from collections import Counter

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from subtitulos import eventos as ev
from subtitulos.texto import visible

from . import tema

ESPERA_FINAL = 60_000      # ms que sigue el icono tras el aviso final, por si se pulsa
TITULO = 'Bajar Subtítulos ESP'


def resumen(resultados, cancelado, errores):
    """(título, texto) del aviso final."""
    n = len(resultados)
    conteo = Counter(r.categoria for r in resultados)
    if errores:
        return ('Se ha detenido por un error',
                f'{visible(errores[0])}. Lo que ya estaba hecho se ha guardado.')
    if cancelado:
        return 'Búsqueda cancelada', f'{n} vídeo{"s" if n != 1 else ""} revisado{"s" if n != 1 else ""} antes de cancelar.'
    if n == 0:
        return 'No hay vídeos', 'No se ha encontrado ningún vídeo.'
    buenos = conteo[ev.CASTELLANO] + conteo[ev.YA_CASTELLANO]
    titulo = 'Subtítulos listos' if buenos == n else 'Subtítulos listos, con avisos'
    partes = []
    for cat in tema.ORDEN_ESTADOS:
        if conteo.get(cat):
            nombre = tema.nombre_estado(cat)
            partes.append(f'{conteo[cat]} {nombre[0].lower()}{nombre[1:]}')
    texto = f'{n} vídeo{"s" if n != 1 else ""}: {", ".join(partes)}.'
    if conteo.get(ev.PENDIENTE):
        texto += '\nLos pendientes superan el límite por tanda: pulsa aquí y luego Procesar pendientes.'
    return titulo, texto


class Bandeja(QObject):
    def __init__(self, ventana, icono, salir, residente=None, parent=None):
        """`salir`: función que cierra la app. `residente`: función que dice si la app sigue junto al
        reloj al cerrar la ventana (la opción de Configuración)."""
        super().__init__(parent)
        self.ventana = ventana
        self.salir = salir
        self.residente = residente or (lambda: False)
        self.activa = False           # búsqueda en segundo plano (en marcha o con su aviso pendiente)
        self._reiniciar()
        self.icono = QSystemTrayIcon(icono, self)
        self.icono.setToolTip(TITULO)
        self.menu = QMenu()
        self.a_ver = self.menu.addAction('Abrir Bajar Subtítulos ESP')
        self.a_ver.triggered.connect(self.ver)
        self.a_cancelar = self.menu.addAction('Cancelar la búsqueda')
        self.a_cancelar.triggered.connect(self._cancelar)
        self.menu.addSeparator()
        self.a_salir = self.menu.addAction('Salir')
        self.a_salir.triggered.connect(self._salir)
        self.menu.aboutToShow.connect(self._preparar_menu)
        self.icono.setContextMenu(self.menu)
        self.icono.activated.connect(self._activado)
        self.icono.messageClicked.connect(self.ver)
        self._fin = QTimer(self)
        self._fin.setSingleShot(True)
        self._fin.setInterval(ESPERA_FINAL)
        self._fin.timeout.connect(self._terminar)
        ventana.progreso.connect(self._progreso)
        ventana.lote_terminado.connect(self._lote)
        ventana.en_reposo.connect(self._reposo)
        ventana.oculta.connect(self.en_bandeja)

    def _reiniciar(self):
        self.resultados, self.errores, self.cancelado = [], [], False

    def actualizar(self):
        """Muestra u oculta el icono: está mientras hay algo en segundo plano o con la opción activada."""
        self.icono.setVisible(self.activa or self.residente())

    def empezar(self):
        """Hay una búsqueda nueva en segundo plano (la ventana está oculta)."""
        if not self.activa:
            self._reiniciar()
        self.activa = True
        self._fin.stop()
        self.ventana.ocultar_al_cerrar = True
        self.icono.setToolTip(f'{TITULO}\nBuscando subtítulos…')
        self.icono.show()

    def en_bandeja(self):
        """Se ha cerrado la ventana y la app sigue: si estaba buscando, sigue en segundo plano."""
        if self.ventana.trabajador is not None and not self.activa:
            self.empezar()
        self.actualizar()

    def _preparar_menu(self):
        if self.ventana.trabajador is not None:
            self.a_ver.setText('Ver progreso')
        elif self.activa:
            self.a_ver.setText('Ver el resumen')
        else:
            self.a_ver.setText('Abrir Bajar Subtítulos ESP')
        self.a_cancelar.setVisible(self.ventana.trabajador is not None)

    def _progreso(self, indice, total):
        self.icono.setToolTip(f'{TITULO}\nBuscando subtítulos: vídeo {indice} de {total}')

    def _lote(self, resultados, cancelado, errores):
        if self.activa:
            self.resultados += resultados
            self.errores += errores
            self.cancelado = self.cancelado or cancelado

    def _reposo(self):
        """Ya no queda nada: si la ventana está a la vista no hace falta avisar."""
        self.icono.setToolTip(TITULO)
        if not self.activa:
            return
        if self.ventana.isVisible():
            self._apagar()
            return
        if self.cancelado and not self.errores:
            self._terminar()                   # lo ha cancelado el usuario: no hace falta aviso
            return
        titulo, texto = resumen(self.resultados, self.cancelado, self.errores)
        aviso = QSystemTrayIcon.Warning if self.errores else QSystemTrayIcon.Information
        self.icono.setToolTip(f'{TITULO}\n{titulo}')
        self.icono.showMessage(titulo, texto, aviso, 15000)
        self._fin.start()

    def _activado(self, motivo):
        if motivo in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.ver()

    def ver(self):
        """Abre la ventana con la búsqueda (en marcha o su resumen), o sin más si no hay ninguna."""
        from .ventana import BUSCANDO
        if self.activa and self.ventana.hay_busqueda:
            self.ventana.ir(BUSCANDO)
        self.ventana.traer_al_frente()
        if self.ventana.trabajador is None:
            self._apagar()

    def _cancelar(self):
        self.ventana._cancelar()

    def _salir(self):
        self._fin.stop()
        self.activa = False
        self.icono.hide()
        self.salir()

    def _apagar(self):
        """Fin del segundo plano (el icono sigue si la opción de seguir junto al reloj está activada)."""
        self._fin.stop()
        self.activa = False
        self.ventana.ocultar_al_cerrar = False
        self.icono.setToolTip(TITULO)
        self.actualizar()

    def _terminar(self):
        """Fin del segundo plano sin que se haya abierto la ventana: se cierra la app (salvo que deba
        seguir junto al reloj)."""
        self._apagar()
        if not self.ventana.isVisible() and not self.residente():
            self.salir()
