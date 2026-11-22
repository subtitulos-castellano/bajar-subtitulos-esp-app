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

`procesar()` no escribe nada en pantalla: avisa de lo que pasa a un objeto `Eventos`. La CLI
lo convierte en texto y la app en su interfaz.
"""
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
                      YA_CASTELLANO, Eventos, Resultado)
from .opciones import MAX_DESCARGAS, Opciones
from .pistas import incrustado, ingles_incrustado
from .texto import MAX_SRT, dialecto, idioma_srt, limpiar_texto, ultimo_tiempo, visible

# opensubtitlescom queda fuera: se usa la cuenta de opensubtitles.org (son cuentas distintas).
# subtis (Argentina) y napiprojekt (polaco) no aportan castellano.
# podnapisi: el dominio dejó de resolver en 2026 (podnapisi.net sin registro A, www sin DNS).
# tvsubtitles: la búsqueda (search.php) responde 403 a programas. Además, ambos daban latino.
PROVIDERS = ['opensubtitles', 'addic7ed', 'gestdown', 'subtitulamos']
PAUSA = 3           # segundos de espera entre un vídeo que busca en internet y el siguiente

RANGO = {None: 0, 'otro': 0, 'ingles': 1, 'latino': 2, 'castellano': 3}
ETIQUETA = {'castellano': 'CASTELLANO', 'latino': 'LATINO', 'ingles': 'INGLÉS'}

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
            detalle(f'  [inglés] {sub.provider_name:13} id={visible(sub.id)} descartado: tamaño anormal')
            continue
        ep_ok = episodio_correcto(sub, video)
        dur_ok = duracion_ok(texto, video)
        detalle(f'  [inglés] {sub.provider_name:13} id={visible(sub.id)} score={compute_score(sub, video)} '
                f'episodio_ok={ep_ok} duración_ok={dur_ok}')
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
                or 'improperly terminated' in mensaje):
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


def procesar(ruta, opciones=None, eventos=None, cancelado=None, credenciales=None, recursivo=True):
    """Busca y guarda subtítulos para un vídeo o para todos los de una carpeta (con sus subcarpetas,
    salvo `recursivo=False`).

    `ruta` también puede ser una lista de vídeos y carpetas: se revisan todos juntos, como si
    estuvieran en la misma carpeta (el límite de vídeos cuenta sobre el conjunto).

    - `opciones`: `Opciones` (por defecto, las de la CLI sin parámetros).
    - `eventos`: `Eventos` que recibe el progreso, las líneas informativas y los resultados.
    - `cancelado`: función sin argumentos; si devuelve True, se para en el siguiente punto de
      control: entre vídeos, durante la pausa, entre consultas a los proveedores y antes de
      escribir. Tras cancelar no se escribe nada más; lo ya guardado se queda guardado.
    - `credenciales`: configuración de proveedores ({'opensubtitles': {...}}); None = leer
      ~/.subtitulos-esp/credenciales.json.

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
            detalle(f'  [dry-run] guardaría {destino.name}')
        else:
            guardar(texto, destino)

    if not region.is_configured:
        try:
            region.configure('dogpile.cache.memory')
        except RegionAlreadyConfigured:     # otra búsqueda la ha configurado a la vez
            pass
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

    try:
        _recorrer(videos, opciones, eventos, cancelado, comprobar, escribir, anotar, detalle,
                  max_descargas, providers, configs)
    except _Cancelado:
        pass
    return resultados


