"""Pistas de subtítulos de texto incrustadas en MKV y MP4/M4V/MOV, sin ffmpeg ni mkvtoolnix.

Solo usa la biblioteca estándar: se puede importar sin cargar subliminal.
"""
import re
import struct
import time

from .idioma import tr
from .texto import ESPANA_NOMBRE, LATINO_NOMBRE, MAX_SRT, dialecto, visible

MKV_EXT = {'.mkv'}
MP4_EXT = {'.mp4', '.m4v', '.mov'}
# Límites de seguridad frente a vídeos corruptos o manipulados.
MAX_ELEMENTO = 16 * 1024 * 1024  # bytes que se leen de golpe de un elemento MKV o muestra MP4
MAX_MOOV = 64 * 1024 * 1024      # tamaño máximo del índice ('moov') de un MP4
MAX_MUESTRAS = 1_000_000         # entradas de una tabla de muestras de una pista de subtítulos


# Extraer una pista incrustada obliga a recorrer el vídeo entero (los subtítulos van repartidos entre
# la imagen y el sonido). En un disco lento o de red, un vídeo de varios GB tarda minutos: si se
# calcula que pasará de LIMITE_EXTRACCION segundos, se deja y se buscan en los proveedores.
LIMITE_EXTRACCION = 15      # segundos
MUESTRA_EXTRACCION = 1.5    # segundos de lectura antes de estimar el total


class ArchivoInvalido(Exception):
    """Vídeo corrupto, cortado o manipulado: se dejan de leer sus pistas incrustadas."""


class Lento(Exception):
    """Extraer la pista tardaría más de LIMITE_EXTRACCION segundos. `segundos`: lo estimado (o None)."""

    def __init__(self, segundos=None):
        super().__init__('lectura demasiado lenta')
        self.segundos = segundos


class Plazo:
    """Corta la extracción si, al ritmo de lectura de los primeros segundos, no acabaría a tiempo."""

    def __init__(self, limite=None, reloj=None, muestra=None):
        self.limite = LIMITE_EXTRACCION if limite is None else limite
        self.muestra = MUESTRA_EXTRACCION if muestra is None else muestra
        self.reloj = reloj or time.monotonic
        self.inicio = self.reloj()
        self._n = 0

    def comprobar(self, hecho, total):
        """`hecho` de `total` (bytes leídos, muestras…). Lanza Lento si no da tiempo."""
        self._n += 1
        if self._n % 64:                   # mirar el reloj cada 64 bloques basta
            return
        t = self.reloj() - self.inicio
        estimado = t * total / hecho if hecho > 0 and total > 0 else None
        if t > self.limite or (t >= self.muestra and estimado is not None and estimado > self.limite):
            raise Lento(estimado)


def _sin_plazo():
    return Plazo(limite=float('inf'))


def _ts(ms):
    ms = max(0, int(round(ms)))
    return '%02d:%02d:%02d,%03d' % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def _a_srt(lineas):
    """[(inicio_ms, fin_ms, texto)] -> texto SRT con CRLF."""
    lineas = sorted(l for l in lineas if l[2])
    return ''.join(f'{k}\r\n{_ts(a)} --> {_ts(b)}\r\n{txt.replace(chr(10), chr(13) + chr(10))}\r\n\r\n'
                   for k, (a, b, txt) in enumerate(lineas, 1))


# ---------- Pistas de subtítulos incrustadas en MKV (sin ffmpeg/mkvtoolnix) ----------

def _vint(f):
    """Tamaño EBML; None si es 'desconocido' o fin de archivo."""
    b = f.read(1)
    if not b:
        return None
    b = b[0]; l = 1; m = 0x80
    while l <= 8 and not b & m:
        m >>= 1; l += 1
    v = b & (m - 1); unk = v == m - 1
    for x in f.read(l - 1):
        v = (v << 8) | x; unk = unk and x == 0xFF
    return None if unk else v


