# Atopile EasyEDA Pro Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the forked `atopile` compiler as a child repo and add a versioned canonical IR, stable IDs, and backend contracts without breaking the current KiCad build flow.

**Architecture:** Phase 1 keeps KiCad as the only emitted layout backend in practice, but moves semantic ownership into the compiler fork by introducing `Canonical Design IR`, stable object identity, and backend-sidecar contracts. The current `ato build --target/-t` flag already selects build targets, so phase 1 must not repurpose that CLI flag yet; backend selection stays internal until the EasyEDA Pro backend is real.

**Tech Stack:** Git submodules, `uv`, Python 3.14, Typer CLI, standard-library `dataclasses`/`json`, `unittest`, `pytest`, GitHub Actions, `faebryk` PCB exporters.

---

## File Structure

### Monorepo files

- `.gitmodules`
  Pins `third_party/atopile/` to `https://github.com/friden-zhang/atopile.git`.
- `pyproject.toml`
  Keeps the dependency name as `atopile` but points `uv` at the local editable child repo.
- `uv.lock`
  Records the local editable source after the repo switches from PyPI-only to child-repo development.
- `README.md`
  Documents `git submodule update --init --recursive` and the fact that builds now emit a canonical IR snapshot.
- `docs/architecture/monorepo.md`
  Documents the child-repo boundary and the new canonical build artifact.
- `.github/workflows/monorepo-ci.yml`
  Ensures checkout pulls submodules before `uv sync`.
- `tools/ci/monorepo.py`
  Validates child-repo presence and verifies that a successful board build emitted `default.canonical_design.json`.
- `tests/test_monorepo_ci.py`
  Covers repo-shape validation, submodule wiring, and canonical artifact checks.

### Child repo files

- `third_party/atopile/src/atopile/model/design_ir/__init__.py`
  Re-exports the canonical IR types and helpers.
- `third_party/atopile/src/atopile/model/design_ir/schema.py`
  Defines the versioned logical, schematic, physical, and backend-projection IR dataclasses.
- `third_party/atopile/src/atopile/model/design_ir/identity.py`
  Defines stable ID seeds and deterministic hash helpers.
- `third_party/atopile/src/atopile/model/design_ir/serde.py`
  Converts IR objects to and from versioned JSON payloads.
- `third_party/atopile/src/atopile/model/design_ir/from_build.py`
  Builds the phase 1 canonical snapshot from the current build context.
- `third_party/atopile/src/atopile/model/__init__.py`
  Exposes the new IR package through the existing `atopile.model` namespace.
- `third_party/atopile/src/atopile/backends/__init__.py`
  Re-exports backend contracts.
- `third_party/atopile/src/atopile/backends/base.py`
  Defines `BuildBackend`, project artifact descriptors, and edit classification enums.
- `third_party/atopile/src/atopile/backends/sidecar.py`
  Defines `identity-map.json`, `managed-objects.json`, and `roundtrip-metadata.json` schemas plus JSON read/write helpers.
- `third_party/atopile/src/atopile/backends/kicad.py`
  Wraps the existing KiCad layout output as a formal backend contract without rewriting the existing KiCad transformer.
- `third_party/atopile/src/atopile/backends/easyeda_pro.py`
  Declares the EasyEDA Pro backend contract surface for phase 2 without pretending the serializer exists yet.
- `third_party/atopile/src/atopile/build_steps.py`
  Calls the canonical snapshot writer and the new KiCad backend sidecar writer.
- `third_party/atopile/test/compiler/test_design_ir_identity.py`
  Covers stable ID determinism and JSON round-tripping.
- `third_party/atopile/test/compiler/test_design_ir_artifacts.py`
  Covers canonical snapshot file paths and versioned JSON emission.
- `third_party/atopile/test/exporters/test_backend_contracts.py`
  Covers backend registry behavior and sidecar schema round-tripping.

## Task 1: Vendor The Forked Compiler Into The Monorepo

**Files:**
- Create: `.gitmodules`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `README.md`
- Modify: `.github/workflows/monorepo-ci.yml`
- Modify: `tools/ci/monorepo.py`
- Test: `tests/test_monorepo_ci.py`

- [ ] **Step 1: Write the failing repo-wiring tests**

