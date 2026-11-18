# Challenge windows for smart-meter erasure closeout on a permissioned ledger

This is the companion repository for the paper **"Acknowledged Is Not Ordered: Challenge Windows for Smart-Meter Erasure Closeout on Permissioned Ledgers"** (under double-blind review).

The repository contains the smart contract, the experiment drivers for a four-validator Hyperledger Besu QBFT network, the complete raw data of the runs reported in the paper, and the scripts that turn those data into every table, figure and number in the paper.

The experiment asks one question. When an assessor records a closure of an erasure case and an authorized challenger contests it at almost the same moment, which assertion does the ledger honour? Four policies, all running the same contract, are compared:

| Name in code | Name in the paper | What the close checks |
|---|---|---|
| `preflight` | Preflight | Nothing on-chain. The assessor read the status off-chain before sending. |
| `atomic-0` | Guard, w = 0 | Rejects the close if a challenge is already committed. |
| `atomic-1` | Guard, w = 1 | The guard, plus the case is eligible only 1 block after registration. |
| `atomic-3` | Guard, w = 3 | The guard, plus the case is eligible only 3 blocks after registration. |

---

## Repository layout

```
contracts/ErasureCloseout.sol   Smart contract (Solidity 0.8.35, Berlin EVM)
qbft.py                         Launches four disposable Besu QBFT validators on localhost
experiment.py                   Contract replay, pilot (conformance) and calibration sweep
campaign.py                     Seeded, matched, counterbalanced campaign used in the paper
analyze_campaign.py             Validates a campaign run and exports result tables and figures
export_fixtures.py              Provenance: how fixtures/gridweave.json was exported (see Notes)
fixtures/gridweave.json         Six synthetic smart-meter conflict pairs (evidence digests only)
setup.sh                        Downloads Besu 26.10.2 and solc 0.8.35 (SHA-256 pinned), creates a venv
requirements.txt                Pinned Python dependencies for the drivers
requirements-plot.txt           Optional: Matplotlib, needed only for figures
LICENSE                         MIT License

results/
  campaign-20261110T035318937901Z/   Canonical run used in the paper (1,728 cases)
    configuration.json                Seeds, offsets, policy order, platform, tool versions, source hashes
    traces.jsonl                      One row per case with every receipt and timestamp
    complete.json                     Completion marker
    chain-1/, chain-2/                Validator logs, genesis log, memory samples per network
    paper-results/                    Archived analyzer output (tables, validation report, figure)
  pilot-20261110T033316509185Z/      Pilot run: conformance check of every decision path
  campaign-20261110T034614676035Z/   Earlier timing-calibration runs (not used for results)
  campaign-20261110T035054137437Z/   Earlier timing-calibration run (not used for results)
  sweep-20261110T033425274078Z/      One-replicate calibration sweep (not used for results)

paper/
  paper_analysis.py               Derived analyses: proposer attribution, audit replay, statistics
  make_paper_figures.py           Generates Figs. 1–4 of the paper
  data/derived/                   Output of paper_analysis.py (CSV tables, paper_numbers.json)
  figures/                        Output of make_paper_figures.py (PDF and SVG)
```

---

## Requirements

- **To reproduce the paper's numbers and figures from the archived data** (§1): Python 3.10 or later. Only the standard library is needed, plus Matplotlib for the figures (`pip install -r requirements-plot.txt`). No blockchain is needed.
- **To re-run the experiment** (§2): Linux x86-64, Java 25, Python 3.14, `curl`, and about 2 GB of free RAM for the four validators. `setup.sh` fetches Besu and solc and checks them against pinned SHA-256 digests.

---

## 1. Reproduce every result in the paper (about one minute, no blockchain)

Run from the repository root:

```bash
pip install -r requirements-plot.txt          # only needed for figures

# (a) Validate the canonical run and regenerate its result tables
python3 analyze_campaign.py results/campaign-20261110T035318937901Z \
    --out /tmp/paper-results --plot

# (b) Derived analyses: proposer attribution, audit-policy replay, statistics
python3 paper/paper_analysis.py

# (c) Figures 1-4 of the paper
python3 paper/make_paper_figures.py
```

What to expect:
- **(a)** recomputes every schedule from its seed and checks every trace row against it. It checks that the source files match the hashes recorded in `configuration.json`, then prints a validation report. The CSV files it writes are byte-identical to those archived in `results/campaign-20261110T035318937901Z/paper-results/`.
- **(b)** writes CSV tables and `paper_numbers.json` to `paper/data/derived/`.
- **(c)** writes `paper/figures/fig_*.pdf`, which are the files included in the paper.

---

## 2. Re-run the experiment from scratch

```bash
./setup.sh                                     # Besu, solc and a Python venv under .tools/

# Conformance pilot: exercises every decision path once per policy
.tools/venv/bin/python experiment.py pilot

# Full campaign used in the paper: 8 seeds, 4 seeds per fresh network
.tools/venv/bin/python campaign.py --replicates 8 --seeds-per-chain 4

# Validate and export the new run
python3 analyze_campaign.py results/<new-campaign-directory> \
    --out results/<new-campaign-directory>/paper-results --plot
python3 paper/paper_analysis.py results/<new-campaign-directory>
python3 paper/make_paper_figures.py results/<new-campaign-directory>
```