def _vint_b(d, p):
    b = d[p]; l = 1; m = 0x80
    while l <= 8 and not b & m:
        m >>= 1; l += 1
    if l > 8:                    # byte 0x00: sin este tope el bucle no terminaba nunca
        raise ArchivoInvalido(tr('número de pista no válido en un bloque MKV'))
    v = b & (m - 1)
    for x in d[p + 1:p + l]:
        v = (v << 8) | x
    return v, p + l


def _eid(f):
    b = f.read(1)
    if not b:
        return None
    b0 = b[0]; l = 1; m = 0x80
    while l <= 4 and not b0 & m:
        m >>= 1; l += 1
    v = b0
    for x in f.read(l - 1):
        v = (v << 8) | x
    return v


def _leer(f, n, maximo=MAX_ELEMENTO):
    """Lee exactamente n bytes; error si falta el tamaño, es anormal o el archivo se acaba antes.

    Sin esta comprobación, un MKV cortado o manipulado dejaba los bucles de lectura leyendo
    datos vacíos al final del archivo para siempre.
    """
    if n is None or n > maximo:
        raise ArchivoInvalido(tr('tamaño de elemento no válido'))
    d = f.read(n)
    if len(d) < n:
        raise ArchivoInvalido(tr('el archivo se acaba antes de tiempo'))
    return d


def pistas_mkv(path):
    """Lista de dicts {num, codec, lang, ietf, name, forced} de las pistas del MKV."""
    pistas = []
    with open(path, 'rb') as f:
        if _eid(f) != 0x1A45DFA3:
            return []
        f.seek(_vint(f), 1)
        if _eid(f) != 0x18538067:
            return []
        _vint(f)
        for _ in range(50):
            i = _eid(f); s = _vint(f)
            if i is None or s is None:
                break
            if i != 0x1654AE6B:
                f.seek(s, 1); continue
            fin = f.tell() + s
            while f.tell() < fin:
                _eid(f); s2 = _vint(f)
                if s2 is None:
                    raise ArchivoInvalido(tr('pista sin tamaño'))
                fin_t = f.tell() + s2
                t = {'lang': 'eng', 'ietf': '', 'name': '', 'forced': 0, 'codec': ''}
                while f.tell() < fin_t:
                    j = _eid(f); d = _leer(f, _vint(f))
                    if j == 0xD7: t['num'] = int.from_bytes(d, 'big')
                    elif j == 0x86: t['codec'] = d.decode('ascii', 'replace')
                    elif j == 0x22B59C: t['lang'] = d.decode('ascii', 'replace')
                    elif j == 0x22B59D: t['ietf'] = d.decode('ascii', 'replace')
                    elif j == 0x536E: t['name'] = d.decode('utf-8', 'replace')
                    elif j == 0x55AA: t['forced'] = int.from_bytes(d, 'big')
                pistas.append(t)
            break
    return pistas


def extraer_srt_mkv(path, nums, plazo=None):
    """Extrae pistas S_TEXT/UTF8 del MKV. Devuelve {num: texto_srt}. Salta los datos de vídeo/audio."""
    plazo = plazo or _sin_plazo()
    nums = set(nums)
    subs = {n: [] for n in nums}
    escala, ctc = 1_000_000, 0

    def bloque(d, dur):
        tn, p = _vint_b(d, 0)
        if tn not in nums:
            return
        t = (ctc + int.from_bytes(d[p:p + 2], 'big', signed=True)) * escala / 1e6
        fin = t + dur * escala / 1e6 if dur else t + 2000
        subs[tn].append((t, fin, d[p + 3:].decode('utf-8', 'replace').strip()))

    with open(path, 'rb') as f:
        size = f.seek(0, 2); f.seek(0)
        _eid(f); f.seek(_vint(f), 1); _eid(f); _vint(f)
        while f.tell() < size:
            plazo.comprobar(f.tell(), size)
            i = _eid(f)
            if i is None:
                break
            s = _vint(f)
            if i == 0x1F43B675:          # Cluster: entrar
                continue
            if s is None:
                continue
            if i == 0x1549A966:          # Info: TimecodeScale
                fin = f.tell() + s
                while f.tell() < fin:
                    j = _eid(f); d = _leer(f, _vint(f))
                    if j == 0x2AD7B1:
                        escala = int.from_bytes(d, 'big')
            elif i == 0xE7:              # Timecode del cluster
                ctc = int.from_bytes(_leer(f, s), 'big')
            elif i == 0xA3:              # SimpleBlock
                tn, _ = _vint_b(f.read(1) + b'\0' * 8, 0); f.seek(-1, 1)
                if tn in nums:
                    bloque(_leer(f, s), None)
                else:
                    f.seek(s, 1)
            elif i == 0xA0:              # BlockGroup
                fin = f.tell() + s; blk = None; dur = None
                while f.tell() < fin:
                    j = _eid(f); s2 = _vint(f)
                    if s2 is None:
                        raise ArchivoInvalido(tr('bloque sin tamaño'))
                    if j == 0xA1:
                        blk = _leer(f, s2)
                    elif j == 0x9B:
                        dur = int.from_bytes(_leer(f, s2), 'big')
                    else:
                        f.seek(s2, 1)
                if blk:
                    bloque(blk, dur)
            else:
                f.seek(s, 1)

    return {n: _a_srt(lineas) for n, lineas in subs.items()}