```python
# tests/test_monorepo_ci.py
    def test_validate_repo_requires_atopile_submodule(self):
        module = load_monorepo_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            make_shared_structure(repo_root)
            make_board(repo_root, "esp32s3_devkit")

            errors = module.validate_repo(repo_root)

            self.assertTrue(any("third_party/atopile" in error for error in errors))

    def test_repo_uses_vendored_atopile_source(self):
        repo_root = Path(__file__).resolve().parents[1]
        pyproject_text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn("[tool.uv.sources]", pyproject_text)
        self.assertIn(
            'atopile = { path = "third_party/atopile", editable = true }',
            pyproject_text,
        )
```

- [ ] **Step 2: Run the repo-wiring tests and verify they fail**

Run: `uv run python -m unittest tests.test_monorepo_ci.MonorepoCiTests.test_validate_repo_requires_atopile_submodule tests.test_monorepo_ci.MonorepoCiTests.test_repo_uses_vendored_atopile_source -v`

Expected: FAIL because `validate_repo()` does not require `third_party/atopile` yet and `pyproject.toml` still points only at the published package.

- [ ] **Step 3: Add the child repo, prefer it in `uv`, and make CI fetch it**

```ini
# .gitmodules
[submodule "third_party/atopile"]
    path = third_party/atopile
    url = https://github.com/friden-zhang/atopile.git
```

```toml
# pyproject.toml
[project]
name = "geek-things"
version = "0.1.0"
description = "Hardware design monorepo built around atopile."
requires-python = ">=3.14"
dependencies = [
    "atopile==0.15.3",
]

[tool.uv]
package = false

[tool.uv.sources]
atopile = { path = "third_party/atopile", editable = true }
```

```yaml
# .github/workflows/monorepo-ci.yml
      - uses: actions/checkout@v4
        with:
          submodules: recursive
```

```python
# tools/ci/monorepo.py
ATOPILE_SUBMODULE = Path("third_party") / "atopile"

def validate_repo(repo_root: Path) -> list[str]:
    errors: list[str] = []

    required_dirs = [
        repo_root / "hardware" / "boards",
        repo_root / "hardware" / "contracts",
        repo_root / "hardware" / "packages" / "interfaces",
        repo_root / "hardware" / "packages" / "power",
        repo_root / "hardware" / "packages" / "common",
        repo_root / "firmware" / "shared",
        repo_root / "firmware" / "boards",
        repo_root / "software" / "tools",
        repo_root / "docs" / "architecture",
        repo_root / "tools" / "ci",
        repo_root / ATOPILE_SUBMODULE,
    ]

    for path in required_dirs:
        if not path.is_dir():
            errors.append(f"Missing required directory: {path.relative_to(repo_root)}")

    required_submodule_files = [
        repo_root / ATOPILE_SUBMODULE / "pyproject.toml",
        repo_root / ATOPILE_SUBMODULE / "src" / "atopile" / "cli" / "cli.py",
    ]
    for path in required_submodule_files:
        if not path.is_file():
            errors.append(f"Missing required compiler path: {path.relative_to(repo_root)}")

    return errors
```

```markdown
# README.md
## Compiler Development

This repository vendors the forked `atopile` compiler as a git submodule at
`third_party/atopile/`.

Bootstrap a fresh checkout with:

`git submodule update --init --recursive`
`uv sync --locked --python 3.14`
```

```bash
git submodule add https://github.com/friden-zhang/atopile.git third_party/atopile
git submodule update --init --recursive
uv lock
```

- [ ] **Step 4: Run the monorepo tests and the repo shape check**

Run: `uv run python -m unittest discover -s tests -v && uv run python tools/ci/monorepo.py --check`

Expected: PASS with output ending in `Monorepo structure OK (1 board(s))`.

- [ ] **Step 5: Commit the monorepo wiring**

```bash
git add .gitmodules pyproject.toml uv.lock README.md .github/workflows/monorepo-ci.yml tools/ci/monorepo.py tests/test_monorepo_ci.py third_party/atopile
git commit -m "feat(monorepo): vendor forked atopile compiler"
```

## Task 2: Add The Canonical IR Schema And Stable IDs

**Files:**
- Create: `third_party/atopile/src/atopile/model/design_ir/__init__.py`
- Create: `third_party/atopile/src/atopile/model/design_ir/schema.py`
- Create: `third_party/atopile/src/atopile/model/design_ir/identity.py`
- Create: `third_party/atopile/src/atopile/model/design_ir/serde.py`
- Modify: `third_party/atopile/src/atopile/model/__init__.py`
- Test: `third_party/atopile/test/compiler/test_design_ir_identity.py`

- [ ] **Step 1: Write failing IR schema and identity tests**

