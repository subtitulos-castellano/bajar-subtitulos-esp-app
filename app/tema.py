"""Colores, tipografía y hoja de estilos (QSS) de la app, en claro y oscuro.

Los colores de estado son fijos y siempre van con icono y texto, nunca solos:
castellano = bien (verde), latino = aviso (ámbar), inglés = serio (naranja),
no encontrado = crítico (rojo); pendiente (violeta) y sin cambios (gris) son informativos.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette

from subtitulos import eventos as ev

CLARO = {
    'nombre': 'claro',
    'fondo': '#f4f4f1', 'lateral': '#ecebe7', 'superficie': '#fcfcfb', 'superficie_hover': '#f0efeb',
    'borde': '#e1e0d9', 'borde_fuerte': '#c3c2b7', 'pista': '#e7e6e0',
    'texto': '#0b0b0b', 'texto2': '#52514e', 'texto3': '#7a7974',
    'acento': '#2a78d6', 'acento_hover': '#2368bd', 'acento_texto': '#ffffff', 'acento_suave': '#e8f0fb',
    'aviso_suave': '#fff6e0', 'aviso_borde': '#f3d58a',
}
OSCURO = {
    'nombre': 'oscuro',
    'fondo': '#121211', 'lateral': '#171716', 'superficie': '#1c1c1b', 'superficie_hover': '#262624',
    'borde': '#2c2c2a', 'borde_fuerte': '#45443f', 'pista': '#2c2c2a',
    'texto': '#f0efec', 'texto2': '#c3c2b7', 'texto3': '#8f8e86',
    'acento': '#3987e5', 'acento_hover': '#5598ea', 'acento_texto': '#ffffff', 'acento_suave': '#1a2a3f',
    'aviso_suave': '#2e2510', 'aviso_borde': '#5c4716',
}

# Categoría -> (color claro, color oscuro, icono, nombre corto, explicación)
# "Ya lo tenían" usa un verde más suave que "Castellano": los dos son buenos, pero solo uno es nuevo.
ESTADOS = {
    ev.CASTELLANO: ('#0ca30c', '#0ca30c', 'ok', 'Castellano', 'Subtítulo en castellano guardado ahora'),
    ev.YA_CASTELLANO: ('#79c779', '#2f7a2f', 'ya', 'Ya lo tenían', 'Ya tenían subtítulo en castellano'),
    ev.LATINO: ('#e09a00', '#fab219', 'aviso', 'Latino', 'Solo había latino: se ha guardado latino'),
    ev.INGLES: ('#e0703f', '#ec835a', 'idioma', 'Inglés', 'No había nada en español: se ha guardado inglés'),
    ev.SIN_CAMBIOS: ('#8a8984', '#8f8e86', 'igual', 'Sin cambios',
                     'Ya tenían latino o inglés y no se ha encontrado nada mejor'),
    ev.PENDIENTE: ('#6250d6', '#9085e9', 'reloj', 'Pendientes',
                   'Superan el límite de vídeos por tanda: se harán la próxima vez'),
    ev.NO_ENCONTRADO: ('#d03b3b', '#e05555', 'error', 'Sin subtítulos', 'No se ha encontrado ningún subtítulo'),
}
ORDEN_ESTADOS = list(ESTADOS)

_actual = CLARO


def actual():
    """Colores del tema activo."""
    return _actual


def oscuro():
    return _actual is OSCURO


def color_estado(categoria):
    claro, osc = ESTADOS[categoria][:2]
    return osc if oscuro() else claro


def icono_estado(categoria):
    return ESTADOS[categoria][2]


def nombre_estado(categoria):
    return ESTADOS[categoria][3]


def explicacion_estado(categoria):
    return ESTADOS[categoria][4]


def sistema_oscuro():
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def aplicar(app, preferencia='sistema'):
    """Aplica el tema ('sistema', 'claro' u 'oscuro'). Devuelve los colores elegidos."""
    global _actual
    es_oscuro = sistema_oscuro() if preferencia == 'sistema' else preferencia == 'oscuro'
    _actual = OSCURO if es_oscuro else CLARO
    hints = QGuiApplication.styleHints()
    if hasattr(hints, 'setColorScheme'):          # Qt >= 6.8: también la barra de título de Windows
        hints.setColorScheme(Qt.ColorScheme.Unknown if preferencia == 'sistema'
                             else Qt.ColorScheme.Dark if es_oscuro else Qt.ColorScheme.Light)
    app.setStyle('Fusion')
    app.setPalette(_paleta(_actual))
    app.setStyleSheet(qss(_actual))
    return _actual


def _paleta(t):
    p = QPalette()
    for rol, clave in ((QPalette.Window, 'fondo'), (QPalette.Base, 'superficie'),
                       (QPalette.AlternateBase, 'superficie_hover'), (QPalette.Button, 'superficie'),
                       (QPalette.WindowText, 'texto'), (QPalette.Text, 'texto'), (QPalette.ButtonText, 'texto'),
                       (QPalette.ToolTipBase, 'superficie'), (QPalette.ToolTipText, 'texto'),
                       (QPalette.PlaceholderText, 'texto3'), (QPalette.Highlight, 'acento'),
                       (QPalette.HighlightedText, 'acento_texto'), (QPalette.Link, 'acento'),
                       (QPalette.Mid, 'borde'), (QPalette.Midlight, 'borde'), (QPalette.Dark, 'borde_fuerte')):
        p.setColor(rol, QColor(t[clave]))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(t['texto3']))
    p.setColor(QPalette.Disabled, QPalette.WindowText, QColor(t['texto3']))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(t['texto3']))
    return p


FUENTE = '"Segoe UI Variable Text", "Segoe UI", sans-serif'
FUENTE_TITULO = '"Segoe UI Variable Display", "Segoe UI", sans-serif'
FUENTE_MONO = '"Cascadia Mono", Consolas, monospace'


def qss(t):
    return f'''
* {{ font-family: {FUENTE}; font-size: 10pt; }}
QWidget {{ color: {t['texto']}; }}
QMainWindow, #raiz, #pagina {{ background: {t['fondo']}; }}
QToolTip {{ background: {t['superficie']}; color: {t['texto']}; border: 1px solid {t['borde']}; padding: 4px 6px; }}

#lateral {{ background: {t['lateral']}; border-right: 1px solid {t['borde']}; }}
#marca {{ font-family: {FUENTE_TITULO}; font-size: 11.5pt; font-weight: 600; }}
#marcaSub {{ color: {t['texto3']}; font-size: 8.5pt; }}
#version {{ color: {t['texto3']}; font-size: 8.5pt; }}
QPushButton#nav {{ text-align: left; padding: 9px 12px; border: 1px solid transparent; border-radius: 8px;
                   background: transparent; color: {t['texto2']}; }}
QPushButton#nav:hover {{ background: {t['superficie_hover']}; color: {t['texto']}; }}
QPushButton#nav:checked {{ background: {t['superficie']}; color: {t['texto']}; font-weight: 600;
                           border: 1px solid {t['borde']}; }}

#titulo {{ font-family: {FUENTE_TITULO}; font-size: 19pt; font-weight: 600; }}
#subtitulo {{ color: {t['texto2']}; font-size: 10.5pt; }}
#seccion {{ font-family: {FUENTE_TITULO}; font-size: 12pt; font-weight: 600; }}
#ayuda {{ color: {t['texto3']}; font-size: 9pt; }}
#secundario {{ color: {t['texto2']}; }}
#tarjeta {{ background: {t['superficie']}; border: 1px solid {t['borde']}; border-radius: 12px; }}
#separador {{ background: {t['borde']}; max-height: 1px; min-height: 1px; border: none; }}

#zona {{ background: {t['superficie']}; border: 2px dashed {t['borde_fuerte']}; border-radius: 18px; }}
#zona[activa="true"] {{ background: {t['acento_suave']}; border: 2px solid {t['acento']}; }}
#zonaTitulo {{ font-family: {FUENTE_TITULO}; font-size: 15pt; font-weight: 600; }}
#zonaTexto {{ color: {t['texto2']}; }}
#resumenOpciones {{ color: {t['texto3']}; font-size: 9pt; }}

#banner {{ background: {t['aviso_suave']}; border: 1px solid {t['aviso_borde']}; border-radius: 8px; }}

QPushButton {{ padding: 7px 14px; border-radius: 6px; border: 1px solid {t['borde_fuerte']};
               background: {t['superficie']}; color: {t['texto']}; }}
QPushButton:hover {{ background: {t['superficie_hover']}; }}
QPushButton:pressed {{ background: {t['borde']}; }}
QPushButton:disabled {{ color: {t['texto3']}; border-color: {t['borde']}; }}
QPushButton#primario {{ background: {t['acento']}; color: {t['acento_texto']}; border: 1px solid {t['acento']};
                        font-weight: 600; }}
QPushButton#primario:hover {{ background: {t['acento_hover']}; border-color: {t['acento_hover']}; }}
QPushButton#plano {{ background: transparent; border: none; color: {t['texto2']}; padding: 6px 8px; }}
QPushButton#plano:hover {{ color: {t['texto']}; background: {t['superficie_hover']}; }}

QProgressBar {{ background: {t['pista']}; border: none; border-radius: 3px; min-height: 6px; max-height: 6px; }}
QProgressBar::chunk {{ background: {t['acento']}; border-radius: 3px; }}

QTableView {{ background: {t['superficie']}; border: 1px solid {t['borde']}; border-radius: 12px;
              gridline-color: transparent; selection-background-color: {t['acento_suave']};
              selection-color: {t['texto']}; outline: none; }}
QTableView::item {{ border-bottom: 1px solid {t['borde']}; padding: 0 8px; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{ background: {t['superficie']}; color: {t['texto3']}; border: none;
                        border-bottom: 1px solid {t['borde']}; padding: 8px 10px; font-size: 8.5pt;
                        font-weight: 600; }}
QHeaderView::section:first {{ border-top-left-radius: 12px; }}
QHeaderView::section:last {{ border-top-right-radius: 12px; }}

QPlainTextEdit#log {{ font-family: {FUENTE_MONO}; font-size: 9pt; background: {t['superficie']};
                      border: 1px solid {t['borde']}; border-radius: 8px; padding: 6px; color: {t['texto2']}; }}

QLineEdit, QSpinBox {{ padding: 6px 8px; border: 1px solid {t['borde_fuerte']}; border-radius: 6px;
                       background: {t['superficie']}; selection-background-color: {t['acento']}; }}
QLineEdit:focus, QSpinBox:focus {{ border: 1px solid {t['acento']}; }}
QLineEdit:disabled, QSpinBox:disabled {{ color: {t['texto3']}; background: {t['fondo']}; border-color: {t['borde']}; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {t['borde_fuerte']}; border-radius: 4px;
                        background: {t['superficie']}; }}
QCheckBox::indicator:checked {{ background: {t['acento']}; border-color: {t['acento']}; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t['borde_fuerte']}; border-radius: 3px; min-height: 30px; margin: 0 2px; }}
QScrollBar::handle:vertical:hover {{ background: {t['texto3']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {t['borde_fuerte']}; border-radius: 3px; min-width: 30px; margin: 2px 0; }}
'''
