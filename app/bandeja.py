"""Búsquedas en segundo plano (menú contextual con «En segundo plano» en Configuración).

La ventana no se abre: mientras busca hay un icono junto al reloj (desde él se ve el progreso o se
cancela) y, al terminar, un aviso de Windows con el resumen. Pulsar el aviso abre el resumen. Si no se
pulsa, la app se cierra sola un minuto después (el icono hace falta para que el aviso responda).
"""
from collections import Counter

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from subtitulos import eventos as ev
from subtitulos.texto import visible

from . import tema

ESPERA_FINAL = 60_000      # ms que sigue el icono tras el aviso final, por si se pulsa


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
    def __init__(self, ventana, icono, salir, parent=None):
        """`salir`: función que cierra la app (cuando ya no queda nada que hacer)."""
        super().__init__(parent)
        self.ventana = ventana
        self.salir = salir
        self.activa = False
        self._reiniciar()
        self.icono = QSystemTrayIcon(icono, self)
        self.menu = QMenu()
        self.a_ver = self.menu.addAction('Ver progreso')
        self.a_ver.triggered.connect(self.ver)
        self.a_cancelar = self.menu.addAction('Cancelar la búsqueda')
        self.a_cancelar.triggered.connect(self._cancelar)
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

    def _reiniciar(self):
        self.resultados, self.errores, self.cancelado = [], [], False

    def empezar(self):
        """Hay una búsqueda nueva en segundo plano (la ventana está oculta)."""
        if not self.activa:
            self._reiniciar()
        self.activa = True
        self._fin.stop()
        self.ventana.ocultar_al_cerrar = True
        self.a_ver.setText('Ver progreso')
        self.a_cancelar.setEnabled(True)
        self.icono.setToolTip('Bajar Subtítulos ESP\nBuscando subtítulos…')
        self.icono.show()

    def _progreso(self, indice, total):
        if self.activa:
            self.icono.setToolTip(f'Bajar Subtítulos ESP\nBuscando subtítulos: vídeo {indice} de {total}')

    def _lote(self, resultados, cancelado, errores):
        if self.activa:
            self.resultados += resultados
            self.errores += errores
            self.cancelado = self.cancelado or cancelado

    def _reposo(self):
        """Ya no queda nada: si la ventana está a la vista no hace falta avisar."""
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
        self.icono.setToolTip(f'Bajar Subtítulos ESP\n{titulo}')
        self.a_ver.setText('Ver el resumen')
        self.a_cancelar.setEnabled(False)
        self.icono.showMessage(titulo, texto, aviso, 15000)
        self._fin.start()

    def _activado(self, motivo):
        if motivo in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.ver()

    def ver(self):
        """Abre la ventana con la búsqueda (en marcha o su resumen)."""
        from .ventana import BUSCANDO
        if self.ventana.hay_busqueda:
            self.ventana.ir(BUSCANDO)
        self.ventana.traer_al_frente()
        if self.ventana.trabajador is None:
            self._apagar()

    def _cancelar(self):
        self.ventana._cancelar()

    def _apagar(self):
        """Fin del segundo plano: la app sigue abierta con su ventana a la vista."""
        self._fin.stop()
        self.activa = False
        self.ventana.ocultar_al_cerrar = False
        self.icono.hide()

    def _terminar(self):
        """Fin del segundo plano sin que se haya abierto la ventana: se cierra la app."""
        self._apagar()
        if not self.ventana.isVisible():
            self.salir()