```python
# third_party/atopile/test/compiler/test_design_ir_identity.py
from atopile.model.design_ir.identity import StableIdSeed, canonical_object_id
from atopile.model.design_ir.schema import (
    CanonicalDesign,
    LogicalDesign,
    PhysicalPcbIntent,
    SchematicIntent,
)
from atopile.model.design_ir.serde import design_from_json, design_to_json


def test_canonical_object_id_is_deterministic_for_same_seed():
    seed = StableIdSeed(
        object_kind="logical-instance",
        semantic_path=("App", "regulator"),
        projection_role="default",
    )

    assert canonical_object_id(seed) == canonical_object_id(seed)


def test_canonical_design_json_roundtrip():
    design = CanonicalDesign(
        schema_version="v1",
        identity_version="v1",
        logical=LogicalDesign(instances=[], nets=[]),
        schematic=SchematicIntent(sheets=[], symbols=[], texts=[]),
        physical=PhysicalPcbIntent(
            board_outline=[],
            footprints=[],
            holes=[],
            keepouts=[],
        ),
    )

    restored = design_from_json(design_to_json(design))

    assert restored == design
```

- [ ] **Step 2: Run the IR tests and verify they fail**

Run: `cd third_party/atopile && uv run pytest test/compiler/test_design_ir_identity.py -v`

Expected: FAIL with import errors because `atopile.model.design_ir` does not exist yet.

- [ ] **Step 3: Implement the versioned IR schema, stable ID seed, and JSON serializer**

```python
# third_party/atopile/src/atopile/model/design_ir/schema.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SchemaVersion = Literal["v1"]
IdentityVersion = Literal["v1"]


@dataclass(frozen=True)
class LogicalInstance:
    stable_id: str
    design_path: tuple[str, ...]
    type_name: str
    role: str
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class LogicalNet:
    stable_id: str
    name: str
    member_paths: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class LogicalDesign:
    instances: list[LogicalInstance]
    nets: list[LogicalNet]


@dataclass(frozen=True)
class SchematicSheet:
    stable_id: str
    name: str
    order: int


@dataclass(frozen=True)
class SchematicSymbol:
    stable_id: str
    logical_instance_id: str
    sheet_id: str
    x_mm: float
    y_mm: float
    rotation_deg: float


@dataclass(frozen=True)
class SchematicText:
    stable_id: str
    sheet_id: str
    text: str
    x_mm: float
    y_mm: float


@dataclass(frozen=True)
class SchematicIntent:
    sheets: list[SchematicSheet]
    symbols: list[SchematicSymbol]
    texts: list[SchematicText]


@dataclass(frozen=True)
class BoardPoint:
    x_mm: float
    y_mm: float


@dataclass(frozen=True)
class PhysicalFootprint:
    stable_id: str
    logical_instance_id: str
    refdes: str
    x_mm: float
    y_mm: float
    rotation_deg: float
    side: Literal["top", "bottom"]


@dataclass(frozen=True)
class DrillHole:
    stable_id: str
    x_mm: float
    y_mm: float
    diameter_mm: float


@dataclass(frozen=True)
class KeepoutRegion:
    stable_id: str
    layer: str
    points: list[BoardPoint]


@dataclass(frozen=True)
class PhysicalPcbIntent:
    board_outline: list[BoardPoint]
    footprints: list[PhysicalFootprint]
    holes: list[DrillHole]
    keepouts: list[KeepoutRegion]


@dataclass(frozen=True)
class BackendProjectionMetadata:
    kicad_ids: dict[str, str] = field(default_factory=dict)
    easyeda_pro_ids: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalDesign:
    schema_version: SchemaVersion
    identity_version: IdentityVersion
    logical: LogicalDesign
    schematic: SchematicIntent
    physical: PhysicalPcbIntent
    backend_projection: BackendProjectionMetadata = field(
        default_factory=BackendProjectionMetadata
    )
```

```python
# third_party/atopile/src/atopile/model/design_ir/identity.py
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class StableIdSeed:
    object_kind: str
    semantic_path: tuple[str, ...]
    projection_role: str


def canonical_object_id(seed: StableIdSeed) -> str:
    token = "|".join(
        (
            "v1",
            seed.object_kind,
            "/".join(seed.semantic_path),
            seed.projection_role,
        )
    )
    digest = sha256(token.encode("utf-8")).hexdigest()[:16]
    return f"{seed.object_kind}:{digest}"
```

