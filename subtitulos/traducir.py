"""Traducción automática de un subtítulo inglés al castellano, sin conexión.

Usa un modelo Opus-MT (inglés → español, Universidad de Helsinki, licencia Apache 2.0) convertido para
CTranslate2. El modelo no va dentro del programa: se descarga la primera vez que hace falta (modelo.py).

Cómo se traduce un .srt:
- Se conservan los tiempos: solo se traduce el texto de cada bloque.
- Se quitan las anotaciones para sordos ([risas], (SUSPIRA), «MAEVE:») y las etiquetas de formato; si
  un bloque iba en cursiva, la traducción también.
- Una frase partida entre varios bloques se traduce entera y luego se reparte entre ellos; en un
  diálogo («- ¿Vienes? / - Ahora voy»), cada intervención por separado.
- Cada frase se traduce por separado: el modelo, con varias frases a la vez, a veces se salta alguna.
- Al resultado se le cambian palabras de Latinoamérica por las de España (computadora → ordenador...).
- Se añade al principio un bloque que avisa de que es una traducción automática. También sirve para
  reconocerla después (texto.es_traduccion).

Este módulo solo usa la biblioteca estándar; ctranslate2 y sentencepiece se importan al traducir.
"""
import os
import re

from .texto import AVISO_TRADUCCION as AVISO
MAX_LINEA = 42          # caracteres por línea al recolocar el texto
MAX_GRUPO = 4           # bloques que, como mucho, se unen para traducir una frase partida
_SIGUE = re.compile(r'[^\W_]$')   # termina en letra o número: la frase sigue en el bloque siguiente
_ETIQUETA = re.compile(r'<[^>]*>|\{\\[^}]*\}')
_SORDOS = re.compile(r'\[[^\]]*\]|\([^)]*\)')
_HABLANTE = re.compile(r"^\s*[A-Z][A-Z0-9 .'&-]{1,30}:\s*")
_FRASES = re.compile(r'(?<=[.!?…])\s+(?=[-¿¡"\'(\[A-Z0-9])')
_TIEMPO = re.compile(r'^\s*(\d+:\d+:\d+[,.]\d+)\s*-->\s*(\d+:\d+:\d+[,.]\d+)')

# Palabras de Latinoamérica que el modelo usa a menudo y su equivalente en España. Solo palabras sin
# otro significado en España (no «carro», «manejar» o «departamento»).
_ESPANA = {
    'computadora': 'ordenador', 'computadoras': 'ordenadores',
    'celular': 'móvil', 'celulares': 'móviles',
    'auto': 'coche', 'autos': 'coches',
    'lentes': 'gafas', 'anteojos': 'gafas',
    'jugo': 'zumo', 'jugos': 'zumos',
    'enojado': 'enfadado', 'enojada': 'enfadada', 'enojados': 'enfadados', 'enojadas': 'enfadadas',
    'enojar': 'enfadar', 'enojes': 'enfades', 'enojo': 'enfado',
    'lindo': 'bonito', 'linda': 'bonita', 'lindos': 'bonitos', 'lindas': 'bonitas',
    'ahorita': 'ahora', 'rentar': 'alquilar', 'renta': 'alquiler',
    'boleto': 'billete', 'boletos': 'billetes',
    'mesero': 'camarero', 'mesera': 'camarera', 'meseros': 'camareros',
    'estacionamiento': 'aparcamiento', 'estacionar': 'aparcar',
    'plomero': 'fontanero', 'recámara': 'habitación', 'chamarra': 'chaqueta',
    'durazno': 'melocotón', 'duraznos': 'melocotones', 'papas fritas': 'patatas fritas',
    'diablos': 'demonios', 'oigan': 'oíd',
}
# Frases cortas muy frecuentes que el modelo traduce de forma poco natural en España («Correcto.» por
# «Right.»). Se comparan sin mayúsculas ni puntuación y se conservan los signos del original.
_HECHAS = {
    'okay': 'vale', 'ok': 'vale', 'right': 'vale', 'all right': 'vale', 'alright': 'vale',
    'okay then': 'vale', 'right then': 'vale', 'yeah': 'sí', 'yep': 'sí', 'yup': 'sí', 'nope': 'no',
    'huh': 'qué', 'what': 'qué', 'hey': 'eh', 'come on': 'venga', 'thanks': 'gracias',
    'thank you': 'gracias', 'okay thanks': 'vale, gracias', 'sorry': 'perdona', 'excuse me': 'perdona',
    'oh my god': 'dios mío', 'shit': 'mierda', 'fuck': 'joder', 'damn': 'joder', 'damn it': 'mierda',
    'good': 'bien', 'great': 'genial', 'cool': 'guay', 'wow': 'hala', 'uh-huh': 'ajá', 'mm-hmm': 'ajá',
    'hello': 'hola', 'hi': 'hola', 'bye': 'adiós', 'goodbye': 'adiós', 'guys': 'chicos', 'you guys': 'chicos',
}
_ESPANA_RE = re.compile(r'\b(' + '|'.join(sorted(_ESPANA, key=len, reverse=True)) + r')\b', re.IGNORECASE)