def _recorrer(videos, opciones, eventos, cancelado, comprobar, escribir, anotar, detalle, max_descargas,
              providers, configs):
    buscados = 0  # vídeos que ya han buscado en internet en esta ejecución
    with ProviderPool(providers=providers, provider_configs=configs) as pool:
        for indice, path in enumerate(videos, 1):
            if cancelado():
                break
            eventos.video(indice, len(videos), path)
            destino = path.with_suffix('.srt')
            # Formato antiguo: <video>.es.srt (o .en.srt si no había español) -> <video>.srt
            previo = destino if destino.exists() else next(
                (p for p in (path.with_suffix('.es.srt'), path.with_suffix('.en.srt')) if p.exists()), None)
            actual = idioma_srt(previo.read_text(encoding='utf-8', errors='replace')) if previo else None
            nota = '-'
            if previo and previo != destino:
                nota = f'renombrado desde {previo.suffixes[-2]}.srt'
                if opciones.dry_run:
                    detalle(f'  [dry-run] renombraría {previo.name} -> {destino.name}')
                else:
                    previo.rename(destino)

            if actual == 'castellano' and not opciones.force:
                anotar(path, 'ya tenía castellano', nota, YA_CASTELLANO)
                continue

            detalle(f'\n== {path.name}')
            if actual:
                detalle(f'  ya tiene {destino.name} en {actual}')

            def aplicar(tipo, texto, estado, fuente):
                """Guarda como <video>.srt salvo que el que ya hay sea de un tipo mejor."""
                if RANGO[tipo] > RANGO[actual] or (opciones.force and RANGO[tipo] == RANGO[actual]):
                    escribir(texto, destino)
                    anotar(path, estado, fuente, tipo)
                else:
                    anotar(path, f'{ETIQUETA[actual]} (ya tenía .srt)', nota, SIN_CAMBIOS)

            emb = incrustado(path, opciones.ingles, detalle)
            comprobar()
            destino_en = path.with_suffix('.en.srt')
            if emb['ingles'] and (opciones.force or not destino_en.exists()):
                escribir(emb['ingles'][0], destino_en)
            if emb['castellano']:
                aplicar('castellano', emb['castellano'][0], 'CASTELLANO (incrustado)', emb['castellano'][1][:30])
                continue

            # A partir de aquí se busca en internet: límite por ejecución y pausa entre vídeos.
            if opciones.max_videos and buscados >= opciones.max_videos:
                detalle(f'  límite de {opciones.max_videos} vídeos con búsqueda en internet alcanzado: '
                        f'queda para otra ejecución')
                anotar(path, 'PENDIENTE (límite)', f'máx. {opciones.max_videos} por ejecución', PENDIENTE)
                continue
            if buscados and _esperar(PAUSA, cancelado):
                break
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

            candidatos = pool.list_subtitles(video, {Language('spa')})
            comprobar()
            if max_descargas and len(candidatos) > max_descargas:
                detalle(f'  {len(candidatos)} candidatos en español: se descargan los {max_descargas} '
                        f'mejores, alternando proveedores')
            castellanos, latinos = [], []
            vistos = set()
            for sub in mejores_candidatos(candidatos, video, max_descargas):
                comprobar()
                if not pool.download_subtitle(sub) or not sub.content:
                    continue
                texto = sub.text
                if len(texto) > MAX_SRT:
                    detalle(f'  {sub.provider_name:13} id={visible(sub.id)} descartado: tamaño anormal')
                    continue
                if texto in vistos:
                    continue
                vistos.add(texto)
                es, la, ok = dialecto(texto)
                ep_ok = episodio_correcto(sub, video)
                dur_ok = duracion_ok(texto, video)
                score = compute_score(sub, video)
                sinc = sincronia(sub, video)
                detalle(f'  {sub.provider_name:13} id={visible(sub.id)} score={score} sincronía={sinc} '
                        f'españa={es} latino={la} episodio_ok={ep_ok} duración_ok={dur_ok}')
                if not (ep_ok and dur_ok):
                    continue
                (castellanos if ok else latinos).append((sinc, es, score, sub, texto))

            if castellanos:
                # 1) sincronía (mismo archivo > mismo release), 2) más señales de castellano,
                # 3) puntuación de subliminal. Antes mandaba la puntuación y un +2 por coincidir
                # en resolución y códec ganaba a un candidato con 5 veces más señales.
                sinc, es, score, sub, texto = max(castellanos, key=lambda c: (c[0], c[1], c[2]))
                aplicar('castellano', texto, 'CASTELLANO', f'{sub.provider_name} {sub.id}')
            elif emb['latino'] and not opciones.solo_castellano:
                # La pista incrustada va sincronizada exactamente con el vídeo: mejor que una web.
                aplicar('latino', emb['latino'][0], 'LATINO (incrustado)', emb['latino'][1][:30])
            elif latinos and not opciones.solo_castellano:
                sinc, es, score, sub, texto = max(latinos, key=lambda c: (c[0], c[2]))
                aplicar('latino', texto, 'LATINO', f'{sub.provider_name} {sub.id}')
            elif RANGO[actual] >= RANGO['ingles'] and (not opciones.force or RANGO[actual] > RANGO['ingles']):
                # Ya hay latino o inglés y no se ha encontrado nada mejor: se deja como está.
                anotar(path, f'{ETIQUETA[actual]} (ya tenía .srt)', nota, SIN_CAMBIOS)
            elif opciones.sin_ingles:
                anotar(path, 'NO ENCONTRADO', f'{len(latinos)} latinos descartados', NO_ENCONTRADO)
            else:
                # Ni castellano ni latino: subtítulos en inglés como último recurso.
                texto, pista = (emb['ingles'] or (None, ''))
                if not texto and not emb['lento']:      # si leer el vídeo es lento, no se reintenta
                    texto, pista = ingles_incrustado(path, detalle)
                if texto:
                    aplicar('ingles', texto, 'INGLÉS (incrustado)', pista[:30])
                    continue
                texto, sub = ingles_proveedores(pool, video, max_descargas, detalle, comprobar)
                if texto:
                    aplicar('ingles', texto, 'INGLÉS', f'{sub.provider_name} {sub.id}')
                else:
                    anotar(path, 'NO ENCONTRADO', 'ni español ni inglés', NO_ENCONTRADO)
