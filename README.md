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

## Common Commands

```bash
python3 tools/ci/monorepo.py --check
python3 tools/ci/monorepo.py --json-boards
python3 tools/ci/monorepo.py --build-board app
```

Build a board directly from its project directory:

```bash
cd hardware/boards/app
ato build
```