# ---------- Pistas de subtítulos incrustadas en MP4/M4V/MOV (sin ffmpeg) ----------
# Solo se lee la caja 'moov' (índice de muestras, unos pocos MB) y luego las muestras de
# las pistas de subtítulos, saltando directamente a su posición: no se lee vídeo ni audio.

def _cajas(d, ini, fin):
    """Itera las cajas ISO-BMFF de d[ini:fin] -> (tipo, inicio_datos, fin)."""
    while ini + 8 <= fin:
        tam, tipo = struct.unpack_from('>I4s', d, ini); cab = 8
        if tam == 1:
            tam = struct.unpack_from('>Q', d, ini + 8)[0]; cab = 16
        elif tam == 0:
            tam = fin - ini
        if tam < cab:
            break
        yield tipo.decode('latin-1'), ini + cab, min(ini + tam, fin)
        ini += tam


def _leer_moov(f):
    tam_arch = f.seek(0, 2); pos = 0
    while pos + 8 <= tam_arch:
        f.seek(pos); cab = f.read(16)
        tam, tipo = struct.unpack_from('>I4s', cab); h = 8
        if tam == 1:
            tam = struct.unpack_from('>Q', cab, 8)[0]; h = 16
        elif tam == 0:
            tam = tam_arch - pos
        if tam < h:
            break
        if tipo == b'moov':
            if tam - h > MAX_MOOV:
                raise ArchivoInvalido(tr('índice MP4 (moov) demasiado grande'))
            f.seek(pos + h)
            return f.read(tam - h)
        pos += tam
    return None


def _trak_mp4(m, ini, fin):
    t = {'num': 0, 'codec': '', 'lang': '', 'ietf': '', 'name': '', 'forced': 0, 'handler': '',
         'escala': 1000, 'stts': [], 'stsc': [], 'stsz': [], 'co': [], 'elst': [], 'chap': [],
         'cajas': {}}

    def rec(i, f_):
        for tipo, a, b in _cajas(m, i, f_):
            v = m[a] if a < len(m) else 0
            if tipo in ('mdia', 'minf', 'stbl', 'udta', 'edts'):
                rec(a, b)
            elif tipo == 'tkhd':
                t['num'] = struct.unpack_from('>I', m, a + (20 if v == 1 else 12))[0]
            elif tipo == 'tref':
                for t2, a2, b2 in _cajas(m, a, b):
                    if t2 == 'chap':
                        t['chap'] += list(struct.unpack_from(f'>{(b2 - a2) // 4}I', m, a2))
            elif tipo == 'hdlr':
                t['handler'] = m[a + 8:a + 12].decode('latin-1')
            elif tipo == 'mdhd':
                t['escala'] = struct.unpack_from('>I', m, a + (20 if v == 1 else 12))[0] or 1000
                c = struct.unpack_from('>H', m, a + (32 if v == 1 else 20))[0]
                if c:
                    t['lang'] = ''.join(chr(((c >> s) & 31) + 0x60) for s in (10, 5, 0))
            elif tipo == 'elng':
                t['ietf'] = m[a + 4:b].split(b'\0')[0].decode('ascii', 'replace')
            elif tipo == 'name':       # título de la pista (udta/name)
                t['name'] = m[a:b].split(b'\0')[0].decode('utf-8', 'replace').strip()
            elif tipo == 'stsd':
                t['codec'] = m[a + 12:a + 16].decode('latin-1')
            elif tipo in ('stts', 'stsc', 'stsz', 'stco', 'co64', 'elst'):
                t['cajas'][tipo] = (a, v)   # se leen después, y solo en pistas de subtítulos

    rec(ini, fin)
    return t


