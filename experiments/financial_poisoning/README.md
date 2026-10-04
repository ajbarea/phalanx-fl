# Financial PhraseBank poisoning

Twelve simulated banks jointly fine-tune a news-sentiment classifier. One of them
relabels negative financial news as positive in its own training data. Does that one
bank move the shared model, and which aggregation rules stop it?

## Setup

| | |
|---|---|
| Data | [`atrost/financial_phrasebank`](https://huggingface.co/datasets/atrost/financial_phrasebank): the `sentences_50agree` subset of Financial PhraseBank ([Malo et al., 2014](https://arxiv.org/abs/1307.5336)) in the FinBERT 64/16/20 split ([Araci, 2019](https://arxiv.org/abs/1908.10063)); labels negative / neutral / positive |
| Banks | 12, IID partition of the 3,100-sentence train split |
| Model | `distilbert-base-uncased` + LoRA (r=8 on `q_lin`, `v_lin`), learning rate 5e-4, one local epoch per round |
| Rounds | 20; the attacker is honest in rounds 1-5 and attacks from round 6 |
| Attacker | bank 0 relabels every negative training sentence as positive (`flip`); in `flip-boosted` it also scales its update by 12, the model-replacement move of [Bagdasaryan et al., 2020](https://arxiv.org/abs/1807.00459) |
| Rules | FedAvg (no defense), Krum, Multi-Krum, Trimmed-Mean, Median, Bulyan (Flower built-ins); rules that take an attacker count are told f = 1 |
| Scored on | the 970-sentence test split no bank trains on, by the server, every round |
| Seeds | 0, 1, 2 |

**Attack success** is the share of truly negative test sentences the global model
labels positive. The `clean` scenario gives its natural rate. **Outlier rank** is
where the attacker's update sits by distance from the coordinate-wise median of all
twelve (1 = farthest), a proxy for whether an inspector could single it out. The
summary reports the share of attack rounds where it was farthest, and, as a control,
its median rank in rounds 1-5, while it was still honest.

## Reproduce

Needs a CUDA torch in the project venv (the sweep gives each client a third of an 8 GB GPU):

```bash
uv sync --all-extras
uv pip install --reinstall torch==2.13.0 torchvision==0.28.0 \
  --index-url https://download.pytorch.org/whl/cu129
uv run --no-sync python experiments/financial_poisoning/sweep.py
uv run --no-sync python experiments/financial_poisoning/summarize.py
```

`sweep.py` copies each run's provenance manifest to `results/` and skips cells already
there. `summarize.py` writes `results/summary.md` and `results/summary.csv` from those
manifests; every figure quoted anywhere comes from them.

## Files

| path | contents |
|---|---|
| `results/summary.md` | per scenario and rule: final accuracy, final attack success, mean attack success over the attack rounds (median [min, max] over seeds), share of attack rounds the attacker was farthest, its median rank while honest |
| `results/summary.csv` | the same, one numeric column per median / min / max |
| `results/summary.tex` | the same as a booktabs table that fits one text column (`\input` it inside a `table`) |
| `results/rounds.csv` | every run, every round: accuracy, loss, attack success, attacker outlier rank |
| `results/figures/attack_success_by_round.{png,pdf}` | attack success per round under FedAvg, one line per scenario; the legend gives each scenario's mean over the attack rounds |
| `results/figures/by_rule.{png,pdf}` | attack success and accuracy for every rule and scenario, averaged over the attack rounds (the boosted attack swings round to round, so the final round alone can land on a peak or a trough) |
| `results/runs/<scenario>__<rule>__s<seed>.json` | one provenance manifest per run: git commit (and whether the tree was dirty), package versions, full run config, and per-round `heldout_metrics` and `attacker_outlier_rank` (current code writes `global_metrics`; `summarize.py` reads either) |

In a manifest, `metrics` (client-side evaluation) is empty because the sweep turns client
evaluation off; all scoring is the server's, in `heldout_metrics` (`global_metrics` from current
code), keyed by round (round 0 is the untrained model).

## Known limitations

- **The committed runs come from tag `financial-poisoning-2026-09-24`** (commit `1a209f0a5`,
  flwr 1.36), the commit every manifest records. Check out that tag to replay them. Running
  `sweep.py` on current code is a new experiment: it differs in the ways below.
- **FedAvg weighted by batch count.** Current code weights by sample count. Here every bank
  holds 206 or 207 training sentences, 7 batches each, so the two weightings differ by at most
  0.027 percentage points of any bank's share.
- **Every seed used the same bank partition.** The IID partitioner shuffled with a fixed seed,
  so the seeds varied each bank's train/test split, the initial adapters and each client's data
  order, but not which sentences a bank held. The spread over seeds leaves out partition
  variance. Current code seeds that shuffle too.
- **Clients seeded from a scaled sum.** Each client pass seeded from
  `1000 * round + partition + 100_000 * seed`, which is distinct for these runs (20 rounds, 12
  banks) but repeats past round 99. Current code seeds from numpy's `SeedSequence`, so its
  client streams differ from these.
- **GPU runs were seeded but not bit-reproducible.** CUDA's nondeterministic kernels were not
  disabled then (current code disables them), so a replay can differ in the last digits.
