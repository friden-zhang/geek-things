# Monorepo Architecture

## Goals

- Keep each PCB as an independently buildable atopile project.
- Share reusable hardware modules through internal packages instead of copy/paste.
- Keep firmware and host-side tooling aligned through explicit board contracts.
- Release the whole repository under one version number for internal iteration speed.

## Directory Rules

- `hardware/boards/<board>/` owns one board's `ato.yaml`, source, layout assets, and outputs.
- `hardware/packages/interfaces/` contains reusable connectors, buses, and board-to-board interfaces.
- `hardware/packages/power/` contains reusable power entry, regulation, protection, and measurement blocks.
- `hardware/packages/common/` contains shared support circuits such as clocks, LED blocks, MCU helpers, and sensor glue.
- `hardware/contracts/<board>.yaml` is the stable handoff surface from hardware into firmware and host tooling.
- `firmware/boards/<board>/` contains board-local firmware configuration and code.
- `firmware/shared/` contains code shared across multiple firmware targets.
- `software/tools/` contains bring-up, factory, and validation tools that run on the host.

## Versioning

- The repository root `VERSION` file is the single release source of truth.
- Hardware artifacts should be labeled as `<version>-<board>`, for example `0.1.0-app`.
- Firmware images and host-side tools should publish against the same repository version window.

## Board Contracts

Every board must have a companion contract file in `hardware/contracts/`. That file records:

- board identifier
- version source
- firmware target path
- expected host-side tools
- named interfaces and test hooks

Firmware and software should consume the contract file or a future generated derivative instead of scraping atopile sources directly.

## CI Workflow

- `tools/ci/monorepo.py --check` validates the expected repository shape.
- `tools/ci/monorepo.py --json-boards` emits a board list for CI matrix discovery.
- `tools/ci/monorepo.py --build-board <board>` runs `ato build` in one board directory.

CI should validate structure and discover boards up front, then run per-board hardware builds in parallel after both checks succeed.

## Adding A New Board

1. Create `hardware/boards/<board>/` with its own `ato.yaml`, `src/main.ato`, `layouts/`, and `README.md`.
2. Add `hardware/contracts/<board>.yaml`.
3. Add `firmware/boards/<board>/`.
4. Wire the board into any shared software tooling that depends on its contract.
5. Verify with `python3 tools/ci/monorepo.py --check` and `python3 tools/ci/monorepo.py --build-board <board>`.
