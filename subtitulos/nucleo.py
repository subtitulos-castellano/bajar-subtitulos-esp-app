"""Búsqueda de subtítulos en castellano para los vídeos de una carpeta: `procesar()`.

El subtítulo principal se guarda como <video>.srt (mismo nombre que el vídeo), para que
cualquier reproductor lo cargue solo. Orden de preferencia: castellano > latino > inglés.
Nunca se sustituye un .srt por otro de un tipo peor.

Primero mira las pistas de texto incrustadas en el vídeo (MKV y MP4, sin ffmpeg); si no
hay castellano, busca en todos los proveedores útiles, descarga todos los candidatos en
español y elige solo los que son castellano de España (por vocabulario), del episodio
correcto y con una duración compatible con el vídeo. Las etiquetas de idioma de las webs
NO son fiables (se han visto latinos marcados como "es" y episodios mal etiquetados), por
eso se comprueba el texto.

Con `Opciones.modo`:
- 'ingles': solo inglés, como <video>.srt (pista incrustada, <video>.en.srt que ya hubiera o proveedores).
  Sustituye el .srt que hubiera en otro idioma (con copia de seguridad).
- 'traducido': el inglés (de <video>.en.srt, de la pista incrustada o de los proveedores) traducido
  automáticamente al castellano sin conexión (traducir.py), como <video>.srt; el inglés se guarda
  también como <video>.en.srt. Sustituye el .srt que hubiera (con copia de seguridad).

`procesar()` no escribe nada en pantalla: avisa de lo que pasa a un objeto `Eventos`. La CLI
lo convierte en texto y la app en su interfaz.
"""
import contextlib
import itertools
import json
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path

from babelfish import Language
from dogpile.cache.exception import RegionAlreadyConfigured
from guessit import guessit
from subliminal import region, refine, scan_video
from subliminal.core import ProviderPool
from subliminal.score import compute_score, episode_scores, movie_scores
from subliminal.video import Episode

from .archivos import HOME, VIDEO_EXT, buscar_en_varias, buscar_videos  # noqa: F401
from .eventos import (CASTELLANO, INGLES, LATINO, NO_ENCONTRADO, PENDIENTE, SIN_CAMBIOS,  # noqa: F401
                      SOLO_INGLES, TRADUCIDO, YA_CASTELLANO, YA_INGLES, YA_TRADUCIDO, Eventos, Resultado)
from .idioma import N_, tr
from .opciones import MAX_DESCARGAS, Opciones
from .pistas import incrustado, ingles_incrustado
from .texto import MAX_SRT, dialecto, idioma_srt, limpiar_texto, ultimo_tiempo, visible

# opensubtitlescom (opensubtitles.com, otra cuenta distinta de la de .org) no va aquí: tiene un cupo
# pequeño de descargas al día, así que solo se le pide como último recurso (ver _UltimoRecurso).
# subtis (Argentina) y napiprojekt (polaco) no aportan castellano.
# podnapisi: el dominio dejó de resolver en 2026 (podnapisi.net sin registro A, www sin DNS).
# tvsubtitles: la búsqueda (search.php) responde 403 a programas. Además, ambos daban latino.
PROVIDERS = ['opensubtitles', 'addic7ed', 'gestdown', 'subtitulamos']
ULTIMO = 'opensubtitlescom'
PAUSA = 3           # segundos de espera entre un vídeo que busca en internet y el siguiente

# Una traducción automática (de este programa) vale más que el inglés y menos que un subtítulo en español
# hecho por personas.
RANGO = {None: 0, 'otro': 0, 'ingles': 1, 'traducido': 2, 'latino': 3, 'castellano': 4}
ETIQUETA = {'castellano': N_('CASTELLANO'), 'latino': N_('LATINO'), 'ingles': N_('INGLÉS'),
            'traducido': N_('TRADUCIDO')}

# Idioma de un .srt que ya existe (idioma_srt), en el registro.
# (En castellano, 'ingles' sin tilde: la salida de la CLI no cambia.)
IDIOMA_SRT = {'castellano': N_('castellano'), 'latino': N_('latino'), 'ingles': N_('ingles'),
              'traducido': N_('castellano traducido automáticamente'), 'otro': N_('otro')}


