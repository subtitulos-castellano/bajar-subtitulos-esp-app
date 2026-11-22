"""Idioma de los textos que se muestran: castellano (el del código) o inglés.

Los textos se escriben en castellano en el código, dentro de `tr()`; `en.py` tiene su traducción.
El idioma se elige una vez, al arrancar (la app lo lee de su configuración; la CLI y la skill no lo
cambian y siguen en castellano). Cambiarlo con la app abierta no rehace lo que ya se ve: por eso la
app se vuelve a abrir al cambiarlo en Configuración.

    tr('Vídeo {indice} de {total}', indice=3, total=10)   # 'Vídeo 3 de 10' o 'Video 3 of 10'

`N_()` solo marca un texto para traducirlo más tarde (en constantes que se crean al importar el
módulo, antes de saber el idioma); se traduce donde se muestra, con `tr(variable)`. Las pruebas
comprueban que todo lo que va en `tr('…')` o `N_('…')` tiene traducción y con los mismos `{campos}`.

Solo usa la biblioteca estándar.
"""
IDIOMAS = ('es', 'en')
POR_DEFECTO = 'es'

_actual = POR_DEFECTO


def poner(codigo):
    """Elige el idioma ('es' o 'en'); cualquier otro valor deja el castellano."""
    global _actual
    _actual = codigo if codigo in IDIOMAS else POR_DEFECTO


def actual():
    return _actual


def tr(texto, **campos):
    """`texto` (en castellano) en el idioma elegido, con los `{campos}` ya puestos. Si falta la
    traducción, se queda en castellano (las pruebas no lo dejan pasar)."""
    if _actual == 'en':
        from .en import TEXTOS
        texto = TEXTOS.get(texto, texto)
    return texto.format(**campos) if campos else texto


def N_(texto):
    """Marca `texto` para traducirlo donde se muestre (con `tr`). Lo devuelve tal cual."""
    return texto
