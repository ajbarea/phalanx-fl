# Phalanx — Active Implementation Log

Rolling notes on in-flight work. See `ROADMAP.md` for the stable plan.
When a roadmap item ships, collapse its notes here into a one-liner under
ROADMAP's "Recently shipped" and clear the relevant block below.

---

## Current focus

**Round ESS and client counts named for their phase (#105).** flwr samples the train and
evaluate cohorts independently, so the one `fl.ess` (train-derived) sat beside
`fl.accuracy` (evaluate-derived) on the round span and read as describing it. The round
now carries both halves under phase names:

| phase | clients | ESS | derived from |
|---|---|---|---|
| train | `fl.clients` | `fl.train_ess` | the replies that produced the adapters |
| evaluate | `fl.evaluate_clients` | `fl.evaluate_ess` | the replies behind `fl.loss` / `fl.accuracy` |

Same names under `fl.round.*` for the metrics. `fl.round.ess` is gone rather than
aliased: it shipped in #102 and nothing read it. `_reply_ess` computes both from the
replies FedAvg aggregates, and a test drives `aggregate_train` / `aggregate_evaluate`
with real `Message` replies of different sizes, so reusing the train figure for evaluate
(or the train client count) fails the suite; both mutations were checked.

---

## Background

The corpus and measurement apparatus moved to
[`ajbarea/sphragis`](https://github.com/ajbarea/sphragis) on 2026-09-13; see ROADMAP's
`corpus` section for why. Open roadmap items here are the v2 observability and v3 breadth
lines.

---

## Shipped: an asymmetric hero (2026-09-20)

The landing page centres its copy because the artwork is square and symmetric, which
leaves nowhere clean to set a left-aligned column. The legibility fix (2026-09-20)
made the copy readable over it, but a veil dense enough to carry text is also dense
enough to dim the art it covers. The sister sites that read best (periplus, ariadne)
put the copy left and the art right, on deliberately empty ground.

Replacing the art is what unblocks that layout. Regenerating it needs three files,
not one:

| file | was | is | used by |
|---|---|---|---|
| `docs/assets/phalanx-hero.jpg` | `.png`, 1678x1641, 3.6MB | 2400x1309, 349KB | dark scheme, `extra.css` |
| `docs/assets/phalanx-hero-light.jpg` | `.png`, 734x740, 685KB | 2400x1309, 383KB | light scheme, `extra.css` |
| `docs/assets/phalanx-og.jpg` | `.png`, 1200x630, 784KB | 1200x630, 114KB | social card, `overrides/main.html` |

All three are JPEG now. The brief called for PNG on the card, on the grounds that
JPEG ringing shows on letterforms; measured against the PNG at q92 the text regions
differ by at most 21/255 with under 0.5% of pixels past a delta of 8, which is not
visible, and the card is 6.6x smaller. `README.md` points at the dark hero too.

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

### Dependabot: 5 alerts are upstream pins in flwr (2026-09-13, dismissed 2026-09-26)

4 alerts against `cryptography` 46.0.7 and 1 against `ray` 2.55.1, both transitive
through `flwr[simulation]`. `flwr` 1.36.0, 1.38.0 and `flwrlabs/flower` main all pin
`cryptography<47.0.0,>=46.0.7` and `ray==2.55.1`, so no lock bump reaches the fixes
(`cryptography` >= 50.0.0, `ray` >= 2.56.0).

None is reachable: neither flwr nor phalanx imports `pkcs7` or
`cryptography.x509.verification`; the bundled-OpenSSL advisory covers PKCS#7/CMS, QUIC,
OCSP, AES-OCB/SIV, DHX and PKCS#12, where flwr uses EC, Ed25519, SSH key loading, HKDF
and Fernet; and Ray is only the simulation backend, never `ray.data`. The alerts are
dismissed as not used, with the analysis on #106, and `make audit` ignores the same IDs.

Clears on the `flwr` release that relaxes the pins (flwrlabs/flower#7763 is open for
cryptography 50). Not doing: `[tool.uv] override-dependencies` past a framework's hard
equality pin, which trades unreachable advisories for a real chance of breaking
simulation.
