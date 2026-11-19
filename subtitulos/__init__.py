"""Núcleo de Bajar Subtítulos ESP, compartido por la línea de comandos y la app.

- `opciones`: preferencias de una ejecución (sin dependencias).
- `texto`: limpieza de textos de terceros y detección de idioma y dialecto (sin dependencias).
- `pistas`: subtítulos incrustados en MKV y MP4 (sin dependencias).
- `nucleo`: búsqueda en los proveedores y `procesar()`. Importa subliminal, que tarda en
  cargar: la app lo importa en segundo plano.
"""
