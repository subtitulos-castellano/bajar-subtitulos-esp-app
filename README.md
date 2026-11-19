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

El remoto `upstream` apunta al repositorio de la skill (solo lectura) para traer sus mejoras:

```bash
git fetch upstream
git merge upstream/main
```

## Fases

0. Repositorios ✅
1. Separar el núcleo (`procesar()`) de la salida por pantalla, sin cambiar el comportamiento de la CLI
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

## Licencia

MIT (ver `LICENSE`). Qt/PySide6 se distribuye bajo LGPL v3.
