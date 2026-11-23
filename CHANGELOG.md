# Cambios

## 1.4.0

- [Windows] **Avisos de actualización solo cuando hay algo para Windows.** Es el primer paso hacia
  la versión para Linux: las dos tendrán siempre el mismo número de versión, y cada una solo avisará
  de las versiones que traigan cambios para su sistema. Si se salta alguna, enseña también sus
  novedades.
- [Windows] Por dentro, el código está reorganizado para la versión de Linux. En Windows todo
  funciona igual que antes.

## 1.3.0

- **opensubtitles.com**, como último recurso: con cuenta, se le piden subtítulos solo si los demás
  proveedores no han encontrado castellano (o, al final, inglés), porque sus cuentas solo permiten unas
  pocas descargas al día.
  - Para en cuanto encuentra un castellano válido, para gastar el menor cupo posible.
  - *Detalles* dice cuántas descargas quedan hoy. Si se agota el cupo (o no acepta la cuenta), lo dice
    y la búsqueda sigue con los demás proveedores.
- *Configuración › Cuentas de OpenSubtitles*: las cuentas de opensubtitles.org y de opensubtitles.com,
  cada una con su usuario, contraseña, *Guardar* y *Probar conexión*. *Usar la cuenta de la skill*
  importa cada una de su `credenciales.json` (`"opensubtitlescom"` para la de .com).

## 1.2.1

- **Novedades de una actualización**: si son largas, se leen enteras con una barra de desplazamiento
  (o con la rueda del ratón). Ya no estiran el aviso ni dejan sin sitio al resto de la ventana.

## 1.2.0

- **La app, también en inglés** (*English*):
  - el instalador pregunta el idioma la primera vez (propone el de Windows); al actualizar se queda el
    de antes;
  - en *Configuración › Idioma · Language* se cambia en cualquier momento (en la versión portable, es
    la única forma). La app se cierra y se vuelve a abrir sola en el idioma elegido;
  - cambia todo: la interfaz, los avisos, las novedades de las actualizaciones, el registro de
    *Detalles* y el menú contextual del Explorador.
- La línea de comandos y la skill siguen en castellano.

## 1.1.1

- **Menú contextual con la versión instalada y la portable**: ya no se queda en el Explorador tras
  desinstalar.
  - El desinstalador quita el menú aunque apunte a una versión portable.
  - El instalador (también al actualizar) se queda con el menú aunque lo tuviera una portable, salvo
    que se haya desactivado en Configuración.
  - La versión portable solo añade el menú si se activa en su Configuración, y avisa de desactivarlo
    antes de borrar su carpeta.
  - Al abrir la app, si el menú apunta a un programa que ya no existe y no está activado, se quita.

## 1.1.0

- **Menú contextual del Explorador**:
  - clic derecho en una carpeta (o en el fondo de una carpeta, o en una unidad): *Bajar subtítulos
    aquí*, con *Solo esta carpeta* o *Esta carpeta y sus subcarpetas*;
  - clic derecho en uno o varios vídeos: *Bajar subtítulos*. Varios vídeos seleccionados son una
    sola búsqueda. No aparece en los `.ts` (también son archivos de TypeScript), aunque la app sí
    los busca dentro de las carpetas;
  - en Windows 11 aparece dentro de *Mostrar más opciones*.
- *Configuración › Menú contextual del Explorador*:
  - mostrarlo u ocultarlo (el instalador lo añade; en la versión portable se activa aquí);
  - al usarlo, **mostrar la ventana** (como al arrastrar) o buscar **en segundo plano**: sin ventana,
    con un icono junto al reloj mientras busca (para ver el progreso o cancelar) y un aviso con el
    resumen al terminar.
- Solo hay una app abierta a la vez: lo que llega del menú (o al abrirla otra vez) va a la que ya
  está abierta, a su cola.
- Se pueden soltar vídeos o carpetas sobre el icono del programa para abrirlo y buscarlos.
- Al desinstalar, el menú contextual se quita.
- *Configuración › Al cerrar la ventana, seguir junto al reloj*: cerrar la ventana la oculta y la app
  sigue con un icono junto al reloj (un clic la abre; *Salir* la cierra). Si estaba buscando, sigue y
  avisa al terminar.
- **Discos lentos**: si extraer la pista de subtítulos de un vídeo fuera a tardar más de 15 segundos
  (vídeos grandes en un disco USB, un NAS o una carpeta de red), no se extrae y se busca en internet.
  En *Detalles* se indica, con lo que habría tardado.

## 1.0.2

- **Icono nuevo**: una pantalla de vídeo con play y subtítulos, y una flecha que entra en una bandeja
  (descargar). Se ve nítido a cualquier tamaño, también con el escalado de Windows al 125 % y 250 %.
- El logo de la barra lateral se dibuja a la resolución de la pantalla.

## 1.0.1

- **Actualizaciones automáticas**:
  - al abrir la app, como mucho una vez al día, mira en GitHub si hay una versión nueva;
  - si la hay, avisa arriba de la ventana con sus novedades, y *Actualizar* la descarga, comprueba
    que su SHA-256 coincide con el publicado en GitHub, la instala en silencio y vuelve a abrir la app;
  - nunca se instala nada sin que lo pidas, ni durante una búsqueda;
  - la versión portable solo avisa y abre la página de descarga.
- *Configuración › Actualizaciones*: activar o desactivar la comprobación automática y *Buscar ahora*.
- Las Releases incluyen `SHA256SUMS.txt` y una atestación de procedencia de GitHub de cada archivo.
- El repositorio es público.

Quien tenga la 1.0.0 tiene que instalar esta versión a mano una vez: la 1.0.0 aún no sabía actualizarse.

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
