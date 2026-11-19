# Cambios

## 1.0.0

Primera versión de **Bajar Subtítulos ESP** como aplicación de Windows 10 y 11.

- Arrastra uno o varios vídeos, o carpetas, a la ventana: se buscan subtítulos en castellano de
  España sin preguntas, con las mismas reglas que la skill `bajar-subtitulos-esp`:
  - primero las pistas incrustadas del vídeo;
  - después OpenSubtitles, Addic7ed, Gestdown y Subtitulamos;
  - castellano > latino > inglés;
  - nunca se sustituye un subtítulo por otro peor;
  - límites para no saturar a los proveedores.
- Mientras busca:
  - todos los vídeos en la tabla desde el principio, con su estado (En espera, Buscando…, resultado);
  - registro de *Detalles* abierto;
  - cancelación inmediata (tras cancelar no se escribe nada más);
  - cola para lo que se arrastra mientras busca.
- Resumen:
  - tarjetas de colores por estado, que filtran la tabla al pulsarlas;
  - barra de proporciones;
  - copiar el resumen;
  - abrir la carpeta;
  - procesar los pendientes.
- Configuración guardada al momento:
  - las opciones de la línea de comandos como interruptores y límites;
  - cuenta de OpenSubtitles (contraseña en el Administrador de credenciales de Windows; importable
    desde la skill) y prueba de conexión;
  - tema claro, oscuro o el de Windows;
  - tamaño del texto como el de Windows o personalizado.
- Recuerda el tamaño y la posición de la ventana.
- Instalador por usuario (sin permisos de administrador) y versión portable.
- Compilación y pruebas automáticas en Windows Server 2022 (base de Windows 10) y 2025 (base de
  Windows 11): instalación, autoprueba del programa instalado y desinstalación.

## 0.x (desarrollo, 19/11/2026)

- 0.5: ejecutable, versión portable, instalador y GitHub Actions.
- 0.4: cambios tras las primeras pruebas:
  - posición de la ventana;
  - tamaño del texto;
  - cancelar al momento;
  - menú Inicio / Buscando… / Configuración;
  - tabla con todos los vídeos;
  - varios vídeos soltados a la vez como una sola búsqueda.
- 0.3: búsqueda real, configuración y credenciales.
- 0.2: prototipo de la ventana con Qt (resultados de demostración).
- 0.1: núcleo separado de la línea de comandos, con la misma salida que la skill.