The canonical campaign took about 14 minutes on the host listed in its `configuration.json` (Intel Core 5 120U, 12 logical CPUs). A new run produces new transaction timings, so exact counts will differ from the archived run. The analyzer accepts only a completed `brain-closeout-campaign/3` run with a `complete.json` marker, and it refuses to run if the source files differ from the hashes recorded for that run.

---

## 3. Where each result in the paper comes from

| Paper element | Source in this repository |
|---|---|
| Table I (outcomes by policy) | `results/campaign-…/paper-results/Results_by_mode.csv` |
| Table II (inclusion lag) | `paper/data/derived/inclusion_lag.csv` |
| Fig. 1 (closeout model) | `paper/make_paper_figures.py` → `fig_system.pdf` |
| Fig. 2 (worked race, seed 20261111, offset −500 ms) | `make_paper_figures.py` → `fig_race.pdf`, from `traces.jsonl` |
| Fig. 3 (close-first share by offset) | `make_paper_figures.py` → `fig_ordering.pdf`, from `traces.jsonl` |
| Fig. 4 (order by proposer) | `paper/data/derived/same_block_by_proposer.csv` → `fig_proposer.pdf` |
| 1,728 cases, 4,480 transactions, 32 deployments, release lag | `paper-results/Validation.json` |
| 172 closures after an ordered challenge; 0 of 586 under the guard | `Results_by_mode.csv`; Wilson bound in `paper_numbers.json` |
| 19/24 and 11/96 overtaken at w = 0, with 95 % Wilson intervals | `Results_by_mode.csv`, `paper_numbers.json` → `wilson_95` |
| 29 of 30 overtakings in the same block | `Results_by_mode.csv` → `advance_recorded_before_challenge_same_block` |
| Challenge head start (median 241 ms; 65–72 ms in bursts) | `paper_numbers.json` → `head_start_ms` |
| Overtaking in 7 of 8 quiet seeds and 3 burst seeds | `paper_numbers.json` → `seeds_with_overtaking` |
| Proposer effect (187/187, 95/95, 44/242) | `paper/data/derived/same_block_by_proposer.csv` |
| Even proposer rotation, uneven close blocks | `paper_numbers.json` → `proposer_blocks`; `close_block_producers.csv` |
| w = 3 vs w = 0: 19 and 11 changed decisions, exact McNemar p | `Matched_contrasts.csv`, `paper_numbers.json` → `mcnemar_exact_w3_vs_w0` |
| Latency medians, p95, paired changes, seed ranges | `Results_by_mode.csv`, `Matched_contrasts.csv` |
| Audit-policy replay (30 vs 1 premature clearances) | `paper/data/derived/audit_replay_summary.csv` |
| Gas per call (31.8k vs 31.7k for a recorded close) | `paper_numbers.json` → `gas` |
| Pilot conformance | `results/pilot-20261110T033316509185Z/traces.jsonl` |

---

## 4. Data format

`traces.jsonl` has one JSON object per case. Its fields are:

- **Case and decision:**
  - identity: `mode`, `grace_blocks`, `workload` (`quiet` / `burst`), `seed`, `wave`, `case_id`, `fixture_pair`, `contract`, `chain`;
  - schedule: `offset_ms` (planned challenge offset from the nominal close, or `null` for uncontested controls);
  - outcome: `decision` (`RECORDED`, `BLOCKED`, `TOO_EARLY`) and `final_status`, the case status read on two validators at the block of the last transaction.
- **Transactions:** `ready`, `close`, `challenge` (the last can be `null`). Each holds `hash`, `block`, `block_hash`, `index`, `gas`, and three times in milliseconds relative to observing the readiness receipt: `submit_ms` (sent), `ack_ms` (RPC response returned) and `seen_ms` (receipt observed).
- **Derived flags:** `recorded_after_finalized_challenge`, `recorded_while_earlier_challenge_pending`, `advance_challenge`, `advance_ack_before_nominal`.
- **Scheduling details:** `nominal_close_ms`, `nominal_from_ready_ms`, `close_gate_from_ready_ms`, `close_dispatch_lag_ms`, `challenge_dispatch_lag_ms`, `same_offset_challenge_first`.

Committed order is `(block, index)`. All times come from one monotonic clock on the host.

---

## 5. Notes for reviewers

- **Anonymisation.** For double-blind review, the absolute path of the authors' working directory was replaced by `<repo>` in the archived validator logs. Nothing else in the logs was changed. Timestamps in the logs carry the host's local time-zone offset. `traces.jsonl`, `configuration.json` and all code are unmodified, and the analyzer verifies the code against the source hashes recorded at run time.
- **Fixtures.** `fixtures/gridweave.json` holds only SHA-256 digests of synthetic receipt streams from a reference benchmark, which is not part of this repository. `export_fixtures.py` documents how the digests were exported and checked. It is not needed to reproduce any result. The contract and drivers use only the digests.
- **Calibration runs.** The earlier `campaign-…` and `sweep-…` directories are timing-calibration records kept for transparency. They are not used for any result, and the analyzer rejects them because they lack a completion marker or use an older schema.
- **Scope.** The experiment measures the ordering and recording of assertions about a case. Physical erasure, the merits of a challenge, and inclusion under network failure or Byzantine validators are outside its scope, as the paper states.

---

## License and citation

The code and data are released under the [MIT License](LICENSE). The copyright line names "The authors" during double-blind review and will be updated, together with the paper's citation, after the review period.
<!-- After acceptance: replace "The authors" in LICENSE with the author names and add the citation (and a CITATION.cff). -->
