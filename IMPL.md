# Phalanx — Active Implementation Log

Rolling notes on in-flight work. See `ROADMAP.md` for the stable plan.
When a roadmap item ships, collapse its notes here into a one-liner under
ROADMAP's "Recently shipped" and clear the relevant block below.

---

## Current focus

_No in-flight work._ The corpus and measurement apparatus moved to
[`ajbarea/sphragis`](https://github.com/ajbarea/sphragis) on 2026-09-13; see ROADMAP's
`corpus` section for why. Open roadmap items here are the v2 observability and v3 breadth
lines.

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
