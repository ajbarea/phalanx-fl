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

## Blocked on an asset: a hero that leaves room for the words

The landing page centres its copy because the artwork is square and symmetric, which
leaves nowhere clean to set a left-aligned column. The legibility fix (2026-09-20)
made the copy readable over it, but a veil dense enough to carry text is also dense
enough to dim the art it covers. The sister sites that read best (periplus, ariadne)
put the copy left and the art right, on deliberately empty ground.

Replacing the art is what unblocks that layout. Regenerating it needs three files,
not one:

| file | current | needed | used by |
|---|---|---|---|
| `docs/assets/phalanx-hero.png` | 1678x1641 | ~2560x1440 | dark scheme, `extra.css:54` |
| `docs/assets/phalanx-hero-light.png` | 734x740 | ~2560x1440 | light scheme, `extra.css:29` |
| `docs/assets/phalanx-og.png` | 1200x630 | 1200x630 | social card, `overrides/main.html:17` |

The aspect ratio is the load-bearing part. `background: ... / contain` on a square
image letterboxes it in a wide viewport, and a square frame cannot hold an empty
left third, so a 1:1 source forecloses the layout no matter what is drawn in it.

### Prompt

> Isometric view of a dark field of many small identical compute nodes arranged in
> loose phalanx formation, each emitting a thin luminous telemetry trace; the traces
> converge rightward and braid into a single ribbon of light. Deep slate-teal base,
> emission only in cyan and violet. The left third of the frame falls off to
> near-black empty space with no detail. Cinematic depth of field, subtle volumetric
> haze. No shields, no crests, no heraldry, no faces, no symmetry, no text.

For the light variant, the same scene on a pale ground: near-white empty left third,
the nodes and traces in the same cyan and violet at higher saturation so they hold
against the paler field.

Two things the prompt is deliberately steering away from. The current art reads as
heraldry rather than as *many clients, telemetry, aggregation*, which is what the
system does; and its symmetry is what forces the centred type. The palette stays on
the existing `--intefl-teal` / `--intefl-purple` tokens so the page does not have to
be recoloured around a new image.

### The OG card is branded for the wrong project

`docs/assets/phalanx-og.png` reads **InteFL — Federated learning, under fire —
10 strategies · 6 attacks · Byzantine-robust**, over a shield wall, with
`github.com/ajbarea/phalanx-fl` beneath it. So every unfurl of a Phalanx link in
Slack, LinkedIn or X has been showing IntelliFL's name and IntelliFL's claims. Those
are deliberately separate projects, and none of those three figures describes this
one, whose line is *federated learning on the latest Flower, with
OpenTelemetry-native observability*.

Burning the wordmark and tagline into the card is correct and stays — the text a
platform renders beside an unfurl varies, and several render none, so a card that
carries its own is the 2026 convention (`research(2026-09)`). What has to change is
which project it names.

Text renders unreliably in an image model, so the card is two steps: generate the
field, then set the type over it.

**Art, 1200x630:**

> Isometric dark field, a shallow arc of twelve to sixteen large identical compute
> nodes seen from slightly above, each emitting one thin luminous telemetry trace;
> the traces rise and converge toward a single bright point off the upper right.
> Deep slate-teal base, emission only in cyan and violet. Lower two thirds carry the
> nodes; upper third falls off to near-black for type. Cinematic depth of field,
> subtle volumetric haze. No shields, no crests, no heraldry, no faces, no text.

Fewer and larger nodes than the hero, because the card renders around 500px wide in
a feed and the hero's many-small-nodes field turns to mush at that size. One focal
point, high contrast, and the same cyan/violet emission so the card and the site
read as one thing.

**Type, composited after:**

- `Phalanx` as the wordmark, in the site's own face, optically centred in the upper
  third
- `Federated learning on the latest Flower, with OpenTelemetry-native observability`
  beneath it, one line if it fits at legible size, otherwise two
- `github.com/ajbarea/phalanx-fl` small, lower right
- Keep all of it inside a centre safe area, roughly 60px in from every edge, since
  platforms crop the margins differently

Export PNG, not JPEG: this is graphics with text, where JPEG ringing shows on the
letterforms.

### When the asset lands

`extra.css` needs the hero switched from `center 48px / contain` to a right-anchored
`cover`, the flex container from `align-items: center` to `flex-start`, and the copy
column capped near `min(34rem, 42%)` with a scrim measured from that column's edge
rather than from a share of the viewport — the mistake that made ariadne's hero
unreadable, fixed there in ariadne#46.

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