# ---------- SRT ----------

def leer_srt(texto):
    """[(inicio, fin, [líneas]), ...] con los tiempos tal como vienen ('00:01:02,345')."""
    bloques = []
    # Algunos .srt traen «\r\r\n» dentro de un bloque: no es una línea en blanco.
    texto = re.sub(r'\r+\n', '\n', texto).replace('\r', '\n').lstrip('\ufeff')
    for trozo in re.split(r'\n[ \t]*\n', texto):
        lineas = trozo.strip('\n').split('\n')
        for i, linea in enumerate(lineas[:2]):
            m = _TIEMPO.match(linea)
            if m:
                bloques.append((m.group(1).replace('.', ','), m.group(2).replace('.', ','), lineas[i + 1:]))
                break
        else:
            # Sin tiempos: es la continuación del bloque anterior, separada por una línea en blanco
            # (o por «\r\r\n», si el texto se leyó convirtiendo los saltos de línea).
            if bloques and trozo.strip():
                bloques[-1][2].extend(l for l in lineas if l.strip())
    return bloques


def escribir_srt(bloques):
    return ''.join(f'{n}\n{ini} --> {fin}\n' + '\n'.join(lineas) + '\n\n'
                   for n, (ini, fin, lineas) in enumerate(bloques, 1))


def _ms(tiempo):
    h, m, resto = tiempo.split(':')
    s, ms = resto.split(',')
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms[:3].ljust(3, '0'))


def _tiempo(ms):
    return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}'


# ---------- Preparar el texto ----------

def _limpiar(lineas):
    """Las líneas de un bloque sin etiquetas ni anotaciones para sordos (que pueden ocupar dos líneas)."""
    texto = _SORDOS.sub('', _ETIQUETA.sub('', '\n'.join(lineas)))
    limpias = []
    for linea in texto.split('\n'):
        linea = re.sub(r'\s+', ' ', _HABLANTE.sub('', linea)).strip()
        if linea.strip('-♪# '):
            limpias.append(linea)
    return limpias


def _intervenciones(lineas):
    """Las intervenciones de un bloque: varias si es un diálogo con guiones, si no una sola."""
    limpias = _limpiar(lineas)
    if sum(1 for l in limpias if l.startswith('-')) >= 2 or (limpias and limpias[0].startswith('-')
                                                             and len(limpias) > 1):
        partes = []
        for l in limpias:
            if l.startswith('-') or not partes:
                partes.append(l.lstrip('- ').strip())
            else:
                partes[-1] += ' ' + l
        return [p for p in partes if p], True
    texto = ' '.join(limpias).lstrip('- ').strip() if limpias else ''
    return ([texto] if texto else []), False


def _musica(texto):
    """('♪ ', texto sin ♪) si es una canción (el modelo no conoce el signo ♪)."""
    if '♪' in texto or texto.startswith('#'):
        return '♪ ', re.sub(r'\s+', ' ', texto.replace('♪', ' ').lstrip('# ')).strip()
    return '', texto