def _tablas_mp4(m, t):
    """Lee las tablas de muestras de una pista de subtítulos, con límites de tamaño.

    Antes se leían las de todas las pistas sin límite: un MP4 manipulado (o un vídeo con
    audio PCM) podía declarar miles de millones de muestras y agotar la memoria.
    """
    def entradas(a, desp=4):
        n = struct.unpack_from('>I', m, a + desp)[0]
        if n > MAX_MUESTRAS:
            raise ArchivoInvalido(tr('tabla de muestras MP4 demasiado grande'))
        return n

    cajas = t.pop('cajas')
    if 'stts' in cajas:
        a, _ = cajas['stts']
        t['stts'] = [struct.unpack_from('>II', m, a + 8 + 8 * k) for k in range(entradas(a))]
    if 'stsc' in cajas:
        a, _ = cajas['stsc']
        t['stsc'] = [struct.unpack_from('>III', m, a + 8 + 12 * k) for k in range(entradas(a))]
    if 'stsz' in cajas:
        a, _ = cajas['stsz']
        tam, n = struct.unpack_from('>I', m, a + 4)[0], entradas(a, 8)
        t['stsz'] = [tam] * n if tam else list(struct.unpack_from(f'>{n}I', m, a + 12))
    for tipo, fmt in (('stco', 'I'), ('co64', 'Q')):
        if tipo in cajas:
            a, _ = cajas[tipo]
            t['co'] = list(struct.unpack_from(f'>{entradas(a)}{fmt}', m, a + 8))
    if 'elst' in cajas:
        a, v = cajas['elst']
        fmt, paso = ('>Qq', 20) if v == 1 else ('>Ii', 12)
        t['elst'] = [struct.unpack_from(fmt, m, a + 8 + paso * k) for k in range(entradas(a))]


def pistas_mp4(path):
    """Pistas de subtítulos de texto (tx3g / WebVTT) del MP4, con el mismo formato que pistas_mkv
    más los índices de muestras. Excluye las pistas de capítulos."""
    with open(path, 'rb') as f:
        moov = _leer_moov(f)
    if not moov:
        return []
    escala_mov, traks = 1000, []
    for tipo, a, b in _cajas(moov, 0, len(moov)):
        if tipo == 'mvhd':
            escala_mov = struct.unpack_from('>I', moov, a + (20 if moov[a] == 1 else 12))[0] or 1000
        elif tipo == 'trak':
            traks.append(_trak_mp4(moov, a, b))
    capitulos = {n for t in traks for n in t['chap']}
    pistas = []
    for t in traks:
        if t['codec'] in ('tx3g', 'wvtt') and t['num'] not in capitulos:
            _tablas_mp4(moov, t)
            t['escala_mov'] = escala_mov
            t['lang'] = t['lang'] or 'und'
            pistas.append(t)
    return pistas


def _texto_muestra(d, codec):
    if codec == 'wvtt':
        partes = [d[a2:b2].decode('utf-8', 'replace')
                  for tipo, a, b in _cajas(d, 0, len(d)) if tipo == 'vttc'
                  for t2, a2, b2 in _cajas(d, a, b) if t2 == 'payl']
        return '\n'.join(partes).strip()
    n = int.from_bytes(d[:2], 'big')
    raw = d[2:2 + n]
    if raw[:2] == b'\xfe\xff':
        txt = raw[2:].decode('utf-16-be', 'replace')
    else:
        txt = raw.decode('utf-8', 'replace')
    return txt.replace('\r\n', '\n').replace('\r', '\n').strip()


