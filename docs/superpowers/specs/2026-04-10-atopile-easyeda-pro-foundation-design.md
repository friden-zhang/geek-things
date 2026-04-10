# Design: Foundation For `atopile` EasyEDA Pro Support

Date: 2026-04-10
Status: Approved for implementation planning

## Summary

`geek-things` currently consumes `atopile==0.15.3` as an external package and
checks in KiCad PCB layout sources for board projects. The long-term goal is to
extend that workflow so the same `.ato` sources can drive both KiCad and
EasyEDA Pro, including schematic and PCB generation, while supporting
controlled round-trip from EasyEDA Pro back into compiler-recognized edits.

This spec covers the first sub-project only. It defines the foundation needed
to make that long-term goal maintainable:

- integrate the forked `atopile` repository as a child repo in this monorepo
- move compiler ownership for EDA-neutral design semantics into the fork
- introduce a versioned `Canonical Design IR`
- introduce stable, tool-agnostic object identity
- define backend and round-trip contracts that later EasyEDA Pro work must obey

This spec does **not** implement the full EasyEDA Pro native backend or full
round-trip behavior. It creates the compiler and repository structure required
to build those features without duplicating compiler logic in this monorepo.

## Context

- This repository is a hardware design monorepo built around `atopile`.
- Current checked-in board assets are centered on KiCad PCB layout sources, for
  example `hardware/boards/esp32s3_devkit/layouts/default/default.kicad_pcb`.
- The repository currently depends on the published `atopile` package rather
  than a checked-in source fork.
- The target new EDA is EasyEDA Pro / JLCEDA Pro, not EasyEDA Standard.
- EasyEDA Pro can import KiCad projects and stores local projects as `.epro` or
  `.zip`, but the official converter path is lossy and explicitly requires
  manual review after conversion. That makes it useful for validation, but not
  an acceptable long-term round-trip foundation.

References:

- [`friden-zhang/atopile` fork](https://github.com/friden-zhang/atopile.git)
- [EasyEDA Pro import/export FAQ](https://prodocs.easyeda.com/en/faq/import-export/)
- [EasyEDA Pro format converter](https://prodocs.easyeda.com/en/import-export/easyeda-pro-format-converter/)

## Product Goal

The long-term product goal is:

1. compile `.ato` designs into a single canonical model
2. emit both KiCad and EasyEDA Pro projects from that canonical model
3. keep object identity stable across rebuilds and backend projections
4. support controlled, explicit synchronization of a safe subset of EasyEDA Pro
   edits back into compiler-recognized design state

The foundation described here is successful if it makes that future possible
without treating EasyEDA Pro support as a pile of monorepo-local adapter
scripts.

## Scope

This spec covers the following phase 1 work:

1. Add the forked `atopile` repository to this monorepo as a child repo.
2. Switch local development and CI to use the child repo for compiler work.
3. Define and implement a versioned `Canonical Design IR` inside the fork.
4. Define and implement stable, backend-independent IDs for canonical design
   objects.
5. Define backend interfaces that both KiCad and EasyEDA Pro emitters must use.
6. Define sidecar and change-classification contracts for future controlled
   round-trip.
7. Prove the foundation on at least one real board fixture in this monorepo.

## Out Of Scope

The following items are explicitly out of scope for this phase 1 spec:

- full native EasyEDA Pro project emission
- full schematic generation for all current boards
- any promise of arbitrary two-way editing between EasyEDA Pro and `.ato`
- automatic absorption of local EDA edits during normal `ato build`
- replacing KiCad as the existing working backend
- complete visual parity across KiCad and EasyEDA Pro
- production signoff of EasyEDA Pro output for manufacturing

These items belong to later sub-projects and are only constrained here at the
interface level.

## Architecture Decisions

### 1. Child Repo Integration

The monorepo will integrate the forked `atopile` repository as a **git
submodule** at:

`third_party/atopile/`

This submodule will point at:

`https://github.com/friden-zhang/atopile.git`

Rationale:

- `atopile` remains an independently versioned compiler codebase
- the monorepo can pin exact compiler commits for reproducible hardware builds
- the fork can evolve on its own branch history without turning this monorepo
  into the compiler's primary source repository
- CI can verify both integration and real-board behavior against pinned commits

Phase 1 must make local development prefer the child repo over the published
PyPI package when working on compiler internals.

### 2. Compiler Ownership Boundary

Compiler-owned responsibilities live in the fork:

- `.ato` compilation and semantic analysis
- canonical design modeling
- stable identity generation
- backend projection interfaces
- future EasyEDA Pro parsing and projection logic

Monorepo-owned responsibilities stay in `geek-things`:

- board source projects and checked-in layout assets
- integration fixtures and real-board regression tests
- CI orchestration for monorepo builds
- repository conventions and release flow for actual hardware projects

This split prevents the monorepo from becoming a shadow compiler.

### 3. Canonical Design IR

The fork will define a versioned `Canonical Design IR` with four layers:

#### `LogicalDesign`

Contains tool-independent electrical semantics:

- module and instance hierarchy
- ports and connectivity
- logical nets
- selected parts
- normalized attributes
- constraint results relevant to downstream EDA generation

#### `SchematicIntent`

Contains tool-independent schematic presentation intent:

- sheets or pages
- symbol projections of logical instances
- ports, power symbols, net labels, hierarchical blocks
- text objects that belong to design intent
- page-local placement and orientation data

#### `PhysicalPcbIntent`

Contains tool-independent board implementation intent:

- footprint projections of logical instances
- pads and net attachment
- board outline
- mounting holes and other mechanical anchors
- keepouts, rule regions, and placement metadata
- component placement and orientation

#### `BackendProjectionMetadata`

Contains backend-specific projection state that must not leak into the other
layers:

- KiCad UUIDs
- EasyEDA Pro object IDs
- serializer version metadata
- import/export bookkeeping needed for later round-trip

The IR must be versioned so future backend work can evolve schemas without
guessing which serializer or identity rules produced an artifact.

### 4. Stable Identity

Every canonical object that may participate in diffing, backend projection, or
round-trip must carry a stable canonical ID.

Stable IDs must be:

- deterministic for the same semantic source object
- independent of output ordering
- independent of backend-specific file formats
- resilient to non-semantic rebuild noise
- versioned so identity rules can evolve deliberately

The ID source should come from semantic origin, not serializer order. Examples:

- logical instance ID: normalized design path + role
- logical net ID: normalized connectivity origin
- schematic symbol ID: logical instance ID + schematic projection role
- PCB footprint ID: logical instance ID + physical projection role

Backend serializers may add their own object IDs, but those IDs are only
projection metadata and never replace canonical identity.

### 5. Backend Interface Contract

All EDA outputs must consume the same canonical IR. Backends must not re-run
their own semantic interpretation of `.ato`.

The backend contract is:

1. `.ato` compiles into `Canonical Design IR`
2. a backend projector converts IR into backend-specific projection objects
3. a serializer writes target files plus versioned sidecar metadata

At minimum, the fork must expose backend interfaces for:

- KiCad emission
- EasyEDA Pro emission
- future EasyEDA Pro parsing for synchronization

Phase 1 only needs to make these contracts real and testable. It does not need
to deliver a complete EasyEDA Pro serializer yet.

### 6. Controlled Round-Trip Policy

Round-trip will be explicit, not implicit. The long-term command surface is:

```bash
ato build --target kicad
ato build --target easyeda-pro
ato build --target all
ato sync --from easyeda-pro
```

Round-trip edits must be classified into three buckets:

- `safe-apply`: edits that can be written back into compiler-recognized state
- `preserve-local-only`: edits that stay in the EDA project only
- `conflict-reject`: edits that must be rejected and redirected to source

Phase 1 must define the policy and metadata needed for later synchronization,
including sidecar schemas such as:

- `identity-map.json`
- `managed-objects.json`
- `roundtrip-metadata.json`

## Repository And Output Layout

Phase 1 repository layout changes:

- `third_party/atopile/`: git submodule for the compiler fork
- `docs/superpowers/specs/`: design and planning documents for this workflow

Planned board output layout for later phases:

- `hardware/boards/<board>/layouts/default/`: KiCad-managed assets
- `hardware/boards/<board>/layouts/easyeda_pro/default/`: EasyEDA Pro assets

This keeps both EDA targets as first-class repository artifacts and matches the
existing checked-in layout model.

## Phase 1 Acceptance Criteria

Phase 1 is complete when all of the following are true:

1. The monorepo can fetch, pin, and initialize `third_party/atopile/` in CI and
   local development.
2. Local development can run the monorepo against the child repo instead of the
   published `atopile` package when compiler changes are being made.
3. At least one real board fixture in this repository, starting with
   `esp32s3_devkit`, can compile into a versioned canonical IR snapshot.
4. The canonical IR contains logical, schematic, and physical sections even if
   later backends do not yet consume every field.
5. Stable IDs remain unchanged across no-op rebuilds and non-semantic source
   reorderings.
6. Existing KiCad-oriented build behavior remains available and validated.
7. Backend interfaces and round-trip sidecar schemas exist as versioned
   contracts with automated tests.

## Follow-On Phases

This foundation is intended to unlock the next three sub-projects:

1. complete EasyEDA Pro native project emission for schematic and PCB
2. add sidecar-backed import and diff of EasyEDA Pro projects
3. enable controlled synchronization of approved edit categories back into
   compiler-recognized design state

Those follow-on phases must use the IR, ID, and metadata contracts defined in
phase 1 rather than introducing monorepo-local shortcuts.

## Test Strategy

Phase 1 test coverage should be split into four groups:

### Unit Tests

- canonical IR schema validation
- stable ID determinism and versioning behavior
- serializer and projector contract validation

### Golden Tests

- canonical IR snapshots for real fixture boards
- no-op rebuild stability checks for IDs and canonical ordering

### Integration Tests

- monorepo build against child repo checkout
- preservation of current KiCad build behavior

### Forward-Compatibility Tests

- sidecar schema generation and parsing
- classification fixtures for `safe-apply`, `preserve-local-only`, and
  `conflict-reject`

Phase 1 does not need full EasyEDA Pro parser coverage, but it must define and
test the contracts that later parser work will consume.

## Risks And Mitigations

### Risk: The foundation scope quietly expands into full backend work

Mitigation:

- keep this spec limited to child repo integration, IR, identity, and contracts
- treat native EasyEDA Pro emission as a follow-on phase with its own plan

### Risk: Tool-specific fields leak into canonical IR

Mitigation:

- keep backend projection metadata isolated from logical, schematic, and
  physical intent layers
- reject designs that require backend-specific core semantics

### Risk: Round-trip promises become unrealistic

Mitigation:

- commit now to controlled round-trip only
- require explicit edit classification
- never silently absorb backend edits during normal builds

### Risk: The fork drifts from monorepo validation needs

Mitigation:

- pin the submodule in the monorepo
- run real-board regression tests from this repository against the pinned fork

## Final Decision

Proceed with a phase 1 foundation project that integrates the forked
`atopile` repo as a git submodule, establishes a canonical IR plus stable
identity inside the fork, preserves KiCad as the baseline backend, and defines
the contracts required for later EasyEDA Pro native output and controlled
round-trip.