```python
# third_party/atopile/src/atopile/model/design_ir/serde.py
from __future__ import annotations

import json
from dataclasses import asdict

from atopile.model.design_ir.schema import (
    BackendProjectionMetadata,
    BoardPoint,
    CanonicalDesign,
    DrillHole,
    KeepoutRegion,
    LogicalDesign,
    LogicalInstance,
    LogicalNet,
    PhysicalFootprint,
    PhysicalPcbIntent,
    SchematicIntent,
    SchematicSheet,
    SchematicSymbol,
    SchematicText,
)


def design_to_json(design: CanonicalDesign) -> str:
    return json.dumps(asdict(design), indent=2, sort_keys=True)


def _board_point(data: dict) -> BoardPoint:
    return BoardPoint(**data)


def design_from_json(payload: str) -> CanonicalDesign:
    data = json.loads(payload)
    return CanonicalDesign(
        schema_version=data["schema_version"],
        identity_version=data["identity_version"],
        logical=LogicalDesign(
            instances=[LogicalInstance(**item) for item in data["logical"]["instances"]],
            nets=[LogicalNet(**item) for item in data["logical"]["nets"]],
        ),
        schematic=SchematicIntent(
            sheets=[SchematicSheet(**item) for item in data["schematic"]["sheets"]],
            symbols=[SchematicSymbol(**item) for item in data["schematic"]["symbols"]],
            texts=[SchematicText(**item) for item in data["schematic"]["texts"]],
        ),
        physical=PhysicalPcbIntent(
            board_outline=[_board_point(item) for item in data["physical"]["board_outline"]],
            footprints=[
                PhysicalFootprint(**item) for item in data["physical"]["footprints"]
            ],
            holes=[DrillHole(**item) for item in data["physical"]["holes"]],
            keepouts=[
                KeepoutRegion(
                    stable_id=item["stable_id"],
                    layer=item["layer"],
                    points=[_board_point(point) for point in item["points"]],
                )
                for item in data["physical"]["keepouts"]
            ],
        ),
        backend_projection=BackendProjectionMetadata(
            **data.get("backend_projection", {})
        ),
    )
```

```python
# third_party/atopile/src/atopile/model/design_ir/__init__.py
from atopile.model.design_ir.identity import StableIdSeed, canonical_object_id
from atopile.model.design_ir.schema import CanonicalDesign
from atopile.model.design_ir.serde import design_from_json, design_to_json

__all__ = [
    "CanonicalDesign",
    "StableIdSeed",
    "canonical_object_id",
    "design_to_json",
    "design_from_json",
]
```

```python
# third_party/atopile/src/atopile/model/__init__.py
__all__ = ["build_history", "build_queue", "builds", "model_state", "design_ir"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        return importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

- [ ] **Step 4: Run the new compiler tests**

Run: `cd third_party/atopile && uv run pytest test/compiler/test_design_ir_identity.py -v`

Expected: PASS with 2 tests passing.

- [ ] **Step 5: Commit the canonical IR foundation**

```bash
git -C third_party/atopile add src/atopile/model/__init__.py src/atopile/model/design_ir test/compiler/test_design_ir_identity.py
git -C third_party/atopile commit -m "feat(model): add canonical design ir foundation"
```

## Task 3: Emit A Versioned Canonical Snapshot During Builds

**Files:**
- Create: `third_party/atopile/src/atopile/model/design_ir/from_build.py`
- Modify: `third_party/atopile/src/atopile/build_steps.py`
- Test: `third_party/atopile/test/compiler/test_design_ir_artifacts.py`

- [ ] **Step 1: Write failing snapshot artifact tests**

```python
# third_party/atopile/test/compiler/test_design_ir_artifacts.py
import json

from atopile.model.design_ir.from_build import (
    canonical_design_artifact_path,
    minimal_phase1_design,
    write_canonical_design_snapshot,
)


def test_canonical_design_artifact_path_uses_output_base_suffix(tmp_path):
    output_base = tmp_path / "build" / "builds" / "default" / "default"

    assert (
        canonical_design_artifact_path(output_base)
        == output_base.with_suffix(".canonical_design.json")
    )


def test_write_canonical_design_snapshot_writes_versioned_json(tmp_path):
    output_base = tmp_path / "build" / "builds" / "default" / "default"
    output_base.parent.mkdir(parents=True, exist_ok=True)

    design = minimal_phase1_design(
        build_name="default",
        entry_address="src/main.ato:App",
        layout_path="layouts/default/default.kicad_pcb",
    )
    artifact_path = write_canonical_design_snapshot(output_base, design)

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact_path.name == "default.canonical_design.json"
    assert payload["schema_version"] == "v1"
    assert payload["identity_version"] == "v1"