def ya_tenia(tipo):
    """Estado del resumen cuando se deja el .srt que había: 'LATINO (ya tenía .srt)'."""
    return tr('{tipo} (ya tenía .srt)', tipo=tr(ETIQUETA[tipo]))


def preparar_cache():
    """La caché de subliminal, en memoria (la usan las búsquedas y la sesión de opensubtitles.com)."""
    if not region.is_configured:
        try:
            region.configure('dogpile.cache.memory')
        except RegionAlreadyConfigured:     # otra búsqueda la ha configurado a la vez
            pass


def leer_credenciales():
    """Configuración de proveedores de ~/.subtitulos-esp/credenciales.json ({} si no existe)."""
    cred = HOME / 'credenciales.json'
    if cred.exists():
        return json.loads(cred.read_text(encoding='utf-8'))
    return {}


# Coincidencias de la puntuación de subliminal que indican que el subtítulo va sincronizado:
# el mismo archivo (hash) o el mismo release (grupo, plataforma, fps). El resto (source,
# resolución, códecs: 1-4 puntos) apenas dice nada de la sincronía.
SINCRONIA = ('hash', 'release_group', 'streaming_service', 'fps')


def sincronia(sub, video):
    """Parte de la puntuación de subliminal que indica sincronía con este vídeo."""
    pesos = episode_scores if isinstance(video, Episode) else movie_scores
    coincidencias = sub.get_matches(video)
    return sum(pesos[m] for m in SINCRONIA if m in coincidencias)


def mejores_candidatos(candidatos, video, maximo):
    """Los `maximo` candidatos que merece la pena descargar, alternando proveedores.

    Dentro de cada proveedor se ordenan por sincronía y puntuación, y se van tomando por
    rondas (el mejor de cada proveedor, luego el segundo...). Así un proveedor con muchos
    resultados empatados (OpenSubtitles) no deja fuera al mejor de otro (Addic7ed), y la
    carga se reparte entre servicios.
    """
    por_proveedor = {}
    for sub in sorted(candidatos, key=lambda s: (sincronia(s, video), compute_score(s, video)),
                      reverse=True):
        por_proveedor.setdefault(sub.provider_name, []).append(sub)
    rondas = itertools.zip_longest(*por_proveedor.values())
    return [sub for ronda in rondas for sub in ronda if sub is not None][:maximo]


def episodio_correcto(sub, video):
    """Rechaza subtítulos cuyo nombre de release indica otro episodio."""
    if not isinstance(video, Episode):
        return True
    nombres = [getattr(sub, a, None) for a in ('movie_release_name', 'release_info', 'filename', 'title')]
    for nombre in filter(None, nombres):
        if not isinstance(nombre, str):
            continue
        g = guessit(nombre, {'type': 'episode'})
        ep, temp = g.get('episode'), g.get('season')
        if isinstance(ep, int) and video.episode and ep != video.episode:
            return False
        if isinstance(temp, int) and video.season and temp != video.season:
            return False
    return True


def duracion_ok(texto, video):
    dur = getattr(video, 'duration', None)
    fin = ultimo_tiempo(texto)
    if not dur or not fin:
        return True
    return 0.6 * dur <= fin <= dur + 120


def _seguir():
    pass


