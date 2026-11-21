"""Iconos SVG de línea (trazos de Lucide, licencia ISC: https://lucide.dev/license).

Se dibujan en el color que se pida, a la resolución de la pantalla.
"""
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

TRAZOS = {
    'inicio': '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    'ajustes': '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    'subtitulos': '<rect width="18" height="14" x="3" y="5" rx="2" ry="2"/><path d="M7 15h4M15 15h2M7 11h2M13 11h4"/>',
    'soltar': '<path d="M12 15V3"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/>',
    'carpeta': '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
    'video': '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M7 3v18"/><path d="M3 7.5h4"/><path d="M3 12h18"/><path d="M3 16.5h4"/><path d="M17 3v18"/><path d="M17 7.5h4"/><path d="M17 16.5h4"/>',
    'copiar': '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    'simulacion': '<path d="M14 2v6a2 2 0 0 0 .245.96l5.51 10.08A2 2 0 0 1 18 22H6a2 2 0 0 1-1.755-2.96l5.51-10.08A2 2 0 0 0 10 8V2"/><path d="M6.453 15h11.094"/><path d="M8.5 2h7"/>',
    'restaurar': '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    'abajo': '<path d="m6 9 6 6 6-6"/>',
    'derecha': '<path d="m9 18 6-6-6-6"/>',
    'usuario': '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    'copias': '<rect width="20" height="5" x="2" y="3" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/>',
    'escudo': '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-.76c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    'idioma': '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    'cerrar': '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    'cola': '<path d="M3 12h.01"/><path d="M3 18h.01"/><path d="M3 6h.01"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M8 6h13"/>',
    # Estados del resumen
    'ok': '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    'ya': '<path d="M20 6 9 17l-5-5"/>',
    'aviso': '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    'error': '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    'reloj': '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    'igual': '<circle cx="12" cy="12" r="10"/><path d="M8 12h8"/>',
    'circulo': '<circle cx="12" cy="12" r="9" stroke-dasharray="3.5 3"/>',
    'buscar': '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    'actualizar': '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
}


# Icono de la app: pantalla de vídeo (cristal oscuro con marco azul) con play y subtítulos, y una
# flecha que entra en una bandeja (descargar). Sin fondo: el contorno es la propia pantalla.
ICONO_APP = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
<defs>
  <linearGradient id="pantalla" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#2c3038"/><stop offset="1" stop-color="#07090c"/>
  </linearGradient>
  <linearGradient id="vidrio" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#ffffff" stop-opacity="0.20"/>
    <stop offset="0.45" stop-color="#ffffff" stop-opacity="0.05"/>
    <stop offset="0.46" stop-color="#ffffff" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="azul" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#4f9cf5"/><stop offset="1" stop-color="#1c5fb3"/>
  </linearGradient>
</defs>
<rect x="10" y="22" width="220" height="172" rx="30" fill="url(#pantalla)"/>
<rect x="10" y="22" width="220" height="172" rx="30" fill="url(#vidrio)"/>
<rect x="13" y="25" width="214" height="166" rx="27" fill="none" stroke="url(#azul)" stroke-width="6"/>
<circle cx="120" cy="90" r="32" fill="#ffffff" fill-opacity="0.9"/>
<path d="M109.8 74 L136.6 90 L109.8 106 Z" fill="#0b0d10" stroke="#0b0d10" stroke-width="3.8" stroke-linejoin="round"/>
<rect x="58" y="140" width="124" height="13" rx="6.5" fill="#ffffff"/>
<rect x="81.6" y="160.8" width="76.9" height="13" rx="6.5" fill="#ffffff" fill-opacity="0.7"/>
<circle cx="200" cy="204" r="52" fill="#000000" fill-opacity="0.25"/>
<circle cx="200" cy="200" r="50" fill="#ffffff"/>
<circle cx="200" cy="200" r="47" fill="none" stroke="url(#azul)" stroke-width="6"/>
<path d="M200 171 V204 M185 191 L200 206 L215 191" fill="none" stroke="#2a78d6" stroke-width="11"
      stroke-linecap="round" stroke-linejoin="round"/>
<path d="M177 208 V216 A6 6 0 0 0 183 222 H217 A6 6 0 0 0 223 216 V208" fill="none" stroke="#2a78d6"
      stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>
</svg>'''


def pixmap_app(lado):
    """El icono de la app a `lado` x `lado` píxeles."""
    pm = QPixmap(lado, lado)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    QSvgRenderer(QByteArray(ICONO_APP.encode())).render(p, QRectF(0, 0, lado, lado))
    p.end()
    return pm


def _svg(nombre, color, grosor):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{grosor}" stroke-linecap="round" stroke-linejoin="round">{TRAZOS[nombre]}</svg>')


def pixmap(nombre, color, tam=20, escala=2.0, grosor=2):
    """QPixmap del icono, nítido en pantallas con escalado (escala = devicePixelRatio)."""
    lado = max(1, round(tam * escala))
    pm = QPixmap(lado, lado)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    QSvgRenderer(QByteArray(_svg(nombre, color, grosor).encode())).render(p, QRectF(0, 0, lado, lado))
    p.end()
    pm.setDevicePixelRatio(escala)
    return pm


def icono(nombre, color, tam=20):
    return QIcon(pixmap(nombre, color, tam))


def dibujar(painter, nombre, color, rect, grosor=2):
    """Dibuja el icono directamente en un QPainter (para widgets pintados a mano)."""
    QSvgRenderer(QByteArray(_svg(nombre, color, grosor).encode())).render(painter, QRectF(rect))
