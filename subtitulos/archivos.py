"""Qué archivos son vídeos. Solo usa la biblioteca estándar."""
from pathlib import Path

# Datos compartidos con la skill: credenciales.json y copias de seguridad (backup/).
HOME = Path.home() / '.subtitulos-esp'
VIDEO_EXT = {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.ts'}


def es_video(ruta):
    ruta = Path(ruta)
    return ruta.suffix.lower() in VIDEO_EXT and 'sample' not in ruta.name.lower()


def buscar_videos(ruta):
    if ruta.is_file():
        return [ruta]
    return sorted(p for p in ruta.rglob('*') if p.suffix.lower() in VIDEO_EXT and 'sample' not in p.name.lower())
