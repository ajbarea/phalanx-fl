# Phalanx — Active Implementation Log

Rolling notes on in-flight work. See `ROADMAP.md` for the stable plan.
When a roadmap item ships, collapse its notes here into a one-liner under
ROADMAP's "Recently shipped" and clear the relevant block below.

---

## Current focus

### Gerrit review corpus, plan A (spec #86, plan #88)

Building the corpus the RQ1 feasibility gate runs on. Seven standard-library modules
under `phalanx/corpus/`, each one pipeline stage, each a pure function over data plus a
thin IO shell.

**Design decisions already pinned** (spec, merged): identity stripping runs inline in
`fetch` before anything is persisted; dedup is three stages; four time-ordered windows
grouped by change-id; the confirmatory test window is defined and hashed now but fetched
only after in-principle acceptance; exact match binds the pass rule with normalized EM and
edit similarity reported alongside; LLM-as-judge excluded from both.

**Order** (plan A): `scrub` → `manifest` → `gerrit` → `examples` → `dedup` → `split` → `cli`.
Each task is a failing test, a minimal implementation, and a commit.

**The HSRO determination does not block this.** `fetch`'s transport is a
`Callable[[str], tuple[int, dict, str]]` seam, so every test runs offline and all seven
tasks are completable before the determination lands. Only the stage bodies (plan A2) wait
on it. Draft request: `corpus/HSRO.md`.

**One recorded spec deviation.** Dedup stage 3 is corpus-wide shingle frequency, not a
suffix array: a linear-time suffix array needs a C extension and a pure-Python one is
quadratic over the concatenated corpus. Plan A task 5 amends the spec text.

**Deadline setting the order:** MSR 2027 Stage 1, 2026-11-20. Checklist in
`papers/org-fingerprint/STAGE1-SKELETON.md`.

---

## Open bugs & findings

### Dependabot: 5 open alerts are upstream pins in flwr 1.36.0 (2026-09-13)

Not repo drift, and not fixable here. 4 alerts against `cryptography` 46.0.7 and 1
against `ray` 2.55.1, both transitive through `flwr[simulation]`.

| Package | Locked | Needed to clear | On PyPI |
|---|---|---|---|
| `cryptography` | 46.0.7 | >= 50.0.0 | 50.0.1 |
| `ray` | 2.55.1 | >= 2.56.0 | 2.58.0 |

`flwr` 1.36.0, the newest release, constrains both: `cryptography<47.0.0,>=46.0.7` and
`ray==2.55.1` for the `simulation` extra. The `ray` pin is a hard equality.
`uv lock --upgrade-package cryptography --upgrade-package ray` resolves to the same
versions, as expected.

Neither advisory looks reachable from this app. The `ray` one is arbitrary code execution
via `ray.data.read_webdataset`'s default decoder, and Phalanx uses Ray only as the Flower
simulation backend, never `ray.data`. The `cryptography` ones are TLS path-building,
wildcard DNS in `permittedSubtrees`, PKCS#7 `EnvelopedData` decryption and a bundled
OpenSSL; Phalanx runs local simulations and neither terminates TLS nor decrypts PKCS#7.

Clears when a `flwr` release relaxes the pins. Not doing: a `[tool.uv]
override-dependencies` block forcing versions past a framework's hard equality pin, which
trades unreachable advisories for a real chance of breaking simulation.
