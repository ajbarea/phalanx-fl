# Banking77 pilot

Four runs of the label-flip setup from `../financial_poisoning/` on `gtfintechlab/banking77`,
an intent-classification set with 77 classes. They check whether the attack and the defence
behave on a many-class task before a sweep is built for it:

| run | rule | attack |
| --- | --- | --- |
| `clean__fedavg__s0` | FedAvg | none |
| `flip__fedavg__s0` | FedAvg | label flip |
| `flip-boosted__fedavg__s0` | FedAvg | label flip, boosted update |
| `flip-boosted__multikrum__s0` | Multi-Krum | label flip, boosted update |

Each run uses one seed, so there is no spread to compare against. The runs show whether the
pipeline works on this dataset; they cannot separate a rule's effect from seed noise.

## Provenance

Every manifest in `results/runs/` records commit `1a209f0a5` with a clean tree: tag
`financial-poisoning-2026-09-24`, the code behind the Financial PhraseBank sweep. Each manifest
holds the run's full `run_config` and its per-round server-side scores under `heldout_metrics`.
A one-off driver, not kept, launched the runs. The manifests do not record the federation
config; `num-nodes-to-select = 11` with `num-malicious = 1` matches the sweep's 12 supernodes.

## Reproduce

Check out the tag, then pass a manifest's `run_config` to `flwr run` as `key=value` pairs,
quoting strings as `sweep.py` does:

```bash
git checkout financial-poisoning-2026-09-24
uv run --no-sync flwr run . local --stream \
  --federation-config "num-supernodes=12 client-resources-num-cpus=1 client-resources-num-gpus=0.34" \
  --run-config "<the manifest's run_config>"
```

The GPU caveats in `../financial_poisoning/README.md` (batch-count weighting, nondeterministic
CUDA kernels, one partition across seeds) apply to these runs too.
