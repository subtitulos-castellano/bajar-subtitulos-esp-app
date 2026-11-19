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


def buscar_en_varias(rutas):
    """Vídeos de varias rutas (vídeos sueltos y carpetas) en una sola lista, como si estuvieran en la
    misma carpeta: en el orden recibido, cada carpeta con sus vídeos ordenados, y sin repetidos."""
    vistos, videos = set(), []
    for ruta in rutas:
        for v in buscar_videos(Path(ruta)):
            clave = v.resolve()
            if clave not in vistos:
                vistos.add(clave)
                videos.append(v)
    return videos


def carpeta_comun(rutas):
    """Carpeta que contiene todas las rutas (para 'Abrir carpeta' y para mostrarla)."""
    import os
    carpetas = [str(r if Path(r).is_dir() else Path(r).parent) for r in rutas]
    try:
        return Path(os.path.commonpath(carpetas))
    except ValueError:               # unidades distintas (C: y D:): la del primero
        return Path(carpetas[0])
