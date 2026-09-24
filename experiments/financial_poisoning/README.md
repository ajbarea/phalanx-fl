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
twelve (1 = farthest), a proxy for whether an inspector could single it out.

## Reproduce

Needs a CUDA torch in the project venv (the sweep gives each client a third of an 8 GB GPU):

```bash
uv sync --extra hf --extra torch
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
| `results/summary.md` | per scenario and rule: final accuracy, final attack success, mean attack success over the attack rounds, attacker outlier rank; median [min, max] over seeds |
| `results/summary.csv` | the same, one numeric column per median / min / max |
| `results/summary.tex` | the same as a booktabs table that fits one text column (`\input` it inside a `table`) |
| `results/rounds.csv` | every run, every round: accuracy, loss, attack success, attacker outlier rank |
| `results/figures/attack_success_by_round.{png,pdf}` | attack success per round under FedAvg, one line per scenario |
| `results/figures/final_by_rule.{png,pdf}` | final-round attack success and accuracy for every rule and scenario |
| `results/runs/<scenario>__<rule>__s<seed>.json` | one provenance manifest per run: git commit (and whether the tree was dirty), package versions, full run config, and per-round `heldout_metrics` and `attacker_outlier_rank` |

In a manifest, `metrics` (client-side evaluation) is empty because the sweep turns client
evaluation off; all scoring is the server's, in `heldout_metrics`, keyed by round (round 0 is
the untrained model).
