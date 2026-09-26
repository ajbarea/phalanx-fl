# Global evaluation: IID vs Dirichlet arms (2026-09-26)

Run manifests (`phalanx/provenance.py`) for three draws of each partitioner, produced at
commit `fdb7ae862` (tag `global-eval-arms-2026-09-26`) with the default run config
(3 rounds, `dirichlet-alpha = 0.5`, `fraction-train = fraction-evaluate = 0.1`,
`global-eval-size = 0`, i.e. all 25,000 rows of IMDB's `test` split) and the Makefile's
federation (5 supernodes, 2 CPUs each, CPU torch). Flower samples clients without a seed,
so draws differ only in which clients each round trains and evaluates on; the initial
adapters are seeded and identical.

Each draw, from the worktree root, with a SuperLink started from the same checkout:

```bash
uv run --no-active --extra hf --extra torch flwr run . local --stream \
  --federation-config "num-supernodes=5 client-resources-num-cpus=2 client-resources-num-gpus=0.0" \
  --run-config 'partitioner="iid"'          # or partitioner="dirichlet"
```

`global_metrics` is the aggregated adapters on the test split, from round 0 (the initial
adapters); `metrics` is the clients' federated evaluation on their own holdouts.
