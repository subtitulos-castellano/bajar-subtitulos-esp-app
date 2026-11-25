"""Una sola app abierta a la vez por usuario.

Con varios vídeos seleccionados, el Explorador abre la app una vez por vídeo, casi a la vez. La primera
que arranca se queda (se decide con un mutex de Windows o, en Linux, con un bloqueo de archivo) y abre
un canal local; las demás le mandan lo que han recibido y se cierran al momento. La primera junta lo que llega seguido (Agrupador) y lo
busca todo de una vez, como cuando se sueltan varios vídeos en la ventana.

Lo mismo si la app ya estaba abierta: lo nuevo va a su cola, y abrirla otra vez desde el menú Inicio
solo trae la ventana al frente.
"""
import getpass
import json
import os
import socket
import tempfile
import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QLocalServer

from .plataforma import LINUX, WINDOWS

MUTEX = 'Local\\BajarSubtitulosESP-instancia'
_mutex = None


def nombre_canal():
    """En Windows, una tubería con nombre; en Linux, un socket en la carpeta privada del usuario."""
    try:
        usuario = getpass.getuser()
    except Exception:  # noqa: BLE001 - sin usuario conocido: un nombre fijo
        usuario = 'usuario'
    nombre = 'BajarSubtitulosESP-' + ''.join(c for c in usuario if c.isalnum())[:40]
    if LINUX:
        from .plataforma import linux
        return str(linux.carpeta_ejecucion() / nombre)
    return nombre


def es_la_primera():
    """True si no hay otra app abierta por este usuario en esta sesión. El mutex (o el bloqueo, en
    Linux) dura lo que dure el proceso: el sistema lo suelta solo, aunque la app se cierre de golpe."""
    global _mutex
    if WINDOWS:
        from .plataforma import windows
        _mutex, existia = windows.crear_mutex(MUTEX)
        return not existia
    if LINUX:
        from .plataforma import linux
        _mutex = linux.bloquear(nombre_canal() + '.lock')
        return _mutex is not None       # False (no se ha podido comprobar): mejor abrirse
    return True


def soltar():
    """Deja de ser «la primera» antes de cerrarse para volver a abrirse (cambio de idioma): así la
    nueva apertura no le pasa el pedido a esta, que se está cerrando."""
    global _mutex
    if _mutex and WINDOWS:
        from .plataforma import windows
        windows.cerrar(_mutex)
    elif _mutex and LINUX:
        from .plataforma import linux
        linux.soltar(_mutex)
    _mutex = None


def permitir_primer_plano():
    """La app que ya está abierta puede ponerse delante (Windows solo deja hacerlo a quien tiene el
    foco, que es este proceso recién lanzado)."""
    if WINDOWS:
        from .plataforma import windows
        windows.permitir_primer_plano()


def enviar(pedido, segundos=10):
    """Manda el pedido a la app ya abierta. Reintenta un rato: puede estar arrancando aún. True si lo
    ha recibido (la otra app cierra la conexión en cuanto lo lee)."""
    if LINUX:
        from .plataforma import linux
        if linux.token_activacion():
            pedido = {**pedido, 'activacion': linux.token_activacion()}
    datos = (json.dumps(pedido, ensure_ascii=False) + '\n').encode('utf-8')
    fin = time.monotonic() + segundos
    while True:
        try:
            if WINDOWS:
                return _enviar_tuberia(datos)
            return _enviar_socket(datos)
        except OSError:
            pass                      # aún no escucha, o está atendiendo a otra apertura
        if time.monotonic() > fin:
            return False
        time.sleep(0.1)


def _enviar_tuberia(datos):
    """QLocalServer en Windows es una tubería con nombre: se escribe en ella como en un archivo."""
    with open(rf'\\.\pipe\{nombre_canal()}', 'r+b', buffering=0) as tuberia:
        tuberia.write(datos)
        try:
            tuberia.read(1)           # vuelve cuando la otra app cierra la conexión
        except OSError:
            pass                      # cerrada: también vale
    return True


