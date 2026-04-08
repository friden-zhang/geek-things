# Firmware

Board-specific firmware lives in `boards/`, while reusable code lives in `shared/`.

Firmware should depend on hardware contracts instead of reaching into atopile source files directly.