def hecha(frase):
    """La traducción de una frase corta muy frecuente, o None."""
    m = re.fullmatch(r'\s*([¿¡"]*)(.*?)([.!?…,"]*)\s*', frase)
    clave = re.sub(r'[,\s]+', ' ', m.group(2).lower()).strip()
    if clave not in _HECHAS:
        return None
    texto, final = _HECHAS[clave], m.group(3)
    texto = texto[0].upper() + texto[1:]
    if '?' in final:
        return f'¿{texto}{final}'
    if '!' in final:
        return f'¡{texto}{final}'
    return texto + final


def frases(texto):
    """Divide un texto en frases para traducirlas por separado."""
    return [f for f in _FRASES.split(texto) if f.strip()]


# ---------- Recolocar ----------

def lineas(texto, ancho=MAX_LINEA):
    """Una o dos líneas equilibradas."""
    if len(texto) <= ancho:
        return [texto]
    mitad = len(texto) // 2
    espacios = [i for i, c in enumerate(texto) if c == ' ']
    if not espacios:
        return [texto]
    corte = min(espacios, key=lambda i: abs(i - mitad))
    return [texto[:corte], texto[corte + 1:]]


def repartir(texto, pesos):
    """Reparte las palabras de `texto` en len(pesos) trozos proporcionales a `pesos`, cortando, si puede, tras
    un signo de puntuación cercano."""
    palabras = texto.split()
    if len(pesos) == 1 or not palabras:
        return [texto] + [''] * (len(pesos) - 1)
    total = sum(pesos) or 1
    trozos, inicio, acumulado = [], 0, 0
    for i, peso in enumerate(pesos[:-1]):
        acumulado += peso
        quedan = len(pesos) - i - 1
        corte = round(len(palabras) * acumulado / total)
        corte = max(inicio + 1, min(corte, len(palabras) - quedan))
        mejor = corte
        for d in (0, -1, 1, -2, 2):
            c = corte + d
            if inicio < c <= len(palabras) - quedan and re.search(r'[,.;:!?…]$', palabras[c - 1]):
                mejor = c
                break
        trozos.append(' '.join(palabras[inicio:mejor]))
        inicio = mejor
    trozos.append(' '.join(palabras[inicio:]))
    return trozos


def a_espana(texto):
    """Cambia palabras de Latinoamérica por las de España, respetando mayúsculas."""
    def cambiar(m):
        palabra = m.group(0)
        nueva = _ESPANA[palabra.lower()]
        if palabra.isupper() and len(palabra) > 1:
            return nueva.upper()
        return nueva[0].upper() + nueva[1:] if palabra[0].isupper() else nueva
    return _ESPANA_RE.sub(cambiar, texto)


# ---------- Traducir ----------

