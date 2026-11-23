"""Lo que cambia según el sistema operativo.

- SISTEMA: 'windows' o 'linux'. Es también el nombre de las marcas [Windows] y [Linux] del CHANGELOG
  (ver actualizar.py: la app solo avisa de las versiones con cambios para su sistema).
- windows.py: llamadas a Windows (mutex, registro, shell32…). Solo se usa en Windows.
- menu_windows.py: el menú contextual del Explorador, en el registro.

Lo común (qué hacer y cuándo) está en el resto de la app; aquí solo cómo se hace en cada sistema.
"""
import sys

WINDOWS = sys.platform == 'win32'
LINUX = sys.platform.startswith('linux')
SISTEMA = 'windows' if WINDOWS else 'linux' if LINUX else sys.platform
