# geek-things

Hardware design monorepo built around atopile.

## Layout

- `hardware/boards/`: one standalone atopile project per board family member
- `hardware/packages/`: reusable internal hardware building blocks
- `hardware/contracts/`: board contracts consumed by firmware and host-side tools
- `firmware/`: board-specific and shared embedded code
- `software/tools/`: bring-up, manufacturing, and test tooling
- `docs/architecture/`: repository conventions and release rules
- `tools/ci/`: structure checks and CI helpers

## Current Board

- `hardware/boards/esp32s3_devkit`: USB-C powered ESP32-S3 development board
- Reusable packages extracted from this board:
  - `hardware/packages/power/usb_c_5v_input.ato`
  - `hardware/packages/power/ap2112k_3v3_ldo.ato`
  - `hardware/packages/common/esp32s3_module_core.ato`
  - `hardware/packages/common/esp32s3_devkit_io.ato`

## Compiler Development

The `atopile` compiler is vendored as a git submodule at `third_party/atopile`.

```bash
git submodule update --init --recursive
uv sync --locked --python 3.14
```

## Common Commands

```bash
uv sync
uv run python tools/ci/monorepo.py --check
uv run python tools/ci/monorepo.py --json-boards
uv run python tools/ci/monorepo.py --build-board esp32s3_devkit
uv run python tools/ci/monorepo.py --build-board esp32s3_devkit --frozen
```

Successful `ato build` runs now produce:

- `layouts/default/default.kicad_pcb`
- `build/builds/default/default.canonical_design.json`

Paths are relative to each board directory under `hardware/boards/<board>/`.

Build a board directly from its project directory:

```bash
cd hardware/boards/esp32s3_devkit
uv run ato build
uv run ato build --frozen
```

## KiCad Layout Safety

`uv run python tools/ci/monorepo.py --build-board <board>` and `uv run ato build`
update the board's checked-in `layouts/default/default.kicad_pcb` in place.
That file is a layout source file, not a disposable build artifact.

If you edited the PCB manually in KiCad, a later build may rewrite parts of that
layout when the `.ato` design changes. The usual risk points are:

- adding or removing footprints
- changing instance names or hierarchy in `.ato`
- changing nets, picked parts, or footprints
- letting atopile re-apply board appearance and managed layout state

Recommended workflow before rebuilding a board with manual KiCad edits:

1. Commit or otherwise checkpoint `layouts/default/default.kicad_pcb`.
2. Run a frozen check first:

```bash
uv run python tools/ci/monorepo.py --build-board esp32s3_devkit --frozen
```

3. If frozen mode reports layout changes, inspect the difference before running a
   normal build.
4. If you decide the update is acceptable, rerun without `--frozen`.

Notes:

- `--frozen` is only meaningful for `--build-board` and `--build-all`.
- Regular `--build-board` will still back up the previous layout under
  `hardware/boards/<board>/build/builds/default/backups/`.
- Even when builds succeed, treat large `.ato` refactors after manual routing as
  potentially layout-destructive until reviewed.