```

- [ ] **Step 2: Run the snapshot tests and verify they fail**

Run: `cd third_party/atopile && uv run pytest test/compiler/test_design_ir_artifacts.py -v`

Expected: FAIL because `from_build.py` does not exist yet.

- [ ] **Step 3: Add a phase 1 build-to-IR snapshot writer and call it from the build pipeline**

```python
# third_party/atopile/src/atopile/model/design_ir/from_build.py
from __future__ import annotations

from pathlib import Path

from atopile.model.design_ir.identity import StableIdSeed, canonical_object_id
from atopile.model.design_ir.schema import (
    CanonicalDesign,
    LogicalDesign,
    LogicalInstance,
    PhysicalPcbIntent,
    SchematicIntent,
    SchematicSheet,
)
from atopile.model.design_ir.serde import design_to_json


def canonical_design_artifact_path(output_base: Path) -> Path:
    return output_base.with_suffix(".canonical_design.json")


def minimal_phase1_design(
    *, build_name: str, entry_address: str, layout_path: str
) -> CanonicalDesign:
    entry_file, entry_section = entry_address.split(":", 1)
    logical_instance_id = canonical_object_id(
        StableIdSeed(
            object_kind="logical-instance",
            semantic_path=(entry_address, build_name),
            projection_role="root",
        )
    )
    sheet_id = canonical_object_id(
        StableIdSeed(
            object_kind="schematic-sheet",
            semantic_path=(entry_address, build_name),
            projection_role="sheet-0",
        )
    )
    return CanonicalDesign(
        schema_version="v1",
        identity_version="v1",
        logical=LogicalDesign(
            instances=[
                LogicalInstance(
                    stable_id=logical_instance_id,
                    design_path=(entry_file, entry_section),
                    type_name=entry_section,
                    role="entry",
                    attributes={"layout_path": layout_path},
                )
            ],
            nets=[],
        ),
        schematic=SchematicIntent(
            sheets=[SchematicSheet(stable_id=sheet_id, name=build_name, order=0)],
            symbols=[],
            texts=[],
        ),
        physical=PhysicalPcbIntent(
            board_outline=[],
            footprints=[],
            holes=[],
            keepouts=[],
        ),
    )


def write_canonical_design_snapshot(output_base: Path, design: CanonicalDesign) -> Path:
    artifact_path = canonical_design_artifact_path(output_base)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(design_to_json(design), encoding="utf-8")
    return artifact_path
```

```python
# third_party/atopile/src/atopile/build_steps.py
from atopile.model.design_ir.from_build import (
    minimal_phase1_design,
    write_canonical_design_snapshot,
)


def write_phase1_canonical_snapshot() -> Path:
    design = minimal_phase1_design(
        build_name=config.build.name,
        entry_address=str(config.build.address),
        layout_path=str(config.build.paths.layout.relative_to(config.project.paths.root)),
    )
    return write_canonical_design_snapshot(config.build.paths.output_base, design)


# Call immediately after the managed KiCad layout has been written.
canonical_snapshot_path = write_phase1_canonical_snapshot()
logger.info("Wrote canonical design snapshot to %s", canonical_snapshot_path)
```

- [ ] **Step 4: Run the new artifact tests**

Run: `cd third_party/atopile && uv run pytest test/compiler/test_design_ir_artifacts.py -v`

Expected: PASS with 2 tests passing.

- [ ] **Step 5: Commit the canonical snapshot plumbing**

```bash
git -C third_party/atopile add src/atopile/model/design_ir/from_build.py src/atopile/build_steps.py test/compiler/test_design_ir_artifacts.py
git -C third_party/atopile commit -m "feat(build): emit canonical design snapshots"
```

## Task 4: Add Backend Contracts And Round-Trip Sidecar Schemas

**Files:**
- Create: `third_party/atopile/src/atopile/backends/__init__.py`
- Create: `third_party/atopile/src/atopile/backends/base.py`
- Create: `third_party/atopile/src/atopile/backends/sidecar.py`
- Create: `third_party/atopile/src/atopile/backends/kicad.py`
- Create: `third_party/atopile/src/atopile/backends/easyeda_pro.py`
- Modify: `third_party/atopile/src/atopile/build_steps.py`
- Test: `third_party/atopile/test/exporters/test_backend_contracts.py`

- [ ] **Step 1: Write failing backend contract tests**

```python
# third_party/atopile/test/exporters/test_backend_contracts.py
from atopile.backends.easyeda_pro import EasyedaProBackend
from atopile.backends.kicad import KicadBackend
from atopile.backends.sidecar import (
    IdentityMap,
    ManagedObjects,
    RoundTripMetadata,
    SidecarBundle,
    read_sidecar_bundle,
    write_sidecar_bundle,
)


