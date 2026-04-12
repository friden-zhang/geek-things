# Atopile EasyEDA Pro Phase 2 — Native Project Export

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a **real EasyEDA Pro (嘉立创 EDA 专业版) local project** that opens in the desktop client, emitted from the compiler fork’s **Canonical Design IR** (plus any required IR extensions), with **versioned sidecars** aligned to the Phase 1 round-trip contracts.

**Architecture:** Treat EasyEDA Pro as a **native serializer backend** under `third_party/atopile/src/atopile/backends/`, mirroring the KiCad adapter pattern but writing **tool-owned project files** (not only JSON sidecars). Start with a **format spike** using official samples or hand-saved minimal projects as **golden fixtures**, then implement a **writer** that maps `CanonicalDesign` → on-disk layout. Run the backend from a **new optional build step** so default `ato build` stays KiCad-first until the exporter is stable; optionally gate monorepo CI on a board that opts in.

**Tech Stack:** Python 3.x (atopile), existing `CanonicalDesign` + `design_to_json` / `design_from_json`, zip/json/binary handling as determined by the format spike, pytest.

**Depends on:** Phase 1 foundation ([design spec](../specs/2026-04-10-atopile-easyeda-pro-foundation-design.md), [foundation plan](./2026-04-10-atopile-easyeda-pro-foundation.md)).

**Repository layout (from foundation spec):** board-local EasyEDA assets live at  
`hardware/boards/<board>/layouts/easyeda_pro/default/` (separate from KiCad’s `layouts/default/`).

---

## Preconditions (read before coding)

1. **Canonical IR is still minimal** (`third_party/atopile/src/atopile/model/design_ir/from_build.py` → `minimal_phase1_design`). A useful schematic/PCB export **requires extending** `CanonicalDesign` population from the real build graph (or an intermediate projection from existing KiCad export internals — avoid duplicating semantics; prefer **one** path into IR).
2. **Lossy KiCad import** into EasyEDA Pro is **out of scope** as the primary deliverable (foundation spec); Phase 2 is **native** emission.
3. **Backward compatibility:** extend `schema_version` / serializer versioning when IR fields grow; keep **stable IDs** as the bridge for future round-trip (Phase 3).

---

## File map (planned)

| Area | Path (under `third_party/atopile/` unless noted) |
|------|-----------------------------------------------------|
| Backend stub (replace) | `src/atopile/backends/easyeda_pro.py` → thin facade or re-export |
| Native writer package | `src/atopile/backends/easyeda_pro/` (`__init__.py`, `writer.py`, `package_layout.py`, `ids.py`, …) |
| IR enrichment | `src/atopile/model/design_ir/schema.py`, `from_build.py`, tests |
| Build wiring | `src/atopile/build_steps.py`, default target graph (optional step) |
| Contracts / tests | `test/exporters/test_easyeda_pro_*.py`, `test/resources/easyeda_pro/` fixtures |
| Monorepo CI (optional) | `tools/ci/monorepo.py`, `tests/test_monorepo_ci.py`, board `ato.yaml` flag if introduced |

---

### Task 1: Format spike and golden fixtures

**Files:**

- Create: `test/resources/easyeda_pro/README.md` (how fixtures were produced)
- Create: `test/resources/easyeda_pro/minimal_project/` (checked-in **minimal** project tree or `.epro` as appropriate)

