# Política de seguridad

## Versiones con soporte

Solo se corrige la última versión publicada en *Releases*. Si usas una anterior, actualiza antes
de informar: el instalador nuevo se instala encima del anterior.

## Cómo avisar de un problema de seguridad

Avisa **en privado**, no en una issue:

- Si tienes acceso al repositorio, crea un aviso de seguridad borrador en la pestaña
  **Security › Advisories › New draft security advisory**.
- Si no, escribe directamente a quien mantiene el proyecto.

Explica qué ocurre, con qué versión y cómo reproducirlo. Si hace falta un archivo de ejemplo (un
subtítulo o un vídeo manipulado), descríbelo o genéralo con un script pequeño; no adjuntes
material con derechos de autor.

## Qué entra en el alcance

- La app (`app/`) y el núcleo (`subtitulos/`): lectura de pistas incrustadas en MKV y MP4,
  descarga, validación y guardado de subtítulos, configuración y credenciales.
- El ejecutable, el instalador y la versión portable que se publican en *Releases*.

Fuera del alcance: fallos de los proveedores de subtítulos, de subliminal y demás dependencias
(avisa a sus autores) y de los reproductores de vídeo.

## Medidas que ya aplica

- Todo lo que llega de fuera (subtítulos, nombres de pistas, identificadores de los proveedores)
  se trata como datos no fiables:
  - Los subtítulos se guardan sin caracteres de control ni de dirección del texto.
  - Lo que se muestra en pantalla va siempre en una sola línea.
- La lectura de vídeos tiene límites de tamaño y de número de elementos, para que un archivo
  corrupto o manipulado no cuelgue el programa ni agote la memoria. Hay pruebas automáticas para
  esto en `tests/test_seguridad.py`.
- Los subtítulos de tamaño anormal se descartan.
- La contraseña de OpenSubtitles se guarda en el Administrador de credenciales de Windows, nunca
  en un archivo.
- Antes de sustituir un subtítulo, se guarda una copia en `%USERPROFILE%\.subtitulos-esp\backup`.
- Los límites de búsqueda por tanda evitan saturar a los proveedores.