def test_kicad_backend_uses_v1_contract():
    backend = KicadBackend()

    assert backend.name == "kicad"
    assert backend.contract_version == "v1"
    assert backend.edit_policy["layout"] == "compiler-managed"


def test_sidecar_bundle_roundtrip(tmp_path):
    bundle = SidecarBundle(
        identity_map=IdentityMap(entries={"fp:R1": "logical-instance:abcd1234"}),
        managed_objects=ManagedObjects(entries={"layout": ["fp:R1"]}),
        roundtrip_metadata=RoundTripMetadata(
            policy_version="v1",
            editable_classes=["symbol-placement", "footprint-placement"],
            local_only_classes=["visual-style"],
            reject_classes=["net-topology"],
        ),
    )

    write_sidecar_bundle(tmp_path, bundle)
    restored = read_sidecar_bundle(tmp_path)

    assert restored == bundle


def test_easyeda_backend_is_declared_but_not_emitting_yet():
    backend = EasyedaProBackend()

    assert backend.name == "easyeda_pro"
    assert backend.contract_version == "v1"
    assert backend.supports_native_emit is False
```

- [ ] **Step 2: Run the backend tests and verify they fail**

Run: `cd third_party/atopile && uv run pytest test/exporters/test_backend_contracts.py -v`

Expected: FAIL because the backend package does not exist yet.

- [ ] **Step 3: Implement the backend protocol, KiCad adapter, and sidecar bundle**

```python
# third_party/atopile/src/atopile/backends/base.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from atopile.model.design_ir.schema import CanonicalDesign

ObjectSyncPolicy = Literal[
    "compiler-managed",
    "safe-apply",
    "preserve-local-only",
    "conflict-reject",
]


@dataclass(frozen=True)
class BackendProjectArtifacts:
    project_root: Path
    managed_files: tuple[Path, ...]
    sidecar_files: tuple[Path, ...]


class BuildBackend(Protocol):
    name: str
    contract_version: str

    def emit_sidecars(
        self, output_root: Path, canonical_design: CanonicalDesign
    ) -> BackendProjectArtifacts:
        pass
```

```python
# third_party/atopile/src/atopile/backends/__init__.py
from atopile.backends.easyeda_pro import EasyedaProBackend
from atopile.backends.kicad import KicadBackend

__all__ = ["EasyedaProBackend", "KicadBackend"]
```

```python
# third_party/atopile/src/atopile/backends/sidecar.py
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class IdentityMap:
    entries: dict[str, str]


@dataclass(frozen=True)
class ManagedObjects:
    entries: dict[str, list[str]]


@dataclass(frozen=True)
class RoundTripMetadata:
    policy_version: str
    editable_classes: list[str]
    local_only_classes: list[str]
    reject_classes: list[str]


@dataclass(frozen=True)
class SidecarBundle:
    identity_map: IdentityMap
    managed_objects: ManagedObjects
    roundtrip_metadata: RoundTripMetadata