- [ ] **Step 1:** In EasyEDA Pro, create **empty** project (one sheet, default PCB), save/export per [official import/export docs](https://prodocs.easyeda.com/en/faq/import-export/).
- [ ] **Step 2:** Document **on-disk structure**: single `.epro` vs folder vs zip; list **required** files and root metadata.
- [ ] **Step 3:** Check in a **minimal fixture** and a short Python test that only asserts structural invariants (paths exist, parseable JSON where expected, stable sizes) — not full semantic equality.

**Verification:** `pytest` passes; fixture reproducibility documented.

---

### Task 2: Extend backend contract for native emission

**Files:**

- Modify: `src/atopile/backends/base.py` — add optional protocol or a second method, e.g. `emit_native_project(...) -> BackendProjectArtifacts`, **without** breaking `KicadBackend` callers.
- Modify: `src/atopile/backends/easyeda_pro.py` — set `supports_native_emit = True` once implemented; keep `contract_version` bumped if wire format changes.
- Modify: `test/exporters/test_backend_contracts.py` — assert new contract surface.

- [ ] **Step 1:** Decide: **single method** on `BuildBackend` vs `NativeEmittingBackend(Protocol)` subclass — prefer smallest change that keeps type hints honest.
- [ ] **Step 2:** Implement no-op or “empty project” implementation returning declared `managed_files` paths.
- [ ] **Step 3:** Tests for protocol compliance and artifact tuple non-empty for EasyEDA backend.

**Verification:** `pytest test/exporters/test_backend_contracts.py` passes.

---

### Task 3: EasyEDA Pro project writer (shell)

**Files:**

- Create: `src/atopile/backends/easyeda_pro/writer.py` — build project bytes/tree from a `CanonicalDesign` + output directory.
- Create: `src/atopile/backends/easyeda_pro/__init__.py`

- [ ] **Step 1:** Writer reproduces **golden minimal** layout byte-for-byte or field-normalized (document normalization: timestamps, UUIDs).
- [ ] **Step 2:** Map **project display name** from `config.build` / `LogicalDesign.root_module` where applicable.
- [ ] **Step 3:** Unit test: write to `tmp_path`, open key files, assert schema-ish keys present.

**Verification:** dedicated `pytest` module green; no network in tests.

---

### Task 4: Sidecars + backend projection metadata for EasyEDA

**Files:**

- Modify: `src/atopile/backends/easyeda_pro.py` (or package) — implement `emit_sidecars` **without** `NotImplementedError`: reuse `write_sidecar_bundle` from `sidecar.py` like `KicadBackend`, with EasyEDA-specific `RoundTripMetadata` / `ManagedObjects` policy (mirror KiCad until product defines finer rules).
- Modify: `src/atopile/model/design_ir/schema.py` — allow `BackendProjectionMetadata` to carry **placeholder** EasyEDA UUID map entries when the writer allocates tool IDs.

- [ ] **Step 1:** Emit `identity-map.json` mapping **canonical IDs → EasyEDA object IDs** for every object the writer creates (start with project + sheet roots).
- [ ] **Step 2:** Round-trip metadata `policy_version` stays aligned with Phase 1 tests.

**Verification:** `test/exporters/test_backend_contracts.py` extended; new golden for sidecar bundle next to project root.

---

### Task 5: Enrich `CanonicalDesign` from the real build

**Files:**

- Modify: `src/atopile/model/design_ir/from_build.py` — replace / augment `minimal_phase1_design` using `BuildStepContext` / `app` graph (same patterns as other build steps that walk `ctx.require_app()`).
- Modify: `src/atopile/model/design_ir/schema.py` — add **backward-compatible** optional fields (prefer additive tuples / new dataclasses with defaults).
- Create: `test/compiler/test_design_ir_from_build.py`

- [ ] **Step 1:** Populate **logical nets** and **instance identifiers** needed for schematic/PCB objects (incremental: start with net names + instance stable IDs from existing `design_ir/identity.py`).
- [ ] **Step 2:** Populate **schematic** `symbol_refs` / sheet structure from compiler data if available; otherwise document “empty sheet” until graph exposes symbols.
- [ ] **Step 3:** Populate **physical** outline / placement when available from layout pipeline without reading KiCad files back (avoid round-tripping through KiCad).

**Verification:** `esp32s3_devkit` build produces richer JSON; **stable ID** tests from Phase 1 still pass or are intentionally version-bumped.

---

### Task 6: Build step and output path convention

**Files:**

- Modify: `src/atopile/build_steps.py` — register `easyeda-pro-export` (name TBD) depending on `generate_canonical_design` (and possibly `build_design`).
- Modify: default `all` / main target: keep **opt-in** (`ato build -t easyeda-pro` or `ato.yaml` feature flag) so CI and users are not broken mid-development.

- [ ] **Step 1:** Resolve output root to  
  `<board>/layouts/easyeda_pro/default/`  
  (mirror KiCad’s `layouts/default/` convention from [monorepo architecture](../../architecture/monorepo.md)).
- [ ] **Step 2:** Idempotent writes: same build → same bytes or documented volatile fields stripped in tests.
- [ ] **Step 3:** Document CLI in fork `README` or atopile docs snippet.

**Verification:** Local `ato build -t …` produces openable project path; monorepo default build unchanged unless flag set.

---

### Task 7: Monorepo integration (optional CI gate)

**Files (geek-things root):**

- Modify: `tools/ci/monorepo.py` — optional `--require-easyeda-pro-artifact` or per-board `ato.yaml` key.
- Modify: `tests/test_monorepo_ci.py` — one test behind the same flag.

- [ ] **Step 1:** Only **one** reference board enables the gate after manual “opens in EasyEDA Pro” signoff.
- [ ] **Step 2:** README note for contributors.

**Verification:** default CI green; optional job proves artifact.

---

## Acceptance criteria (Phase 2 “done”)

1. **Open in EasyEDA Pro:** Double-open (or official “open project”) succeeds for the reference board output **without** manual file repair beyond documented limitations.
2. **Determinism:** Repeated `ato build` yields **bit-identical** output or documented normalized diff (no random UUIDs without capture in sidecar).
3. **Contracts:** `identity-map.json`, `managed-objects.json`, `roundtrip-metadata.json` present beside the project root; schemas parse under existing tests.
4. **Isolation:** KiCad default workflow and Phase 1 canonical artifact checks remain valid when EasyEDA export is **disabled**.

---

## Follow-on (Phase 3 preview — not in this plan)

- Parse `.epro` / project folder back into **projection diff** vs `CanonicalDesign`.
- `ato sync --from easyeda-pro` classification (`safe-apply` / `preserve-local-only` / `conflict-reject`).

---

## Risks

| Risk | Mitigation |
|------|------------|
| Proprietary / undocumented binary chunks | Spike first; store **versioned** fixture; minimize undocumented surface; escalate to “supported subset” doc. |
| IR too shallow for real PCBs | Task 5 incremental enrichment; ship **shell** then **content** milestones. |
| Scope creep into full schematic parity | Time-box Phase 2 to **one** reference board + explicit non-goals in PR description. |