class _UltimoRecurso:
    """opensubtitles.com, con la misma forma que un ProviderPool (list_subtitles y download_subtitle).

    Solo se usa si hay cuenta y solo cuando los demás proveedores no han dado castellano (o, al final,
    inglés). Su pool se abre (e inicia sesión) la primera vez que hace falta. Se deja de usar en toda la
    búsqueda en cuanto falla (cuenta incorrecta, servicio caído) o se agota el cupo de descargas del día.
    Tras cada descarga, el servidor dice cuántas quedan: se avisa en Detalles."""

    def __init__(self, configs, detalle, pila):
        self.config = configs.get(ULTIMO)
        self.activo = isinstance(self.config, dict)
        self._detalle = detalle
        self._pila = pila
        self._pool = None
        self.restantes = None
        self._informado = None

    def _abrir(self):
        if self._pool is None:
            self._pool = self._pila.enter_context(ProviderPool(providers=[ULTIMO],
                                                               provider_configs={ULTIMO: self.config}))
        return self._pool

    def _vigilar_cupo(self):
        """Apunta las descargas que quedan (subliminal no las guarda): de la respuesta del servidor."""
        proveedor = getattr(self._pool, 'initialized_providers', {}).get(ULTIMO)
        if proveedor is None or getattr(proveedor, '_vigilado', False) or not hasattr(proveedor, 'api_post'):
            return
        original = proveedor.api_post

        def api_post(path, body=None, **k):
            r = original(path, body, **k)
            if path == 'download' and isinstance(r, dict) and isinstance(r.get('remaining'), int):
                self.restantes = r['remaining']
            return r
        proveedor.api_post = api_post
        proveedor._vigilado = True

    def _apagar(self, motivo):
        self.activo = False
        self._detalle(motivo)

    def list_subtitles(self, video, idiomas):
        if not self.activo:
            return []
        pool = self._abrir()
        candidatos = pool.list_subtitles(video, idiomas)
        if ULTIMO in pool.discarded_providers:
            self._apagar(tr('  opensubtitles.com no responde o no acepta la cuenta: no se le pide nada más en '
                            'esta búsqueda'))
            return []
        self._vigilar_cupo()
        return candidatos

    def download_subtitle(self, sub):
        if not self.activo:
            return False
        ok = self._pool.download_subtitle(sub)
        if ULTIMO in self._pool.discarded_providers:
            # Las dos cosas se notan aquí: la búsqueda no inicia sesión, la primera descarga sí.
            self._apagar(tr('  opensubtitles.com no deja descargar (cupo de hoy agotado o cuenta no válida): no '
                            'se le pide nada más en esta búsqueda'))
            return False
        return ok

    def informar(self):
        """Descargas que quedan hoy, si han cambiado desde el último aviso."""
        if self.activo and self.restantes is not None and self.restantes != self._informado:
            self._informado = self.restantes
            self._detalle(tr('  opensubtitles.com: quedan {n} descargas por hoy', n=self.restantes))


def ingles_proveedores(pool, video, max_descargas=MAX_DESCARGAS, detalle=lambda linea: None, comprobar=_seguir):
    """Busca subtítulos en inglés; descarga por orden de puntuación hasta encontrar uno válido."""
    candidatos = pool.list_subtitles(video, {Language('eng')})
    candidatos.sort(key=lambda s: compute_score(s, video), reverse=True)
    for sub in candidatos[:max_descargas]:
        comprobar()
        if not pool.download_subtitle(sub) or not sub.content:
            continue
        texto = sub.text
        if len(texto) > MAX_SRT:
            detalle(tr('  [inglés] {proveedor:13} id={id} descartado: tamaño anormal',
                       proveedor=sub.provider_name, id=visible(sub.id)))
            continue
        ep_ok = episodio_correcto(sub, video)
        dur_ok = duracion_ok(texto, video)
        detalle(tr('  [inglés] {proveedor:13} id={id} score={score} episodio_ok={ep_ok} duración_ok={dur_ok}',
                   proveedor=sub.provider_name, id=visible(sub.id), score=compute_score(sub, video),
                   ep_ok=ep_ok, dur_ok=dur_ok))
        if ep_ok and dur_ok:
            return texto, sub
    return None, None


def guardar(texto, destino):
    if destino.exists():
        bk = HOME / 'backup' / f'{datetime.now():%Y%m%d-%H%M%S}_{destino.name}'
        bk.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destino, bk)
    # El texto viene de terceros: se guarda sin caracteres de control ni de dirección del texto.
    destino.write_text(limpiar_texto(texto), encoding='utf-8', newline='')


class SinRuido(logging.Filter):
    """subliminal escribe trazas largas en stderr y el refinador omdb da 401 siempre.

    Se descartan, porque no cambian el resultado:
    - los fallos de refinado (omdb...);
    - el cierre de sesión de opensubtitles.org (el servidor ya no tiene el método
      `close`, pero la búsqueda y las descargas funcionan);
    - los avisos de knowit (largos banners de "ffprobe/mkvmerge not found": el script lee
      las pistas MKV/MP4 por su cuenta y no necesita esos programas).
    Del resto de avisos se deja una sola línea, sin traza. Así la salida es limpia en
    cualquier shell y agente sin tener que filtrarla con grep / Where-Object.
    """

    def filter(self, record):
        mensaje = record.getMessage()
        if (record.name.startswith('knowit') or 'Failed to refine' in mensaje
                or 'improperly terminated' in mensaje
                # opensubtitles.com sin cupo: ya lo dice Detalles, en el idioma de la app
                or 'download quota exceeded' in mensaje or f'Discarding provider {ULTIMO}' in mensaje):
            return False
        record.exc_info = record.exc_text = None
        return True