def _muestras_mp4(f, p, plazo):
    """[(inicio_ms, fin_ms, texto)] de una pista de subtítulos MP4."""
    tams, stsc = p['stsz'], p['stsc']
    if not stsc or not tams:
        return []                    # MP4 fragmentado (moof): no soportado
    offs, k = [], 0
    for ci, base in enumerate(p['co'], 1):
        while k + 1 < len(stsc) and stsc[k + 1][0] <= ci:
            k += 1
        for _ in range(stsc[k][1]):
            if len(offs) >= len(tams):
                break
            offs.append(base)
            base += tams[len(offs) - 1]
    # Una entrada de 'stts' puede declarar miles de millones de muestras: solo hacen falta tantas
    # duraciones como muestras tiene la pista.
    durs = []
    for n, d in p['stts']:
        durs.extend([d] * min(n, len(tams) - len(durs)))
        if len(durs) >= len(tams):
            break
    # Lista de edición: un hueco inicial retrasa la pista; un media_time > 0 la adelanta.
    desfase = 0.0
    for dur_seg, t_media in p['elst']:
        if t_media == -1:
            desfase += dur_seg / p['escala_mov']
        else:
            desfase -= t_media / p['escala']
            break
    lineas, t = [], 0
    for i, (o, tam) in enumerate(zip(offs, tams)):
        plazo.comprobar(i, len(tams))
        d = durs[i] if i < len(durs) else 0
        if tam > MAX_ELEMENTO:
            raise ArchivoInvalido(tr('muestra de subtítulo MP4 demasiado grande'))
        if tam > 2:
            f.seek(o)
            texto = _texto_muestra(f.read(tam), p['codec'])
            if texto:
                ini = (t / p['escala'] + desfase) * 1000
                fin = ((t + d) / p['escala'] + desfase) * 1000
                if lineas and lineas[-1][2] == texto and abs(lineas[-1][1] - ini) < 1:
                    lineas[-1] = (lineas[-1][0], fin, texto)     # WebVTT parte una frase en varias muestras
                else:
                    lineas.append((ini, fin, texto))
        t += d
    return lineas


def extraer_srt_mp4(path, nums, plazo=None):
    plazo = plazo or _sin_plazo()
    nums = set(nums)
    pistas = [p for p in pistas_mp4(path) if p['num'] in nums]
    with open(path, 'rb') as f:
        return {p['num']: _a_srt(_muestras_mp4(f, p, plazo)) for p in pistas}


# ---------- Pistas incrustadas (común a MKV y MP4) ----------

def pistas_texto(path):
    ext = path.suffix.lower()
    if ext in MKV_EXT:
        return [p for p in pistas_mkv(path) if p['codec'] == 'S_TEXT/UTF8']
    if ext in MP4_EXT:
        return pistas_mp4(path)
    return []


def extraer_srt(path, nums, plazo=None):
    """{num: texto_srt}. Con `plazo`, lanza Lento si la lectura no va a acabar a tiempo."""
    return (extraer_srt_mkv if path.suffix.lower() in MKV_EXT else extraer_srt_mp4)(path, nums, plazo)


def _forzada(p):
    return p.get('forced') or re.search(r'forced|forzad', p['name'], re.IGNORECASE)


def _es_espanol(p):
    return p['lang'] in ('spa', 'es') or p['ietf'].lower().startswith('es')


def _es_ingles(p):
    return p['lang'] in ('eng', 'en') or p['ietf'].lower().startswith('en')


def _etiqueta_latina(p):
    ietf = p['ietf'].lower()
    return (ietf.startswith('es-') and ietf != 'es-es') or bool(LATINO_NOMBRE.search(p['name']))


def _etiqueta_espana(p):
    return p['ietf'].lower() == 'es-es' or bool(ESPANA_NOMBRE.search(p['name']))


def _nada(linea):
    pass


def _duracion(segundos):
    if segundos is None:
        return tr('más de {n} s', n=LIMITE_EXTRACCION)
    if segundos < 90:
        return tr('unos {n} s', n=round(segundos))
    return tr('unos {n} min', n=round(segundos / 60))


