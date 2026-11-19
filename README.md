# Bajar Subtítulos ESP

Aplicación de escritorio para **Windows 10 y 11** que descarga subtítulos en **castellano
(español de España)** para series y películas. Basta con arrastrar un vídeo o una carpeta a
la ventana.

> **Estado:** en desarrollo. Ver el plan del proyecto en las fases descritas abajo.

## Origen

Parte de la skill [`bajar-subtitulos-esp`](https://github.com/subtitulos-castellano/bajar-subtitulos-esp)
y conserva su historial. La app hace exactamente lo mismo que la skill:

- Mira primero dentro del vídeo, en las pistas incrustadas de MKV y MP4.
- Después busca en los proveedores de subtítulos.
- Prefiere castellano a latino y latino a inglés.
- Respeta los límites para no saturar a los proveedores.
- Hace copias de seguridad de los `.srt` que sustituye.

A todo eso añade una interfaz gráfica hecha con Qt (PySide6).

El remoto `upstream` apunta al repositorio de la skill (solo lectura). En la app, el antiguo
`bajar_subs.py` se ha repartido en el paquete `subtitulos/`, así que las mejoras de la skill
se traen a mano:

```bash
git fetch upstream
git diff <último commit de la skill revisado> upstream/main -- bajar_subs.py
```

Después se aplican en el módulo correspondiente:

- `subtitulos/pistas.py`: subtítulos incrustados en MKV/MP4.
- `subtitulos/texto.py`: limpieza de textos y detección de idioma y dialecto.
- `subtitulos/nucleo.py`: proveedores y `procesar()`.
- `bajar_subs.py`: parámetros de la CLI.

Último commit de la skill incorporado: `3aa1f5e`.

## Fases

0. Repositorios ✅
1. Separar el núcleo (`procesar()`) de la salida por pantalla, sin cambiar el comportamiento de la CLI ✅
2. Prototipo de la ventana: arrastrar y soltar, y estilo claro/oscuro
3. Interfaz completa: Inicio, progreso, resumen con colores y Configuración
4. Empaquetado: `.exe`, instalador y versión portable
5. Pruebas en Windows 10 y 11
6. Documentación y versión 1.0

## Línea de comandos

Mientras tanto, el script sigue funcionando como en la skill:

```bash
python -I bajar_subs.py "<carpeta o vídeo>" [--dry-run] [--force] [--solo-castellano]
                       [--sin-ingles] [--ingles] [--max-videos N] [--max-descargas N]
```

Requiere `pip install -r requirements.txt`.

## Estructura

```
subtitulos/
  opciones.py   Opciones de una ejecución (equivalen a los parámetros de la CLI)
  texto.py      limpieza de textos de terceros, idioma y dialecto
  pistas.py     subtítulos incrustados en MKV y MP4 (sin ffmpeg)
  nucleo.py     proveedores y procesar(ruta, opciones, eventos, cancelado)
bajar_subs.py   CLI
tests/
```

`opciones.py`, `texto.py` y `pistas.py` solo usan la biblioteca estándar. `nucleo.py` importa
subliminal, que tarda en cargar.

## Pruebas

```bash
python -m unittest discover -s tests
```

`tests/test_nucleo.py` simula los proveedores, así que no necesita internet. Comprueba que la CLI
produce exactamente la misma salida y los mismos archivos que el script original de la skill
(`tests/esperado/`).

## Licencia

MIT (ver `LICENSE`). Qt/PySide6 se distribuye bajo LGPL v3.
