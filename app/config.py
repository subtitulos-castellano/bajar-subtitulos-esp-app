"""Preferencias de la app en %APPDATA%\\BajarSubtitulosEsp\\config.json.

Se guardan al momento, en cada cambio. Si el archivo no existe o está dañado, se usan los
valores por defecto (los mismos que la CLI sin parámetros). La contraseña de OpenSubtitles
NO se guarda aquí: va al Administrador de credenciales de Windows (ver credenciales.py).
"""
import json
import os
from dataclasses import asdict, fields
from pathlib import Path

from subtitulos.opciones import Opciones

TEMAS = ('sistema', 'claro', 'oscuro')


def carpeta():
    base = os.environ.get('APPDATA')
    return (Path(base) if base else Path.home() / '.config') / 'BajarSubtitulosEsp'


class Config:
    def __init__(self, ruta=None):
        self.ruta = Path(ruta) if ruta else carpeta() / 'config.json'
        self.opciones = Opciones()
        self.tema = 'sistema'
        self.usuario_opensubtitles = ''
        self.geometria = ''          # tamaño y posición de la ventana (base64 de Qt)
        self.cargar()

    def cargar(self):
        try:
            datos = json.loads(self.ruta.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return
        if not isinstance(datos, dict):
            return
        validos = {f.name for f in fields(Opciones)}
        guardadas = datos.get('opciones')
        if isinstance(guardadas, dict):
            try:
                self.opciones = Opciones(**{k: v for k, v in guardadas.items() if k in validos})
            except (TypeError, ValueError):
                self.opciones = Opciones()
        if datos.get('tema') in TEMAS:
            self.tema = datos['tema']
        if isinstance(datos.get('usuario_opensubtitles'), str):
            self.usuario_opensubtitles = datos['usuario_opensubtitles']
        if isinstance(datos.get('geometria'), str):
            self.geometria = datos['geometria']

    def guardar(self):
        datos = {'opciones': asdict(self.opciones), 'tema': self.tema,
                 'usuario_opensubtitles': self.usuario_opensubtitles, 'geometria': self.geometria}
        try:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            temporal = self.ruta.with_suffix('.tmp')
            temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding='utf-8')
            temporal.replace(self.ruta)      # escritura atómica: nunca queda a medias
        except OSError:
            pass                              # sin permisos: la app sigue con lo que tiene en memoria