def aviso_lento(e, ingles=False):
    que = tr('los subtítulos en inglés') if ingles else tr('los subtítulos incrustados')
    return tr('  no se han extraído {que} del propio vídeo porque leerlo era muy lento '
              '(tardaría {tiempo}; el límite es {limite} s)', que=que, tiempo=_duracion(e.segundos),
              limite=LIMITE_EXTRACCION)


def _desc(p):
    """Descripción corta de una pista para el resumen: 'pista 3 Español (España)'."""
    return visible(f"{tr('pista {n}', n=p['num'])} {p['name']}".strip())


def incrustado(path, con_ingles=False, detalle=_nada, limite=None):
    """Busca en las pistas de texto del MKV/MP4.
    Devuelve {'castellano', 'latino', 'ingles'} -> (texto, descripción) o None, y 'lento': True si
    no se ha extraído porque leer el vídeo tardaría más de `limite` segundos (LIMITE_EXTRACCION).
    `detalle` recibe las líneas informativas (la CLI las imprime)."""
    res = {'castellano': None, 'latino': None, 'ingles': None, 'lento': False}
    try:
        pistas = [p for p in pistas_texto(path) if not _forzada(p)]
    except Exception as e:
        detalle(tr('  (no se pudieron leer las pistas incrustadas: {error})', error=visible(e)))
        return res
    if not pistas:
        return res
    detalle(tr('  {n} pistas de subtítulos incrustadas', n=len(pistas)))
    esp = [p for p in pistas if _es_espanol(p)]
    eng = sorted((p for p in pistas if _es_ingles(p)), key=lambda p: 'sdh' not in p['name'].lower())
    nums = [p['num'] for p in esp] + ([eng[0]['num']] if eng and con_ingles else [])
    if not nums:
        return res
    try:
        textos = extraer_srt(path, nums, Plazo(limite))
    except Lento as e:
        detalle(aviso_lento(e))
        res['lento'] = True
        return res
    except Exception as e:
        detalle(tr('  (no se pudieron extraer las pistas incrustadas: {error})', error=visible(e)))
        return res
    cast, lat = [], []
    for p in esp:
        texto = textos.get(p['num'])
        if not texto or len(texto) > MAX_SRT:
            continue
        es, la, ok = dialecto(texto)
        detalle(tr('  pista incrustada {n} [{idioma}] {nombre}: españa={es} latino={la}', n=p['num'],
                   idioma=visible(p['ietf'] or p['lang']), nombre=visible(p['name']), es=es, la=la))
        desc = _desc(p)
        # En las pistas oficiales la etiqueta latina es fiable, y el detector de dialecto no
        # basta (una pista "LA" de Disney+ dio españa=26 latino=11 y pasaba por castellano).
        if ok and not _etiqueta_latina(p):
            cast.append(((_etiqueta_espana(p), es / (la + 1)), texto, desc))
        else:
            lat.append(((_etiqueta_latina(p), la), texto, desc))
    if cast:
        res['castellano'] = max(cast, key=lambda c: c[0])[1:]
    if lat:
        res['latino'] = max(lat, key=lambda c: c[0])[1:]
    if eng and con_ingles and textos.get(eng[0]['num']) and len(textos[eng[0]['num']]) <= MAX_SRT:
        res['ingles'] = (textos[eng[0]['num']], _desc(eng[0]))
    return res


def ingles_incrustado(path, detalle=_nada, limite=None):
    """Extrae la mejor pista inglesa de texto del MKV/MP4 (prefiere SDH). Devuelve (texto | None, nombre)."""
    try:
        pistas = [p for p in pistas_texto(path) if not _forzada(p) and _es_ingles(p)]
        if not pistas:
            return None, ''
        pistas.sort(key=lambda p: 'sdh' not in p['name'].lower())
        texto = extraer_srt(path, [pistas[0]['num']], Plazo(limite)).get(pistas[0]['num'])
    except Lento as e:
        detalle(aviso_lento(e, ingles=True))
        return None, ''
    except Exception:
        return None, ''
    if not texto or len(texto) > MAX_SRT:
        return None, ''
    return texto, _desc(pistas[0])