def ruta_socket(nombre=None):
    """Dónde escucha QLocalServer fuera de Windows: la ruta tal cual si es absoluta; si no, en la carpeta
    temporal (como Qt)."""
    nombre = nombre or nombre_canal()
    return nombre if os.path.isabs(nombre) else os.path.join(tempfile.gettempdir(), nombre)


def _enviar_socket(datos):
    """QLocalServer fuera de Windows es un socket Unix. Sin Qt: así la apertura que solo pasa el pedido
    no necesita crear una aplicación Qt (ni conectarse a la pantalla)."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(3)
        s.connect(ruta_socket())
        s.sendall(datos)
        try:
            s.recv(1)                 # vuelve cuando la otra app cierra la conexión
        except OSError:
            pass                      # se ha agotado el tiempo: también vale, el pedido ya está enviado
    return True


class Servidor(QObject):
    """Recibe los pedidos de las demás aperturas."""
    pedido = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.servidor = QLocalServer(self)
        self.servidor.setSocketOptions(QLocalServer.UserAccessOption)   # solo este usuario
        self.servidor.newConnection.connect(self._conexion)
        self._buffers = {}

    def escuchar(self):
        nombre = nombre_canal()
        if not self.servidor.listen(nombre):
            QLocalServer.removeServer(nombre)       # resto de una app que se cerró de golpe (Linux)
            return self.servidor.listen(nombre)
        return True

    def cerrar(self):
        self.servidor.close()

    def _conexion(self):
        while self.servidor.hasPendingConnections():
            s = self.servidor.nextPendingConnection()
            self._buffers[s] = b''
            s.readyRead.connect(lambda s=s: self._leer(s))
            s.disconnected.connect(lambda s=s: (self._leer(s), self._buffers.pop(s, None), s.deleteLater()))
            if s.bytesAvailable():
                self._leer(s)

    def _leer(self, s):
        if s not in self._buffers:
            return
        datos = self._buffers[s] + bytes(s.readAll().data())
        if len(datos) > 1_000_000:                  # nadie manda tanto: se corta
            self._buffers[s] = b''
            s.abort()
            return
        self._buffers[s] = datos
        if b'\n' not in datos:
            return
        linea = datos.split(b'\n', 1)[0]
        del self._buffers[s]
        s.disconnectFromServer()
        try:
            pedido = json.loads(linea.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            return
        if isinstance(pedido, dict):
            self.pedido.emit(pedido)


class Agrupador(QObject):
    """Junta las rutas que llegan seguidas (una por cada vídeo seleccionado) en una sola búsqueda:
    espera a que pase `pausa` ms sin que llegue nada más, como mucho `maximo` ms desde la primera (con
    muchos vídeos seleccionados, las aperturas tardan en llegar todas)."""
    listo = Signal(list, bool, bool, str)    # rutas, recursivo, desde el menú contextual, modo ('' = el de siempre)

    def __init__(self, pausa=700, maximo=10_000, parent=None):
        super().__init__(parent)
        self.pendientes = {}            # (recursivo, menu, modo) -> [rutas]
        self._primera = None
        self._maximo = maximo
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(pausa)
        self._timer.timeout.connect(self.soltar)

    def agregar(self, rutas, recursivo=True, menu=False, modo=None):
        lista = self.pendientes.setdefault((recursivo, menu, modo or ''), [])
        for r in rutas:
            if r not in lista:
                lista.append(r)
        if self._primera is None:
            self._primera = time.monotonic()
        if (time.monotonic() - self._primera) * 1000 >= self._maximo:
            self.soltar()
        else:
            self._timer.start()

    def soltar(self):
        self._timer.stop()
        self._primera = None
        pendientes, self.pendientes = self.pendientes, {}
        for (recursivo, menu, modo), rutas in pendientes.items():
            self.listo.emit(rutas, recursivo, menu, modo)
