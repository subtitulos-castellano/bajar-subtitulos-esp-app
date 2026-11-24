"""Traducción al inglés de los textos de la app y del núcleo (ver idioma.py).

Clave: el texto en castellano, exactamente como está en el código. Valor: el mismo texto en inglés, con
los mismos `{campos}` (las pruebas lo comprueban, y también que no sobre ni falte ninguno).

Vocabulario: castellano = «Spanish from Spain»; latino = «Latin American»
(«Latin American Spanish»); proveedores = «providers»; tanda = «batch»; incrustado = «embedded».
"""
TEXTOS = {
    # ---------- Núcleo: resumen y Detalles (subtitulos/nucleo.py, pistas.py) ----------
    'CASTELLANO': 'SPANISH FROM SPAIN',
    'CASTELLANO (incrustado)': 'SPANISH FROM SPAIN (embedded)',
    'LATINO': 'LATIN AMERICAN',
    'LATINO (incrustado)': 'LATIN AMERICAN (embedded)',
    'INGLÉS': 'ENGLISH',
    'INGLÉS (incrustado)': 'ENGLISH (embedded)',
    'ya tenía castellano': 'already had Spanish from Spain',
    '{tipo} (ya tenía .srt)': '{tipo} (already had .srt)',
    'PENDIENTE (límite)': 'PENDING (limit)',
    'NO ENCONTRADO': 'NOT FOUND',
    'máx. {n} por ejecución': 'max. {n} per run',
    'ni español ni inglés': 'no Spanish or English',
    '{n} latinos descartados': '{n} Latin American discarded',
    'renombrado desde {extension}.srt': 'renamed from {extension}.srt',
    'pista {n}': 'track {n}',
    'castellano': 'Spanish from Spain',
    'latino': 'Latin American',
    'ingles': 'English',
    'otro': 'another language',
    '  ya tiene {nombre} en {idioma}': '  already has {nombre} in {idioma}',
    '  [dry-run] guardaría {nombre}': '  [dry-run] would save {nombre}',
    '  [dry-run] renombraría {previo} -> {destino}': '  [dry-run] would rename {previo} -> {destino}',
    '  límite de {n} vídeos con búsqueda en internet alcanzado: queda para otra ejecución':
        '  limit of {n} videos searched online reached: left for another run',
    '  {n} candidatos en español: se descargan los {maximo} mejores, alternando proveedores':
        '  {n} Spanish candidates: downloading the best {maximo}, alternating providers',
    '  {proveedor:13} id={id} descartado: tamaño anormal': '  {proveedor:13} id={id} discarded: abnormal size',
    '  {proveedor:13} id={id} score={score} sincronía={sinc} españa={es} latino={la} '
    'episodio_ok={ep_ok} duración_ok={dur_ok}':
        '  {proveedor:13} id={id} score={score} sync={sinc} spain={es} latam={la} '
        'episode_ok={ep_ok} duration_ok={dur_ok}',
    '  [inglés] {proveedor:13} id={id} descartado: tamaño anormal':
        '  [english] {proveedor:13} id={id} discarded: abnormal size',
    '  [inglés] {proveedor:13} id={id} score={score} episodio_ok={ep_ok} duración_ok={dur_ok}':
        '  [english] {proveedor:13} id={id} score={score} episode_ok={ep_ok} duration_ok={dur_ok}',
    '  {n} pistas de subtítulos incrustadas': '  {n} embedded subtitle tracks',
    '  pista incrustada {n} [{idioma}] {nombre}: españa={es} latino={la}':
        '  embedded track {n} [{idioma}] {nombre}: spain={es} latam={la}',
    'españa={es} latino={la}': 'spain={es} latam={la}',
    '  (no se pudieron leer las pistas incrustadas: {error})': '  (could not read the embedded tracks: {error})',
    '  (no se pudieron extraer las pistas incrustadas: {error})': '  (could not extract the embedded tracks: {error})',
    '  no se han extraído {que} del propio vídeo porque leerlo era muy lento '
    '(tardaría {tiempo}; el límite es {limite} s)':
        '  {que} were not extracted from the video itself because reading it was too slow '
        '(it would take {tiempo}; the limit is {limite} s)',
    'los subtítulos incrustados': 'the embedded subtitles',
    'los subtítulos en inglés': 'the English subtitles',
    'más de {n} s': 'more than {n} s',
    'unos {n} s': 'about {n} s',
    'unos {n} min': 'about {n} min',
    'número de pista no válido en un bloque MKV': 'invalid track number in an MKV block',
    'tamaño de elemento no válido': 'invalid element size',
    'el archivo se acaba antes de tiempo': 'the file ends too early',
    'pista sin tamaño': 'track without size',
    'bloque sin tamaño': 'block without size',
    'índice MP4 (moov) demasiado grande': 'MP4 index (moov) too large',
    'tabla de muestras MP4 demasiado grande': 'MP4 sample table too large',
    'muestra de subtítulo MP4 demasiado grande': 'MP4 subtitle sample too large',
    'aviso': 'warning',
    '  opensubtitles.com (último recurso): {n} candidatos en español':
        '  opensubtitles.com (last resort): {n} Spanish candidates',
    '  opensubtitles.com: quedan {n} descargas por hoy': '  opensubtitles.com: {n} downloads left today',
    '  opensubtitles.com no responde o no acepta la cuenta: no se le pide nada más en esta búsqueda':
        '  opensubtitles.com does not respond or does not accept the account: nothing more is asked of it in '
        'this search',
    '  opensubtitles.com no deja descargar (cupo de hoy agotado o cuenta no válida): no se le pide nada más en '
    'esta búsqueda':
        '  opensubtitles.com does not allow downloading (today’s quota used up or invalid account): nothing more '
        'is asked of it in this search',

    # ---------- Ventana y barra lateral ----------
    'Castellano de España': 'Spanish from Spain',
    'Inicio': 'Home',
    'Pantalla para arrastrar vídeos o carpetas': 'Screen to drag videos or folders onto',
    'Buscando…': 'Searching…',
    'La búsqueda en marcha o la última que se hizo': 'The search in progress or the last one',
    'Configuración': 'Settings',
    'Preferencias de la búsqueda y de la app': 'Search and app preferences',
    'Versión {version}': 'Version {version}',
    'Suelta para añadir a la cola': 'Drop to add to the queue',
    'Se procesará en cuanto termine lo que está en marcha.': 'It will be processed as soon as the current search ends.',
    'Suelta para buscar subtítulos': 'Drop to search for subtitles',
    '{n} elementos': '{n} items',

    # ---------- Inicio, progreso y resumen ----------
    'Bajar subtítulos': 'Get subtitles',
    'Subtítulos en castellano de España para tus series y películas.':
        'Subtitles in Spanish from Spain for your series and movies.',
    'Modo simulación activado: se mostrará qué se haría, pero no se escribirá ningún archivo.':
        'Simulation mode on: it will show what would be done, but no file will be written.',
    'Arrastra aquí un vídeo o una carpeta': 'Drag a video or a folder here',
    'Elige un vídeo o una carpeta': 'Choose a video or a folder',
    'Desde WSL no se puede arrastrar desde Windows. Se buscan los subtítulos nada más elegirlos, sin '
    'preguntas. Las carpetas se revisan con todas sus subcarpetas.':
        'In WSL you cannot drag from Windows. Subtitles are searched for as soon as you choose them, no '
        'questions asked. Folders are checked with all their subfolders.',
    'Se buscan los subtítulos nada más soltarlo, sin preguntas. Las carpetas se revisan con todas sus subcarpetas.':
        'Subtitles are searched for as soon as you drop it, no questions asked. Folders are checked with all '
        'their subfolders.',
    'Elegir carpeta…': 'Choose folder…',
    'Elegir vídeo…': 'Choose video…',
    'Elegir carpeta con vídeos': 'Choose a folder with videos',
    'Elegir vídeos': 'Choose videos',
    'Vídeos': 'Videos',
    'Cambiar preferencias': 'Change preferences',
    'Buscando subtítulos…': 'Searching for subtitles…',
    'Cancelar': 'Cancel',
    'Cancelando…': 'Cancelling…',
    'Prototipo: resultados de demostración. Todavía no se busca ni se descarga nada.':
        'Prototype: demo results. Nothing is searched for or downloaded yet.',
    'Buscando vídeos…': 'Looking for videos…',
    '{n} elementos de {carpeta}': '{n} items from {carpeta}',
    '(sin subcarpetas)': '(without subfolders)',
    'No se ha encontrado ningún vídeo.': 'No videos were found.',
    '{n} vídeos encontrados': '{n} videos found',
    'Vídeo {indice} de {total}': 'Video {indice} of {total}',
    'ERROR: {mensaje}': 'ERROR: {mensaje}',
    'En cola: {n}': 'Queued: {n}',
    'Listo': 'Done',
    'Listo, con avisos': 'Done, with warnings',
    'Cancelado': 'Cancelled',
    'No hay vídeos': 'No videos',
    'Se ha detenido por un error': 'Stopped because of an error',
    'Copiar resumen': 'Copy summary',
    'Copiado': 'Copied',
    'Abrir carpeta': 'Open folder',
    'Procesar pendientes': 'Process pending',
    'Vuelve a revisar la misma carpeta: los vídeos ya resueltos se saltan enseguida y se buscan los pendientes.':
        'Checks the same folder again: videos already done are skipped right away and the pending ones are '
        'searched for.',
    'Simulación: no se ha escrito ningún archivo.': 'Simulation: no file has been written.',
    'Pulsa Inicio o arrastra otro vídeo o carpeta para seguir.': 'Click Home or drag another video or folder to go on.',
    '{n} de {total} vídeos revisados': '{n} of {total} videos checked',
    '1 vídeo revisado': '1 video checked',
    '{n} vídeos revisados': '{n} videos checked',
    '{videos} en {tiempo}': '{videos} in {tiempo}',
    '{error}. Lo que ya estaba hecho se ha guardado; puedes volver a intentarlo arrastrando la carpeta otra vez.':
        '{error}. What was already done has been saved; you can try again by dragging the folder again.',
    '==== RESUMEN ====': '==== SUMMARY ====',
    'Detalles': 'Details',

    # ---------- Tabla y estados ----------
    'Estado': 'Status',
    'Vídeo': 'Video',
    'Origen': 'Source',
    'No revisado': 'Not checked',
    'Pulsa para ver solo estos vídeos.': 'Click to see only these videos.',
    'Castellano': 'Spanish from Spain',
    'Subtítulo en castellano guardado ahora': 'Subtitle in Spanish from Spain saved now',
    'Ya lo tenían': 'Already had it',
    'Ya tenían subtítulo en castellano': 'They already had a subtitle in Spanish from Spain',
    'Latino': 'Latin American',
    'Solo había latino: se ha guardado latino': 'There was only Latin American Spanish: it has been saved',
    'Inglés': 'English',
    'No había nada en español: se ha guardado inglés': 'There was nothing in Spanish: English has been saved',
    'Sin cambios': 'No changes',
    'Ya tenían latino o inglés y no se ha encontrado nada mejor':
        'They already had Latin American Spanish or English and nothing better was found',
    'Pendientes': 'Pending',
    'Superan el límite de vídeos por tanda: se harán la próxima vez':
        'Over the limit of videos per batch: they will be done next time',
    'Sin subtítulos': 'No subtitles',
    'No se ha encontrado ningún subtítulo': 'No subtitle was found',
    'No revisados': 'Not checked',
    'No se llegaron a revisar porque se canceló la búsqueda': 'They were not checked because the search was cancelled',
    'En espera': 'Waiting',
    'Todavía no se ha revisado': 'Not checked yet',
    'Se está revisando ahora': 'Being checked now',

    # ---------- Icono junto al reloj ----------
    'ya lo tenían': 'already had it',
    'inglés': 'English',
    'sin cambios': 'no changes',
    'pendientes': 'pending',
    'sin subtítulos': 'no subtitles',
    'no revisados': 'not checked',
    'Subtítulos listos': 'Subtitles ready',
    'Subtítulos listos, con avisos': 'Subtitles ready, with warnings',
    '1 vídeo: {lista}.': '1 video: {lista}.',
    '{n} vídeos: {lista}.': '{n} videos: {lista}.',
    '{error}. Lo que ya estaba hecho se ha guardado.': '{error}. What was already done has been saved.',
    'Búsqueda cancelada': 'Search cancelled',
    '1 vídeo revisado antes de cancelar.': '1 video checked before cancelling.',
    '{n} vídeos revisados antes de cancelar.': '{n} videos checked before cancelling.',
    'Los pendientes superan el límite por tanda: pulsa aquí y luego Procesar pendientes.':
        'The pending ones are over the limit per batch: click here and then Process pending.',
    'Abrir Bajar Subtítulos ESP': 'Open Bajar Subtítulos ESP',
    'Cancelar la búsqueda': 'Cancel the search',
    'Salir': 'Exit',
    'Ver progreso': 'See progress',
    'Ver el resumen': 'See the summary',
    'Buscando subtítulos: vídeo {indice} de {total}': 'Searching for subtitles: video {indice} of {total}',

    # ---------- Configuración ----------
    'Los cambios se guardan al momento y se usan en la siguiente búsqueda.':
        'Changes are saved right away and used in the next search.',
    'Idioma de la app': 'App language',
    'Al cambiarlo, la app se cierra y se vuelve a abrir sola en el idioma elegido, en esta misma pantalla.':
        'When you change it, the app closes and opens again by itself in the chosen language, on this same '
        'screen.',
    'No se ha podido volver a abrir la app: el idioma nuevo se usará la próxima vez que la abras.':
        'The app could not be reopened: the new language will be used the next time you open it.',
    'Qué subtítulos guardar': 'Which subtitles to save',
    'Siempre se prefiere castellano de España. Nunca se sustituye un subtítulo por otro peor.':
        'Spanish from Spain is always preferred. A subtitle is never replaced with a worse one.',
    'Si no hay castellano, guardar latino': 'If there is no Spanish from Spain, save Latin American',
    'El resumen lo marca como Latino para que sepas que no es castellano.':
        'The summary marks it as Latin American so you know it is not Spanish from Spain.',
    'Si no hay nada en español, guardar inglés': 'If there is nothing in Spanish, save English',
    'Primero la pista inglesa del propio vídeo (mejor si es SDH); si no hay, de los proveedores.':
        'First the English track of the video itself (SDH preferred); if there is none, from the providers.',
    'Extraer también la pista inglesa incrustada': 'Also extract the embedded English track',
    'Se guarda aparte como <vídeo>.en.srt, además del subtítulo principal.':
        'It is saved separately as <video>.en.srt, besides the main subtitle.',
    'Cómo trabajar': 'How to work',
    'Rehacer aunque ya haya castellano': 'Redo even if there is Spanish from Spain already',
    'Vuelve a buscar en todos los vídeos. El subtítulo anterior se copia a la carpeta de copias de seguridad.':
        'Searches again for every video. The previous subtitle is copied to the backup folder.',
    'Modo simulación': 'Simulation mode',
    'Muestra qué se haría, sin escribir ni renombrar ningún archivo.':
        'Shows what would be done, without writing or renaming any file.',
    'Límites para no saturar a los proveedores': 'Limits so as not to overload the providers',
    'Los proveedores de subtítulos son servicios gratuitos. Sube estos límites solo si lo necesitas: los vídeos '
    'que pasen del límite quedan como Pendientes para la siguiente vez.':
        'Subtitle providers are free services. Raise these limits only if you need to: videos over the limit are '
        'left as Pending for next time.',
    'Sin límite': 'No limit',
    'Vídeos que buscan en internet en cada tanda': 'Videos searched online in each batch',
    'Por defecto, {n}. Los que ya tienen castellano o lo traen dentro no cuentan.':
        'Default: {n}. Those that already have Spanish from Spain, or have it embedded, do not count.',
    'Candidatos que se descargan por vídeo': 'Candidates downloaded per video',
    'Por defecto, {n}. Se eligen los mejores, alternando proveedores.':
        'Default: {n}. The best ones are chosen, alternating providers.',
    'Ventana, apariencia y copias de seguridad': 'Window, appearance and backups',
    'Al cerrar la ventana, seguir junto al reloj': 'When closing the window, keep running next to the clock',
    'La app no se cierra: queda un icono junto al reloj para volver a abrirla. Si estaba buscando, sigue y avisa '
    'al terminar. Para cerrarla del todo: clic derecho en el icono › Salir.':
        'The app does not close: an icon stays next to the clock to open it again. If it was searching, it goes '
        'on and lets you know when it ends. To close it completely: right-click the icon › Exit.',
    'Tema': 'Theme',
    'Sistema': 'System',
    'Claro': 'Light',
    'Oscuro': 'Dark',
    'Claro, oscuro o el mismo que Windows.': 'Light, dark or the same as Windows.',
    'Claro, oscuro o el mismo que el sistema.': 'Light, dark or the same as the system.',
    '100 % es el tamaño normal, el mismo que en el resto de programas. Súbelo para agrandar el texto o bájalo '
    'para reducirlo.':
        '100 % is the normal size, the same as in other programs. Raise it to make the text bigger or lower it to '
        'make it smaller.',
    'Opcionales, pero dan más resultados. opensubtitles.org y opensubtitles.com son cuentas distintas. Las '
    'contraseñas se guardan en el llavero del sistema (KWallet o GNOME Keyring), nunca en un archivo.':
        'Optional, but they give more results. opensubtitles.org and opensubtitles.com are separate accounts. '
        'Passwords are stored in the system keyring (KWallet or GNOME Keyring), never in a file.',
    'Este sistema no tiene llavero: para usar las cuentas, instala uno (por ejemplo, gnome-keyring) y vuelve a '
    'abrir la app.':
        'This system has no keyring: to use the accounts, install one (for example, gnome-keyring) and open the '
        'app again.',
    'No se pudo guardar la contraseña en el llavero del sistema.': 'The password could not be saved in the system keyring.',
    'Esperando al llavero del sistema. Si te pide su contraseña, desbloquéalo.':
        'Waiting for the system keyring. If it asks for its password, unlock it.',
    'Tamaño del texto': 'Text size',
    'Como Windows': 'Like Windows',
    'Como Windows ({n} %)': 'Like Windows ({n} %)',
    'Personalizado': 'Custom',
    'Como Windows: el de Configuración de Windows › Accesibilidad › Tamaño del texto. Si lo cambias allí, la app '
    'se ajusta al volver a ella.':
        'Like Windows: the one in Windows Settings › Accessibility › Text size. If you change it there, the app '
        'adjusts when you come back to it.',
    'Copias de seguridad': 'Backups',
    'Copia de cada subtítulo sustituido, en {carpeta} (la misma carpeta que usa la skill).':
        'A copy of each replaced subtitle, in {carpeta} (the same folder the skill uses).',
    'Menú contextual del Explorador': 'File Explorer context menu',
    'Menú contextual del gestor de archivos': 'File manager context menu',
    'Busca subtítulos con el botón derecho del ratón, sin abrir antes la app.':
        'Search for subtitles with the right mouse button, without opening the app first.',
    'Busca subtítulos con el botón derecho del ratón, sin abrir antes la app. En Windows 11 está dentro de '
    '«Mostrar más opciones».':
        'Search for subtitles with the right mouse button, without opening the app first. In Windows 11 it is '
        'under “Show more options”.',
    'Mostrar «Bajar subtítulos» en el menú contextual': 'Show “Get subtitles” in the context menu',
    'En una carpeta: «Bajar subtítulos aquí», solo en esa carpeta o también en sus subcarpetas. En uno o varios '
    'vídeos: «Bajar subtítulos».':
        'On a folder: “Get subtitles here”, in that folder only or in its subfolders too. On one or more videos: '
        '“Get subtitles”.',
    'Versión portable: antes de borrar o mover su carpeta, desactívalo aquí.':
        'Portable version: before deleting or moving its folder, turn it off here.',
    'Al usarlo': 'When using it',
    'Mostrar la ventana': 'Show the window',
    'En segundo plano': 'In the background',
    'Mostrar la ventana: como al arrastrar a la app. En segundo plano: sin ventana; solo un icono junto al reloj '
    'mientras busca (para ver el progreso o cancelar) y un aviso con el resumen al terminar.':
        'Show the window: as when dragging onto the app. In the background: no window; just an icon next to the '
        'clock while searching (to see the progress or cancel) and a notification with the summary at the end.',
    'Solo en Windows.': 'Windows only.',
    'No disponible: este escritorio no muestra iconos junto al reloj. En GNOME se activan con la '
    'extensión «AppIndicator and KStatusNotifierItem Support».':
        'Not available: this desktop does not show icons next to the clock. In GNOME, they are enabled with '
        'the "AppIndicator and KStatusNotifierItem Support" extension.',
    'Todavía no está disponible en Linux: llegará en una próxima versión.':
        'Not available on Linux yet: it will come in a future version.',
    'No se ha podido cambiar el menú contextual ({error}).': 'The context menu could not be changed ({error}).',
    'Actualizaciones': 'Updates',
    'Buscar actualizaciones automáticamente': 'Check for updates automatically',
    'Al abrir la app, como mucho una vez al día, mira en GitHub si hay una versión nueva. Antes de instalar nada '
    'siempre te pregunta.':
        'When the app opens, at most once a day, it checks GitHub for a new version. It always asks you before '
        'installing anything.',
    'Versión instalada: {version}': 'Installed version: {version}',
    'Comprueba ahora si hay una versión nueva.': 'Check now for a new version.',
    'Buscar ahora': 'Check now',
    'Buscando en GitHub…': 'Checking GitHub…',
    'Hay una versión nueva: {version}.': 'There is a new version: {version}.',
    'Tienes la última versión ({version}).': 'You have the latest version ({version}).',
    'No se ha podido comprobar: {mensaje}': 'Could not check: {mensaje}',
    'Restaurar valores por defecto': 'Restore default values',
    'Cuentas de OpenSubtitles': 'OpenSubtitles accounts',
    'Opcionales, pero dan más resultados. opensubtitles.org y opensubtitles.com son cuentas distintas. Las '
    'contraseñas se guardan en el Administrador de credenciales de Windows, nunca en un archivo.':
        'Optional, but they give more results. opensubtitles.org and opensubtitles.com are separate accounts. '
        'Passwords are stored in Windows Credential Manager, never in a file.',
    'Solo se usa como último proveedor: se le piden subtítulos únicamente si los demás no han encontrado '
    'castellano (o, al final, inglés), porque sus cuentas solo permiten unas pocas descargas al día. Usa el '
    'nombre de usuario, no el email.':
        'Used only as the last provider: it is asked for subtitles only if the others have not found Spanish from '
        'Spain (or, at the end, English), because its accounts only allow a few downloads a day. Use your '
        'username, not your email.',
    'Se usará la cuenta «{usuario}» como último recurso.': 'The account “{usuario}” will be used as a last resort.',
    'Sin cuenta: no se usa opensubtitles.com.': 'No account: opensubtitles.com is not used.',
    'Usuario': 'Username',
    'Contraseña': 'Password',
    'Guardar': 'Save',
    'Probar conexión': 'Test connection',
    'Usar la cuenta de la skill': 'Use the skill’s account',
    'Importa {archivo}': 'Imports {archivo}',
    'Hay cambios sin guardar.': 'There are unsaved changes.',
    'Se usará la cuenta «{usuario}» en las búsquedas.': 'The account “{usuario}” will be used in searches.',
    'Sin cuenta: se busca en Addic7ed, Gestdown y Subtitulamos.':
        'No account: Addic7ed, Gestdown and Subtitulamos are searched.',
    'No se pudo guardar la contraseña en el Administrador de credenciales.':
        'The password could not be saved in Credential Manager.',
    'Comprobando la conexión con {sitio}…': 'Checking the connection to {sitio}…',
    'Conexión correcta.': 'Connection OK.',
    'Usuario o contraseña incorrectos.': 'Wrong username or password.',
    'No se pudo cargar el proveedor: {error}': 'The provider could not be loaded: {error}',
    'No se pudo conectar ({error}). Revisa la conexión a internet.':
        'Could not connect ({error}). Check your internet connection.',
    'Preferencias: {lista}': 'Preferences: {lista}',
    'Latino si no hay castellano': 'Latin American if there is no Spanish from Spain',
    'Solo castellano': 'Spanish from Spain only',
    'inglés como último recurso': 'English as a last resort',
    'sin inglés': 'no English',
    'también .en.srt': 'also .en.srt',
    'rehacer todo': 'redo everything',
    'máx. {n} vídeos por tanda': 'max. {n} videos per batch',
    'sin límite de vídeos': 'no video limit',

    # ---------- Menú contextual del Explorador ----------
    'Bajar subtítulos aquí': 'Get subtitles here',
    'Solo esta carpeta': 'This folder only',
    'Esta carpeta y sus subcarpetas': 'This folder and its subfolders',

    # ---------- Actualizaciones ----------
    'Novedades': 'What’s new',
    'Ocultar novedades': 'Hide what’s new',
    'Ver en GitHub': 'See on GitHub',
    'Más tarde': 'Later',
    'Cerrar': 'Close',
    'Actualizar': 'Update',
    'Descargar': 'Download',
    'Reintentar': 'Retry',
    'Hay una versión nueva: {version}': 'There is a new version: {version}',
    'Se descarga, se comprueba que es la publicada en GitHub y se instala sola. La app se cerrará y se volverá a '
    'abrir.':
        'It is downloaded, checked to be the one published on GitHub and installed by itself. The app will close '
        'and open again.',
    'Estás usando la versión portable: descarga la nueva desde su página en GitHub.':
        'You are using the portable version: download the new one from its page on GitHub.',
    'Descárgala desde su página en GitHub.': 'Download it from its page on GitHub.',
    'Descargando la versión {version}…': 'Downloading version {version}…',
    'Comprobando la huella SHA-256 mientras se descarga.': 'Checking the SHA-256 fingerprint while it downloads.',
    '{porcentaje} % · {hecho:.1f} de {total:.1f} MB': '{porcentaje} % · {hecho:.1f} of {total:.1f} MB',
    'Instalando la versión {version}…': 'Installing version {version}…',
    'La app se cierra ahora y se volverá a abrir sola en unos segundos.':
        'The app closes now and will open again by itself in a few seconds.',
    'No se ha podido actualizar': 'Could not update',
    'Actualizada a la versión {version}': 'Updated to version {version}',
    'Puedes ver qué ha cambiado en la página de esta versión.': 'You can see what has changed on this version’s page.',
    'Disponible cuando termine la búsqueda.': 'Available when the search ends.',
    'No se ha podido abrir el instalador ({error}).': 'The installer could not be opened ({error}).',
    'Error inesperado ({error}).': 'Unexpected error ({error}).',
    'Error inesperado al descargar ({error}).': 'Unexpected error while downloading ({error}).',
    'GitHub ha devuelto una respuesta demasiado grande.': 'GitHub returned a response that is too large.',
    'GitHub ha devuelto una respuesta inesperada.': 'GitHub returned an unexpected response.',
    'GitHub ha respondido con el error {codigo}.': 'GitHub responded with error {codigo}.',
    'No se ha podido conectar con GitHub. Comprueba la conexión a internet.':
        'Could not connect to GitHub. Check your internet connection.',
    'La actualización no tiene una huella SHA-256 con la que comprobarla.':
        'The update has no SHA-256 fingerprint to check it with.',
    'La actualización es demasiado grande: no se ha descargado.': 'The update is too large: it has not been downloaded.',
    'La descarga se ha interrumpido. Comprueba la conexión a internet.':
        'The download was interrupted. Check your internet connection.',
    'La descarga no coincide con la huella SHA-256 publicada en GitHub: no se ha instalado nada.':
        'The download does not match the SHA-256 fingerprint published on GitHub: nothing has been installed.',
}
