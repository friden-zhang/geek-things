# Hardware

Each directory in `boards/` is an independently buildable atopile project.

Shared hardware building blocks live in `packages/`, and every board publishes a stable handoff contract in `contracts/`.

The first concrete board in this repo is `esp32s3_devkit`, which also seeds the first reusable power and common packages.