def traducir_srt(texto, traducir_frases, avance=lambda hecho, total: None):
    """Devuelve el .srt `texto` traducido.

    `traducir_frases(lista de frases en inglés)` → lista de frases en castellano (el motor).
    `avance(hechas, total)` se llama mientras se traduce.
    """
    bloques = leer_srt(texto)
    # 1) Unidades: (índices de bloque, intervención) que se traducen como un todo.
    preparados = []          # por bloque: (ini, fin, intervenciones, es_dialogo, cursiva)
    for ini, fin, ls in bloques:
        partes, dialogo = _intervenciones(ls)
        cursiva = any('<i>' in l.lower() for l in ls)
        preparados.append((ini, fin, partes, dialogo, cursiva))
    unidades = []            # (lista de (bloque, peso), texto en inglés)
    i = 0
    while i < len(preparados):
        partes, dialogo = preparados[i][2], preparados[i][3]
        if not partes:
            i += 1
            continue
        if dialogo:
            for n, p in enumerate(partes):
                unidades.append(([(i, n)], p))
            i += 1
            continue
        grupo = [i]
        texto_grupo = partes[0]
        # Una frase partida: el bloque acaba sin puntuación (si acaba en coma, se traduce por separado).
        while (len(grupo) < MAX_GRUPO and _SIGUE.search(texto_grupo) and '♪' not in texto_grupo
               and i + 1 < len(preparados) and preparados[i + 1][2] and not preparados[i + 1][3]
               and '♪' not in preparados[i + 1][2][0]
               and _ms(preparados[i + 1][0]) - _ms(preparados[i][1]) < 1500):
            i += 1
            grupo.append(i)
            texto_grupo += ' ' + preparados[i][2][0]
        unidades.append(([(b, 0) for b in grupo], texto_grupo))
        i += 1

    # 2) Frases distintas, traducidas por tandas.
    por_unidad = []
    pendientes = {}
    for _, texto_u in unidades:
        musica, limpio = _musica(texto_u)
        lista = frases(limpio)
        por_unidad.append((musica, lista))
        for f in lista:
            pendientes.setdefault(f, hecha(f))
    hecho = {f: t for f, t in pendientes.items() if t is not None}
    originales = [f for f, t in pendientes.items() if t is None]
    traducidas = []
    tanda = 64
    for n in range(0, len(originales), tanda):
        traducidas += traducir_frases(originales[n:n + tanda])
        avance(min(n + tanda, len(originales)), len(originales))
    hecho.update(zip(originales, traducidas))

    # 3) Volver a montar cada bloque.
    resultado = [[] for _ in preparados]
    for (destinos, texto_u), (musica, lista) in zip(unidades, por_unidad):
        texto_es = a_espana(' '.join(hecho[f].strip() for f in lista if hecho.get(f)))
        if texto_es and texto_u[:1].islower() and texto_es[:1].isupper():
            texto_es = texto_es[0].lower() + texto_es[1:]     # sigue la frase del bloque anterior
        if len(destinos) == 1:
            trozos = [texto_es]
        else:
            trozos = repartir(texto_es, [len(preparados[b][2][0]) for b, _ in destinos])
        for (b, _), trozo in zip(destinos, trozos):
            if trozo:
                resultado[b].append(musica + trozo if musica else trozo)
    salida = []
    for (ini, fin, partes, dialogo, cursiva), textos in zip(preparados, resultado):
        if not textos:
            continue
        if dialogo and len(textos) > 1:
            ls = [f'- {t}' for t in textos]
        else:
            ls = lineas(' '.join(textos))
        if cursiva:
            ls = [f'<i>{l}</i>' for l in ls]
        salida.append((ini, fin, ls))
    # 4) Aviso al principio: hasta el primer bloque (como mucho 4 s).
    primero = _ms(salida[0][0]) if salida else 4000
    fin_aviso = max(1, min(4000, primero - 50))
    salida.insert(0, (_tiempo(0), _tiempo(fin_aviso), [AVISO]))
    return escribir_srt(salida)


class Motor:
    """El modelo de traducción cargado en memoria (ctranslate2 + sentencepiece)."""

    def __init__(self, carpeta, hilos=None):
        import ctranslate2
        import sentencepiece
        carpeta = str(carpeta)
        self._origen = sentencepiece.SentencePieceProcessor(model_file=os.path.join(carpeta, 'source.spm'))
        self._destino = sentencepiece.SentencePieceProcessor(model_file=os.path.join(carpeta, 'target.spm'))
        hilos = hilos or max(1, min(8, (os.cpu_count() or 2) - 1))
        self._modelo = ctranslate2.Translator(carpeta, device='cpu', compute_type='int8', inter_threads=1,
                                              intra_threads=hilos)

    def __call__(self, frases_en):
        if not frases_en:
            return []
        tokens = [self._origen.encode(f, out_type=str)[:400] + ['</s>'] for f in frases_en]
        resultados = self._modelo.translate_batch(tokens, beam_size=4, max_batch_size=32,
                                                  max_decoding_length=512, repetition_penalty=1.1)
        return [self._destino.decode(r.hypotheses[0]) for r in resultados]