def write_sidecar_bundle(output_root: Path, bundle: SidecarBundle) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "identity-map.json").write_text(
        json.dumps(asdict(bundle.identity_map), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_root / "managed-objects.json").write_text(
        json.dumps(asdict(bundle.managed_objects), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_root / "roundtrip-metadata.json").write_text(
        json.dumps(asdict(bundle.roundtrip_metadata), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def read_sidecar_bundle(output_root: Path) -> SidecarBundle:
    identity_map = IdentityMap(
        **json.loads((output_root / "identity-map.json").read_text(encoding="utf-8"))
    )
    managed_objects = ManagedObjects(
        **json.loads(
            (output_root / "managed-objects.json").read_text(encoding="utf-8")
        )
    )
    roundtrip_metadata = RoundTripMetadata(
        **json.loads(
            (output_root / "roundtrip-metadata.json").read_text(encoding="utf-8")
        )
    )
    return SidecarBundle(identity_map, managed_objects, roundtrip_metadata)
```

```python
# third_party/atopile/src/atopile/backends/kicad.py
from __future__ import annotations

from pathlib import Path

from atopile.backends.base import BackendProjectArtifacts
from atopile.backends.sidecar import (
    IdentityMap,
    ManagedObjects,
    RoundTripMetadata,
    SidecarBundle,
    write_sidecar_bundle,
)
from atopile.model.design_ir.schema import CanonicalDesign


class KicadBackend:
    name = "kicad"
    contract_version = "v1"
    edit_policy = {
        "layout": "compiler-managed",
        "symbol-placement": "safe-apply",
        "footprint-placement": "safe-apply",
    }

    def emit_sidecars(
        self, output_root: Path, canonical_design: CanonicalDesign
    ) -> BackendProjectArtifacts:
        bundle = SidecarBundle(
            identity_map=IdentityMap(
                entries={
                    footprint.stable_id: footprint.logical_instance_id
                    for footprint in canonical_design.physical.footprints
                }
            ),
            managed_objects=ManagedObjects(entries={"layout": ["default"]}),
            roundtrip_metadata=RoundTripMetadata(
                policy_version="v1",
                editable_classes=["symbol-placement", "footprint-placement"],
                local_only_classes=["visual-style"],
                reject_classes=["net-topology"],
            ),
        )
        write_sidecar_bundle(output_root, bundle)
        return BackendProjectArtifacts(
            project_root=output_root,
            managed_files=(),
            sidecar_files=(
                output_root / "identity-map.json",
                output_root / "managed-objects.json",
                output_root / "roundtrip-metadata.json",
            ),
        )
```

```python
# third_party/atopile/src/atopile/backends/easyeda_pro.py
class EasyedaProBackend:
    name = "easyeda_pro"
    contract_version = "v1"
    supports_native_emit = False
    project_extension = ".epro"
```

```python
# third_party/atopile/src/atopile/build_steps.py
from atopile.backends.kicad import KicadBackend
from atopile.model.design_ir.from_build import canonical_design_artifact_path
from atopile.model.design_ir.serde import design_from_json


canonical_snapshot_file = canonical_design_artifact_path(config.build.paths.output_base)
canonical_design = design_from_json(canonical_snapshot_file.read_text(encoding="utf-8"))
KicadBackend().emit_sidecars(
    config.build.paths.output_base.parent,
    canonical_design,
)
```

- [ ] **Step 4: Run the backend contract tests and one existing KiCad exporter regression**

Run: `cd third_party/atopile && uv run pytest test/exporters/test_backend_contracts.py test/exporters/pcb/kicad/test_pcb_transformer.py -v`

Expected: PASS with both the new contract tests and the existing KiCad transformer regression staying green.

- [ ] **Step 5: Commit the backend contract layer**

```bash
git -C third_party/atopile add src/atopile/backends src/atopile/build_steps.py test/exporters/test_backend_contracts.py
git -C third_party/atopile commit -m "feat(backends): add phase 1 backend contracts"
```

## Task 5: Verify The Real Board Fixture And Gate CI On The Canonical Artifact

**Files:**
- Modify: `tools/ci/monorepo.py`
- Modify: `tests/test_monorepo_ci.py`
- Modify: `README.md`
- Modify: `docs/architecture/monorepo.md`

- [ ] **Step 1: Write failing monorepo artifact-validation tests**

```python
# tests/test_monorepo_ci.py
    def test_build_board_requires_canonical_design_artifact(self):
        module = load_monorepo_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            make_shared_structure(repo_root)
            make_board(repo_root, "esp32s3_devkit")
            build_dir = (
                repo_root
                / "hardware"
                / "boards"
                / "esp32s3_devkit"
                / "build"
                / "builds"
                / "default"
            )
            calls: list[tuple[list[str], Path, bool]] = []

            def fake_run(cmd, cwd, check):
                calls.append((cmd, cwd, check))
                build_dir.mkdir(parents=True, exist_ok=True)
                (build_dir / "default.canonical_design.json").write_text(
                    '{"schema_version":"v1","identity_version":"v1"}',
                    encoding="utf-8",
                )

                class Result:
                    returncode = 0

                return Result()

            original_run = module.subprocess.run
            module.subprocess.run = fake_run
            try:
                exit_code = module.build_board(repo_root, "esp32s3_devkit", frozen=False)
            finally:
                module.subprocess.run = original_run

            self.assertEqual(exit_code, 0)

    def test_build_board_fails_if_canonical_design_artifact_is_missing(self):
        module = load_monorepo_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            make_shared_structure(repo_root)
            make_board(repo_root, "esp32s3_devkit")

            def fake_run(cmd, cwd, check):
                class Result:
                    returncode = 0

                return Result()

            original_run = module.subprocess.run
            module.subprocess.run = fake_run
            try:
                exit_code = module.build_board(repo_root, "esp32s3_devkit", frozen=False)
            finally:
                module.subprocess.run = original_run

            self.assertEqual(exit_code, 1)
```

- [ ] **Step 2: Run the new monorepo artifact tests and verify they fail**

Run: `uv run python -m unittest tests.test_monorepo_ci.MonorepoCiTests.test_build_board_requires_canonical_design_artifact tests.test_monorepo_ci.MonorepoCiTests.test_build_board_fails_if_canonical_design_artifact_is_missing -v`

Expected: FAIL because `build_board()` currently returns the subprocess status without checking for `default.canonical_design.json`.

- [ ] **Step 3: Make board builds verify the canonical snapshot and document the artifact**

```python
# tools/ci/monorepo.py
def canonical_design_artifact(board: Board) -> Path:
    return (
        board.path
        / "build"
        / "builds"
        / "default"
        / "default.canonical_design.json"
    )


def build_board(repo_root: Path, board_name: str, frozen: bool = False) -> int:
    boards = {board.name: board for board in discover_boards(repo_root)}
    board = boards.get(board_name)
    if board is None:
        print(f"Unknown board: {board_name}", file=sys.stderr)
        return 1

    print(f"==> ato build ({board.name})")
    command = ["ato", "build"]
    if frozen:
        command.append("--frozen")
    result = subprocess.run(command, cwd=board.path, check=False)
    if result.returncode != 0:
        return result.returncode

    artifact = canonical_design_artifact(board)
    if not artifact.is_file():
        print(
            f"Missing canonical design artifact: {artifact.relative_to(repo_root)}",
            file=sys.stderr,
        )
        return 1

    return 0
```

```markdown
# docs/architecture/monorepo.md
- `third_party/atopile/` pins the compiler source used for local development and CI.
- `hardware/boards/<board>/build/builds/default/default.canonical_design.json`
  is the phase 1 canonical IR artifact emitted by every successful board build.
```

```markdown
# README.md
Successful `ato build` runs now produce:

- `layouts/default/default.kicad_pcb`
- `build/builds/default/default.canonical_design.json`
```

- [ ] **Step 4: Run the full monorepo verification, including the real board build**

Run: `uv run python -m unittest discover -s tests -v && uv run python tools/ci/monorepo.py --check && uv run python tools/ci/monorepo.py --build-board esp32s3_devkit`

Expected:
- unit tests PASS
- repo check prints `Monorepo structure OK (1 board(s))`
- board build succeeds and leaves `hardware/boards/esp32s3_devkit/build/builds/default/default.canonical_design.json`

- [ ] **Step 5: Commit the fixture verification and CI gate**

```bash
git add tools/ci/monorepo.py tests/test_monorepo_ci.py README.md docs/architecture/monorepo.md
git commit -m "feat(ci): require canonical design snapshots"
```

## Final Verification

- [ ] Run monorepo verification:

```bash
uv run python -m unittest discover -s tests -v
uv run python tools/ci/monorepo.py --check
uv run python tools/ci/monorepo.py --build-board esp32s3_devkit --frozen
```

- [ ] Run child repo verification:

```bash
cd third_party/atopile
uv run pytest \
  test/compiler/test_design_ir_identity.py \
  test/compiler/test_design_ir_artifacts.py \
  test/exporters/test_backend_contracts.py \
  test/exporters/pcb/kicad/test_pcb_transformer.py -v
```

- [ ] Confirm artifacts exist after the board build:

```bash
ls hardware/boards/esp32s3_devkit/build/builds/default
```

Expected entries include:

- `default.canonical_design.json`
- `identity-map.json`
- `managed-objects.json`
- `roundtrip-metadata.json`

## Spec Coverage Check

- Child repo integration: Task 1
- Local and CI usage of the child repo: Task 1 and Task 5
- Versioned `Canonical Design IR`: Task 2
- Stable IDs: Task 2
- IR snapshot on a real board fixture: Task 3 and Task 5
- Backend interface contract: Task 4
- Sidecar schemas for controlled round-trip: Task 4
- KiCad behavior preserved while introducing the new layer: Task 4 and Final Verification