def _esperar(segundos, cancelado):
    """Pausa entre vídeos que se puede interrumpir. Devuelve True si se ha cancelado."""
    fin = time.monotonic() + segundos
    while (resto := fin - time.monotonic()) > 0:
        if cancelado():
            return True
        time.sleep(min(resto, 0.2))
    return cancelado()


def _no_cancelado():
    return False


class _Cancelado(Exception):
    """Uso interno: corta procesar() en cuanto se cancela, sin esperar a terminar el vídeo."""


def procesar(ruta, opciones=None, eventos=None, cancelado=None, credenciales=None, recursivo=True, traductor=None):
    """Busca y guarda subtítulos para un vídeo o para todos los de una carpeta (con sus subcarpetas,
    salvo `recursivo=False`).

    `ruta` también puede ser una lista de vídeos y carpetas: se revisan todos juntos, como si
    estuvieran en la misma carpeta (el límite de vídeos cuenta sobre el conjunto).

    - `opciones`: `Opciones` (por defecto, las de la CLI sin parámetros).
    - `eventos`: `Eventos` que recibe el progreso, las líneas informativas y los resultados.
    - `cancelado`: función sin argumentos; si devuelve True, se para en el siguiente punto de
      control: entre vídeos, durante la pausa, entre consultas a los proveedores y antes de
      escribir. Tras cancelar no se escribe nada más; lo ya guardado se queda guardado.
    - `credenciales`: configuración de proveedores ({'opensubtitles': {...}, 'opensubtitlescom': {...}},
      cada una con 'username' y 'password'; .com solo como último recurso); None = leer
      ~/.subtitulos-esp/credenciales.json.
    - `traductor`: solo en el modo 'traducido', función que traduce una lista de frases del inglés
      (traducir.Motor); None = cargar el modelo descargado (modelo.motor(), que lanza ErrorModelo si falta).

    Devuelve la lista de `Resultado` (el resumen).
    """
    opciones = opciones or Opciones()
    eventos = eventos or Eventos()
    cancelado = cancelado or _no_cancelado
    detalle = eventos.detalle
    max_descargas = opciones.max_descargas or None  # None: sin límite

    def comprobar():
        if cancelado():
            raise _Cancelado

    def escribir(texto, destino):
        comprobar()
        if opciones.dry_run:
            detalle(tr('  [dry-run] guardaría {nombre}', nombre=destino.name))
        else:
            guardar(texto, destino)

    preparar_cache()
    configs = leer_credenciales() if credenciales is None else credenciales
    providers = [p for p in PROVIDERS if p != 'opensubtitles' or 'opensubtitles' in configs]

    if isinstance(ruta, (list, tuple)):
        videos = buscar_en_varias(ruta, recursivo)
    else:
        videos = buscar_videos(Path(ruta), recursivo)
    eventos.inicio(videos)
    resultados = []

    def anotar(path, estado, fuente, categoria):
        r = Resultado(path, estado, fuente, categoria)
        resultados.append(r)
        eventos.resultado(r)

    if opciones.modo == 'traducido' and traductor is None and videos:
        from .modelo import motor
        traductor = motor()
    try:
        _recorrer(videos, opciones, eventos, cancelado, comprobar, escribir, anotar, detalle,
                  max_descargas, providers, configs, traductor)
    except _Cancelado:
        pass
    return resultados


def _leer_srt(ruta):
    """Texto de un .srt que ya existe (sin convertir los saltos de línea), o None."""
    try:
        with open(ruta, encoding='utf-8', errors='replace', newline='') as f:
            return f.read(MAX_SRT + 1)
    except OSError:
        return None


