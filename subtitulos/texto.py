"""Limpieza de textos de terceros y detección del idioma y del dialecto de un subtítulo.

Solo usa la biblioteca estándar: se puede importar sin cargar subliminal.
"""
import re

MAX_SRT = 2 * 1024 * 1024        # caracteres de un subtítulo (los normales tienen 20-200 mil)
# Caracteres de control (C0 y C1), de ancho cero y de dirección del texto: no aparecen en un
# subtítulo normal y pueden servir para engañar a reproductores, terminales o al agente.
CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f​-‏‪-‮⁦-⁩]')
CONTROL_LINEA = re.compile(r'[\x00-\x1f\x7f-\x9f​-‏‪-‮⁦-⁩]')

ES_RE = re.compile(
    r'\b(vosotr[oa]s|vuestr[oa]s?|os|vale(?!\s+la\s+pena)|chaval\w*|leches|ordenador\w*|móvil\w*'
    r'|gilipollas|joder|mola|guay|tío|tía|\w+áis|\w+éis)\b',
    re.IGNORECASE,
)
LA_RE = re.compile(
    r'\b(ustedes|computadora\w*|celular\w*|carro|carros|enojad\w*|ahorita|platic\w*|chamac\w*'
    r'|rentar|nomás|recién|lindo|jalar)\b',
    re.IGNORECASE,
)
# Para saber si un .srt que ya existe está en inglés o en español.
EN_PALABRAS = re.compile(r"\b(the|you|and|what|this|that|is|are|it's|don't|i'm|with)\b", re.IGNORECASE)
SP_PALABRAS = re.compile(r'\b(que|qué|el|los|las|una|por|para|está|pero|con|es)\b', re.IGNORECASE)
# Nombres de pistas incrustadas: "... LA", "Spanish (Latin America)", "Español (España)"...
LATINO_NOMBRE = re.compile(r'\b(la|lat|latam|latino\w*|latinoam\w*|latin|419|mx|méxico|mexico)\b',
                           re.IGNORECASE)
ESPANA_NOMBRE = re.compile(r'\b(es|esp|españa|spain|castellano|castilian|european|eur)\b', re.IGNORECASE)


def limpiar_texto(texto):
    """Quita del subtítulo los caracteres de control, de ancho cero y de dirección del texto."""
    return CONTROL.sub('', texto)


def visible(valor):
    """Texto de terceros (nombres de pista, ids...) seguro para mostrarlo en una sola línea."""
    return CONTROL_LINEA.sub(' ', str(valor))


def dialecto(texto):
    es = len(ES_RE.findall(texto))
    la = len(LA_RE.findall(texto))
    return es, la, es >= 3 and es > 2 * la


def idioma_srt(texto):
    """'castellano', 'latino', 'ingles', 'otro' o None (vacío)."""
    if not texto.strip():
        return None
    if dialecto(texto)[2]:
        return 'castellano'
    n_en, n_sp = len(EN_PALABRAS.findall(texto)), len(SP_PALABRAS.findall(texto))
    if n_sp > n_en:
        return 'latino'
    if n_en > n_sp:
        return 'ingles'
    return 'otro'


def ultimo_tiempo(texto):
    tiempos = re.findall(r'-->\s*(\d+):(\d+):(\d+)', texto)
    if not tiempos:
        return None
    h, m, s = map(int, tiempos[-1])
    return h * 3600 + m * 60 + s
