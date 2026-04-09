# Hardware Packages

Internal packages are organized by reuse boundary:

- `interfaces/`: buses, connectors, board-to-board interfaces, and test-point naming schemes
- `power/`: power entry, protection, regulation, supervision, and measurement blocks
- `common/`: reusable support circuits that are not interface- or power-specific

Package files should use `snake_case.ato` filenames and expose `PascalCase` modules or interfaces.

Current extracted packages:

- `power/usb_c_5v_input.ato`: USB-C sink-side input with fuse, ESD, and CC handling via the upstream connector package
- `power/ap2112k_3v3_ldo.ato`: concrete AP2112K-3.3 5V-to-3V3 regulation stage
- `common/esp32s3_module_core.ato`: ESP32-S3-WROOM-1 core, strapping, USB, and default bus assignments
- `common/esp32s3_devkit_io.ato`: BOOT/RESET/USER buttons plus WS2812B-2020 status LED