def _recorrer(videos, opciones, eventos, cancelado, comprobar, escribir, anotar, detalle, max_descargas,
              providers, configs, traductor=None):
    buscados = 0  # vídeos que ya han buscado en internet en esta ejecución
    with contextlib.ExitStack() as pila:
        pool = pila.enter_context(ProviderPool(providers=providers, provider_configs=configs))
        ultimo = _UltimoRecurso(configs, detalle, pila)

        def internet(path):
            """Antes de buscar en internet: límite por ejecución y pausa entre vídeos. Devuelve el vídeo
            para los proveedores, o None si queda pendiente."""
            nonlocal buscados
            if opciones.max_videos and buscados >= opciones.max_videos:
                detalle(tr('  límite de {n} vídeos con búsqueda en internet alcanzado: queda para otra ejecución',
                           n=opciones.max_videos))
                anotar(path, tr('PENDIENTE (límite)'), tr('máx. {n} por ejecución', n=opciones.max_videos),
                       PENDIENTE)
                return None
            if buscados and _esperar(PAUSA, cancelado):
                raise _Cancelado
            buscados += 1

            video = scan_video(str(path))
            # scan_video adivina sobre la ruta completa: una carpeta como "<SERIE> - FULL"
            # convierte la serie en "<SERIE> FULL" y ningún proveedor encuentra nada.
            if isinstance(video, Episode):
                g = guessit(path.name)
                if g.get('title'):
                    video.series = g['title']
                    video.title = g.get('episode_title')
            refine(video, refiners=['hash', 'metadata', 'tvdb'])
            comprobar()
            return video

        def ingles_internet(video):
            """(texto, sub) del mejor inglés de los proveedores (opensubtitles.com, como último recurso)."""
            texto, sub = ingles_proveedores(pool, video, max_descargas, detalle, comprobar)
            if not texto and ultimo.activo:
                texto, sub = ingles_proveedores(ultimo, video, max_descargas, detalle, comprobar)
                ultimo.informar()
            return texto, sub

        def ingles_de(path, usar_en_srt):
            """El inglés de un vídeo, para los modos 'ingles' y 'traducido': (texto, estado, fuente, origen)
            con origen 'en.srt', 'incrustado' o 'internet'; (None, ...) si no hay; None si queda pendiente."""
            destino_en = path.with_suffix('.en.srt')
            if usar_en_srt and not opciones.force and destino_en.exists():
                texto = _leer_srt(destino_en)
                if texto and len(texto) <= MAX_SRT and idioma_srt(texto) == 'ingles':
                    return texto, '.en.srt', destino_en.name, 'en.srt'
            texto, pista = ingles_incrustado(path, detalle)
            comprobar()
            if texto:
                return texto, 'incrustado', pista[:30], 'incrustado'
            video = internet(path)
            if video is None:
                return None
            texto, sub = ingles_internet(video)
            if texto:
                return texto, '', f'{sub.provider_name} {sub.id}', 'internet'
            return None, '', '', ''

        def modo_ingles(path):
            destino = path.with_suffix('.srt')
            previo = _leer_srt(destino) if destino.exists() else None
            actual = idioma_srt(previo) if previo else None
            if actual == 'ingles' and not opciones.force:
                anotar(path, tr('ya tenía inglés'), '-', YA_INGLES)
                return
            detalle(f'\n== {path.name}')
            if actual:
                detalle(tr('  ya tiene {nombre} en {idioma}', nombre=destino.name, idioma=tr(IDIOMA_SRT[actual])))
            hallado = ingles_de(path, usar_en_srt=True)
            if hallado is None:
                return
            texto, _, fuente, origen = hallado
            if not texto:
                anotar(path, tr('NO ENCONTRADO'), tr('sin inglés'), NO_ENCONTRADO)
                return
            escribir(texto, destino)
            estado = {'en.srt': tr('INGLÉS (de .en.srt)'), 'incrustado': tr('INGLÉS (incrustado)')}.get(
                origen, tr('INGLÉS'))
            anotar(path, estado, fuente, SOLO_INGLES)

        def modo_traducido(path):
            destino = path.with_suffix('.srt')
            destino_en = path.with_suffix('.en.srt')
            previo = _leer_srt(destino) if destino.exists() else None
            actual = idioma_srt(previo) if previo else None
            if actual == 'traducido' and not opciones.force:
                anotar(path, tr('ya tenía traducido'), '-', YA_TRADUCIDO)
                return
            detalle(f'\n== {path.name}')
            if actual:
                detalle(tr('  ya tiene {nombre} en {idioma}', nombre=destino.name, idioma=tr(IDIOMA_SRT[actual])))
            # Un .srt en inglés que ya estaba (de antes) también sirve como original.
            if actual == 'ingles' and not destino_en.exists():
                hallado = previo, '.srt', destino.name, 'srt'
            else:
                hallado = ingles_de(path, usar_en_srt=True)
            if hallado is None:
                return
            texto, _, fuente, origen = hallado
            if not texto:
                anotar(path, tr('NO ENCONTRADO'), tr('sin inglés que traducir'), NO_ENCONTRADO)
                return
            detalle(tr('  traduciendo al castellano (sin conexión)...'))
            from .traducir import traducir_srt
            traducido = traducir_srt(texto, traductor, avance=lambda hecho, total: comprobar())
            if origen != 'en.srt' and (opciones.force or not destino_en.exists()):
                escribir(texto, destino_en)          # el original en inglés, junto al traducido
            escribir(traducido, destino)
            estado = {'en.srt': tr('TRADUCIDO (de .en.srt)'), 'srt': tr('TRADUCIDO (de su .srt)'),
                      'incrustado': tr('TRADUCIDO (incrustado)')}.get(origen, tr('TRADUCIDO'))
            anotar(path, estado, fuente, TRADUCIDO)

        def modo_castellano(path):
            destino = path.with_suffix('.srt')
            # Formato antiguo: <video>.es.srt (o .en.srt si no había español) -> <video>.srt
            previo = destino if destino.exists() else next(
                (p for p in (path.with_suffix('.es.srt'), path.with_suffix('.en.srt')) if p.exists()), None)
            actual = idioma_srt(previo.read_text(encoding='utf-8', errors='replace')) if previo else None
            nota = '-'
            if previo and previo != destino:
                nota = tr('renombrado desde {extension}.srt', extension=previo.suffixes[-2])
                if opciones.dry_run:
                    detalle(tr('  [dry-run] renombraría {previo} -> {destino}', previo=previo.name,
                               destino=destino.name))
                else:
                    previo.rename(destino)

            if actual == 'castellano' and not opciones.force:
                anotar(path, tr('ya tenía castellano'), nota, YA_CASTELLANO)
                return

            detalle(f'\n== {path.name}')
            if actual:
                detalle(tr('  ya tiene {nombre} en {idioma}', nombre=destino.name, idioma=tr(IDIOMA_SRT[actual])))

            def aplicar(tipo, texto, estado, fuente):
                """Guarda como <video>.srt salvo que el que ya hay sea de un tipo mejor."""
                if RANGO[tipo] > RANGO[actual] or (opciones.force and RANGO[tipo] == RANGO[actual]):
                    escribir(texto, destino)
                    anotar(path, estado, fuente, tipo)
                else:
                    anotar(path, ya_tenia(actual), nota, SIN_CAMBIOS)

            emb = incrustado(path, opciones.ingles, detalle)
            comprobar()
            destino_en = path.with_suffix('.en.srt')
            if emb['ingles'] and (opciones.force or not destino_en.exists()):
                escribir(emb['ingles'][0], destino_en)
            if emb['castellano']:
                aplicar('castellano', emb['castellano'][0], tr('CASTELLANO (incrustado)'), emb['castellano'][1][:30])
                return

            # A partir de aquí se busca en internet: límite por ejecución y pausa entre vídeos.
            video = internet(path)
            if video is None:
                return

            candidatos = pool.list_subtitles(video, {Language('spa')})
            comprobar()
            if max_descargas and len(candidatos) > max_descargas:
                detalle(tr('  {n} candidatos en español: se descargan los {maximo} mejores, alternando proveedores',
                           n=len(candidatos), maximo=max_descargas))
            castellanos, latinos = [], []
            vistos = set()

            def revisar(fuente, candidatos, hasta_el_primero=False):
                """Descarga los mejores candidatos de `fuente` y los clasifica. Con `hasta_el_primero`,
                para en el primer castellano válido (opensubtitles.com: cada descarga gasta cupo)."""
                for sub in mejores_candidatos(candidatos, video, max_descargas):
                    comprobar()
                    if not fuente.download_subtitle(sub) or not sub.content:
                        continue
                    texto = sub.text
                    if len(texto) > MAX_SRT:
                        detalle(tr('  {proveedor:13} id={id} descartado: tamaño anormal', proveedor=sub.provider_name,
                                   id=visible(sub.id)))
                        continue
                    if texto in vistos:
                        continue
                    vistos.add(texto)
                    es, la, ok = dialecto(texto)
                    ep_ok = episodio_correcto(sub, video)
                    dur_ok = duracion_ok(texto, video)
                    score = compute_score(sub, video)
                    sinc = sincronia(sub, video)
                    detalle(tr('  {proveedor:13} id={id} score={score} sincronía={sinc} españa={es} latino={la} '
                               'episodio_ok={ep_ok} duración_ok={dur_ok}', proveedor=sub.provider_name,
                               id=visible(sub.id), score=score, sinc=sinc, es=es, la=la, ep_ok=ep_ok, dur_ok=dur_ok))
                    if not (ep_ok and dur_ok):
                        continue
                    (castellanos if ok else latinos).append((sinc, es, score, sub, texto))
                    if hasta_el_primero and ok:
                        return

            revisar(pool, candidatos)
            if not castellanos and ultimo.activo:
                # Último recurso: opensubtitles.com, solo si los demás no han dado castellano.
                candidatos = ultimo.list_subtitles(video, {Language('spa')})
                comprobar()
                if candidatos:
                    detalle(tr('  opensubtitles.com (último recurso): {n} candidatos en español', n=len(candidatos)))
                    revisar(ultimo, candidatos, hasta_el_primero=True)
                    ultimo.informar()

            if castellanos:
                # 1) sincronía (mismo archivo > mismo release), 2) más señales de castellano,
                # 3) puntuación de subliminal. Antes mandaba la puntuación y un +2 por coincidir
                # en resolución y códec ganaba a un candidato con 5 veces más señales.
                sinc, es, score, sub, texto = max(castellanos, key=lambda c: (c[0], c[1], c[2]))
                aplicar('castellano', texto, tr('CASTELLANO'), f'{sub.provider_name} {sub.id}')
            elif emb['latino'] and not opciones.solo_castellano:
                # La pista incrustada va sincronizada exactamente con el vídeo: mejor que una web.
                aplicar('latino', emb['latino'][0], tr('LATINO (incrustado)'), emb['latino'][1][:30])
            elif latinos and not opciones.solo_castellano:
                sinc, es, score, sub, texto = max(latinos, key=lambda c: (c[0], c[2]))
                aplicar('latino', texto, tr('LATINO'), f'{sub.provider_name} {sub.id}')
            elif RANGO[actual] >= RANGO['ingles'] and (not opciones.force or RANGO[actual] > RANGO['ingles']):
                # Ya hay latino, una traducción o inglés y no se ha encontrado nada mejor: se deja como está.
                anotar(path, ya_tenia(actual), nota, SIN_CAMBIOS)
            elif opciones.sin_ingles:
                anotar(path, tr('NO ENCONTRADO'), tr('{n} latinos descartados', n=len(latinos)), NO_ENCONTRADO)
            else:
                # Ni castellano ni latino: subtítulos en inglés como último recurso.
                texto, pista = (emb['ingles'] or (None, ''))
                if not texto and not emb['lento']:      # si leer el vídeo es lento, no se reintenta
                    texto, pista = ingles_incrustado(path, detalle)
                if texto:
                    aplicar('ingles', texto, tr('INGLÉS (incrustado)'), pista[:30])
                    return
                texto, sub = ingles_internet(video)
                if texto:
                    aplicar('ingles', texto, tr('INGLÉS'), f'{sub.provider_name} {sub.id}')
                else:
                    anotar(path, tr('NO ENCONTRADO'), tr('ni español ni inglés'), NO_ENCONTRADO)

        por_modo = {'ingles': modo_ingles, 'traducido': modo_traducido}.get(opciones.modo, modo_castellano)
        for indice, path in enumerate(videos, 1):
            if cancelado():
                break
            eventos.video(indice, len(videos), path)
            por_modo(path)
