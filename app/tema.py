"""Colores, tamaño del texto y hoja de estilos (QSS) de la app, en claro y oscuro.

Los colores de estado son fijos y siempre van con icono y texto, nunca solos:
castellano = bien (verde), latino = aviso (ámbar), inglés = serio (naranja),
no encontrado = crítico (rojo); pendiente (violeta) y sin cambios (gris) son informativos.

Tamaño del texto: por defecto sigue a Windows (Configuración › Accesibilidad › Tamaño del
texto, que guarda TextScaleFactor en el registro), igual que el Explorador. Todo lo que tiene
que ver con texto (letra, márgenes, alturas de filas y tarjetas) se multiplica por esa escala.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette

from subtitulos import eventos as ev
from subtitulos.idioma import N_, tr

from .plataforma import WINDOWS

CLARO = {
    'nombre': 'claro',
    'fondo': '#f4f4f1', 'lateral': '#ecebe7', 'superficie': '#fcfcfb', 'superficie_hover': '#f0efeb',
    'borde': '#e1e0d9', 'borde_fuerte': '#c3c2b7', 'pista': '#e7e6e0',
    'texto': '#0b0b0b', 'texto2': '#52514e', 'texto3': '#7a7974',
    'acento': '#2a78d6', 'acento_hover': '#2368bd', 'acento_texto': '#ffffff', 'acento_suave': '#e8f0fb',
    'aviso_suave': '#fff6e0', 'aviso_borde': '#f3d58a',
    'error_suave': '#fdecec', 'error_borde': '#f1b5b5',
}
OSCURO = {
    'nombre': 'oscuro',
    'fondo': '#121211', 'lateral': '#171716', 'superficie': '#1c1c1b', 'superficie_hover': '#262624',
    'borde': '#2c2c2a', 'borde_fuerte': '#45443f', 'pista': '#2c2c2a',
    'texto': '#f0efec', 'texto2': '#c3c2b7', 'texto3': '#8f8e86',
    'acento': '#3987e5', 'acento_hover': '#5598ea', 'acento_texto': '#ffffff', 'acento_suave': '#1a2a3f',
    'aviso_suave': '#2e2510', 'aviso_borde': '#5c4716',
    'error_suave': '#331717', 'error_borde': '#6b2a2a',
}

# Estados de la tabla mientras se busca (solo de la interfaz, no del núcleo).
EN_ESPERA = 'en_espera'        # aún no se ha revisado
BUSCANDO = 'buscando'          # el vídeo que se está revisando ahora
NO_REVISADO = 'no_revisado'    # se canceló antes de llegar a él

# Categoría -> (color claro, color oscuro, icono, nombre corto, explicación)
# "Ya lo tenían" usa un verde más suave que "Castellano": los dos son buenos, pero solo uno es nuevo.
ESTADOS = {
    ev.CASTELLANO: ('#0ca30c', '#0ca30c', 'ok', N_('Castellano'), N_('Subtítulo en castellano guardado ahora')),
    ev.YA_CASTELLANO: ('#79c779', '#2f7a2f', 'ya', N_('Ya lo tenían'), N_('Ya tenían subtítulo en castellano')),
    ev.LATINO: ('#e09a00', '#fab219', 'aviso', N_('Latino'), N_('Solo había latino: se ha guardado latino')),
    ev.INGLES: ('#e0703f', '#ec835a', 'idioma', N_('Inglés'), N_('No había nada en español: se ha guardado inglés')),
    ev.SIN_CAMBIOS: ('#8a8984', '#8f8e86', 'igual', N_('Sin cambios'),
                     N_('Ya tenían latino o inglés y no se ha encontrado nada mejor')),
    ev.PENDIENTE: ('#6250d6', '#9085e9', 'reloj', N_('Pendientes'),
                   N_('Superan el límite de vídeos por tanda: se harán la próxima vez')),
    ev.NO_ENCONTRADO: ('#d03b3b', '#e05555', 'error', N_('Sin subtítulos'), N_('No se ha encontrado ningún subtítulo')),
    NO_REVISADO: ('#a3a29b', '#6f6e68', 'circulo', N_('No revisados'),
                  N_('No se llegaron a revisar porque se canceló la búsqueda')),
}
ORDEN_ESTADOS = list(ESTADOS)
ESTADOS_PROGRESO = {
    EN_ESPERA: (None, None, 'circulo', N_('En espera'), N_('Todavía no se ha revisado')),
    BUSCANDO: (None, None, 'buscar', N_('Buscando…'), N_('Se está revisando ahora')),
}

_actual = CLARO
_escala = 1.0


def actual():
    """Colores del tema activo."""
    return _actual


def oscuro():
    return _actual is OSCURO


def _estado(categoria):
    return ESTADOS.get(categoria) or ESTADOS_PROGRESO[categoria]


def color_estado(categoria):
    if categoria == EN_ESPERA:
        return _actual['texto3']
    if categoria == BUSCANDO:
        return _actual['acento']
    claro, osc = ESTADOS[categoria][:2]
    return osc if oscuro() else claro


def icono_estado(categoria):
    return _estado(categoria)[2]


def nombre_estado(categoria):
    return tr(_estado(categoria)[3])


def explicacion_estado(categoria):
    return tr(_estado(categoria)[4])


# ---------- Tamaño del texto ----------

def escala_windows():
    """Porcentaje de 'Tamaño del texto' de Windows (100-225). 100 si no se puede leer."""
    if not WINDOWS:
        return 100
    from .plataforma import windows
    return windows.escala_texto()


def porcentaje(tamano_texto):
    """tamano_texto: 0 = como Windows; si no, el porcentaje elegido."""
    return escala_windows() if not tamano_texto else tamano_texto


def escala():
    return _escala


def px(n):
    """Medida en píxeles que crece con el texto."""
    return max(1, round(n * _escala))


def pt(n):
    """Tamaño de letra en puntos, con la escala aplicada."""
    return n * _escala


def fuente(base, puntos, peso=None, titulo=False):
    f = QFont(base)
    if titulo:
        f.setFamilies(['Segoe UI Variable Display', 'Segoe UI'])
    f.setPointSizeF(pt(puntos))
    if peso is not None:
        f.setWeight(peso)
    return f


# ---------- Aplicar ----------

def sistema_oscuro():
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def aplicar(app, preferencia='sistema', tamano_texto=0):
    """Aplica el tema ('sistema', 'claro' u 'oscuro') y el tamaño del texto. Devuelve los colores."""
    global _actual, _escala
    es_oscuro = sistema_oscuro() if preferencia == 'sistema' else preferencia == 'oscuro'
    _actual = OSCURO if es_oscuro else CLARO
    _escala = porcentaje(tamano_texto) / 100
    hints = QGuiApplication.styleHints()
    if hasattr(hints, 'setColorScheme'):          # Qt >= 6.8: también la barra de título de Windows
        hints.setColorScheme(Qt.ColorScheme.Unknown if preferencia == 'sistema'
                             else Qt.ColorScheme.Dark if es_oscuro else Qt.ColorScheme.Light)
    app.setStyle('Fusion')
    app.setPalette(_paleta(_actual))
    f = QFont(app.font())
    f.setFamilies(['Segoe UI Variable Text', 'Segoe UI'])
    f.setPointSizeF(pt(10))
    app.setFont(f)
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
    def f(n):
        return f'{pt(n):.2f}pt'

    def p(n):
        return f'{px(n)}px'

    return f'''
* {{ font-family: {FUENTE}; font-size: {f(10)}; }}
QWidget {{ color: {t['texto']}; }}
QMainWindow, #raiz, #pagina {{ background: {t['fondo']}; }}
QToolTip {{ background: {t['superficie']}; color: {t['texto']}; border: 1px solid {t['borde']}; padding: 4px 6px; }}

#lateral {{ background: {t['lateral']}; border-right: 1px solid {t['borde']}; }}
#marca {{ font-family: {FUENTE_TITULO}; font-size: {f(11.5)}; font-weight: 600; }}
#marcaSub {{ color: {t['texto3']}; font-size: {f(8.5)}; }}
#version {{ color: {t['texto3']}; font-size: {f(8.5)}; }}
QPushButton#nav {{ text-align: left; padding: {p(9)} {p(12)}; border: 1px solid transparent; border-radius: 8px;
                   background: transparent; color: {t['texto2']}; qproperty-iconSize: {p(18)} {p(18)}; }}
QPushButton#nav:hover {{ background: {t['superficie_hover']}; color: {t['texto']}; }}
QPushButton#nav:checked, QPushButton#nav:checked:disabled {{
    background: {t['superficie']}; color: {t['texto']}; font-weight: 600; border: 1px solid {t['borde']}; }}
QPushButton#nav:disabled {{ color: {t['texto3']}; background: transparent; }}

#titulo {{ font-family: {FUENTE_TITULO}; font-size: {f(19)}; font-weight: 600; }}
#subtitulo {{ color: {t['texto2']}; font-size: {f(10.5)}; }}
#seccion {{ font-family: {FUENTE_TITULO}; font-size: {f(12)}; font-weight: 600; }}
#ayuda {{ color: {t['texto3']}; font-size: {f(9)}; }}
#secundario {{ color: {t['texto2']}; }}
#tarjeta {{ background: {t['superficie']}; border: 1px solid {t['borde']}; border-radius: 12px; }}
#separador {{ background: {t['borde']}; max-height: 1px; min-height: 1px; border: none; }}

#zona {{ background: {t['superficie']}; border: 2px dashed {t['borde_fuerte']}; border-radius: 18px; }}
#zona[activa="true"] {{ background: {t['acento_suave']}; border: 2px solid {t['acento']}; }}
#zonaTitulo {{ font-family: {FUENTE_TITULO}; font-size: {f(15)}; font-weight: 600; }}
#zonaTexto {{ color: {t['texto2']}; }}
#resumenOpciones {{ color: {t['texto3']}; font-size: {f(9)}; }}

#banner {{ background: {t['aviso_suave']}; border: 1px solid {t['aviso_borde']}; border-radius: 8px; }}
#bannerError {{ background: {t['error_suave']}; border: 1px solid {t['error_borde']}; border-radius: 8px; }}
#bannerInfo {{ background: {t['acento_suave']}; border: 1px solid {t['acento']}; border-radius: 10px; }}
#avisoTitulo {{ font-weight: 600; }}
#avisoNotas {{ color: {t['texto2']}; font-size: {f(9)}; background: transparent; }}
#avisoNotasMarco, #avisoNotasVista {{ background: transparent; }}

QPushButton {{ padding: {p(7)} {p(14)}; border-radius: 6px; border: 1px solid {t['borde_fuerte']};
               background: {t['superficie']}; color: {t['texto']}; qproperty-iconSize: {p(16)} {p(16)}; }}
QPushButton:hover {{ background: {t['superficie_hover']}; }}
QPushButton:pressed {{ background: {t['borde']}; }}
QPushButton:disabled {{ color: {t['texto3']}; border-color: {t['borde']}; }}
QPushButton#primario {{ background: {t['acento']}; color: {t['acento_texto']}; border: 1px solid {t['acento']};
                        font-weight: 600; }}
QPushButton#primario:hover {{ background: {t['acento_hover']}; border-color: {t['acento_hover']}; }}
QPushButton#primario:disabled {{ background: {t['superficie']}; color: {t['texto3']}; border-color: {t['borde']};
                                 font-weight: normal; }}
QPushButton#plano {{ background: transparent; border: none; color: {t['texto2']}; padding: {p(6)} {p(8)}; }}
QPushButton#plano:hover {{ color: {t['texto']}; background: {t['superficie_hover']}; }}
QPushButton#segmento {{ border-radius: 0; padding: {p(6)} {p(16)}; margin: 0; }}
QPushButton#segmento[pos="ini"] {{ border-top-left-radius: 6px; border-bottom-left-radius: 6px; }}
QPushButton#segmento[pos="medio"] {{ border-left: none; border-right: none; }}
QPushButton#segmento[pos="fin"] {{ border-top-right-radius: 6px; border-bottom-right-radius: 6px; }}
QPushButton#segmento:checked {{ background: {t['acento']}; color: {t['acento_texto']};
                                border-color: {t['acento']}; font-weight: 600; }}

QTableView {{ background: {t['superficie']}; border: 1px solid {t['borde']}; border-radius: 12px;
              gridline-color: transparent; selection-background-color: {t['acento_suave']};
              selection-color: {t['texto']}; outline: none; }}
QTableView::item {{ border-bottom: 1px solid {t['borde']}; padding: 0 {p(8)}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{ background: {t['superficie']}; color: {t['texto3']}; border: none;
                        border-bottom: 1px solid {t['borde']}; padding: {p(8)} {p(10)}; font-size: {f(8.5)};
                        font-weight: 600; }}
QHeaderView::section:first {{ border-top-left-radius: 12px; }}
QHeaderView::section:last {{ border-top-right-radius: 12px; }}

QPlainTextEdit#log {{ font-family: {FUENTE_MONO}; font-size: {f(10)}; background: {t['superficie']};
                      border: 1px solid {t['borde']}; border-radius: 8px; padding: {p(8)}; color: {t['texto2']}; }}

QLineEdit, QSpinBox {{ padding: {p(6)} {p(8)}; border: 1px solid {t['borde_fuerte']}; border-radius: 6px;
                       background: {t['superficie']}; selection-background-color: {t['acento']}; }}
QLineEdit:focus, QSpinBox:focus {{ border: 1px solid {t['acento']}; }}
/* Sin flechas: se escribe el número o se usa la rueda. (setButtonSymbols(NoButtons) junto con una
   hoja de estilos deja el campo con 1 px de ancho en Qt 6.12.) */
QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; border: none; }}
QLineEdit:disabled, QSpinBox:disabled {{ color: {t['texto3']}; background: {t['fondo']}; border-color: {t['borde']}; }}

QCheckBox {{ spacing: {p(8)}; }}
QCheckBox::indicator {{ width: {p(16)}; height: {p(16)}; border: 1px solid {t['borde_fuerte']}; border-radius: 4px;
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
