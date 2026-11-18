#!/usr/bin/env python3
"""Derived analyses for the paper from the canonical BRAINS campaign.

Reads traces.jsonl and the validator logs of the canonical run and writes CSV
tables and paper_numbers.json to paper/data/derived/. Standard library only.

  python3 paper/paper_analysis.py [results/campaign-20261110T035318937901Z]

Analyses
  1. Proposer attribution: joins each committed block (chain, height, hash
     prefix/suffix) to the validator whose log reports "Produced #<height>".
     Validator roles follow qbft.launch_network / experiment.Replay:
     V1 assessor ingress, V2 challenger ingress, V3 receipt observer,
     V4 cross-check observer.
  2. Same-block order by proposer role for challenged cases.
  3. Audit-consumer replay: for every recorded close that a challenge follows
     in ledger order, the decision of an event policy (acts on the close
     event) and a block-end state policy (reads case status at the end of the
     close block), and the actionable interval in blocks.
  4. Inclusion lag of uncontested closes (close block - ready block).
  5. paper_numbers.json: every statistic quoted in the paper that is not a
     direct column of the analyzer's CSVs (Wilson intervals, exact McNemar
     tests, challenge head start, per-seed spread, gas, proposer rotation).
"""
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
from statistics import median
import re
import sys

ROLE = {1: "Assessor ingress (V1)", 2: "Challenger ingress (V2)",
        3: "Receipt observer (V3)", 4: "Cross-check (V4)"}
PRODUCED = re.compile(r"Produced #(\d+)\s+\(([0-9a-f]{5})\.+([0-9a-f]{5})\)")


def proposers(run):
    table = {}
    for chain_dir in sorted(run.glob("chain-*")):
        chain = int(chain_dir.name.split("-")[1])
        for validator in range(1, 5):
            for line in (chain_dir / f"validator-{validator}.log").read_text().splitlines():
                match = PRODUCED.search(line)
                if match:
                    height, prefix, suffix = int(match[1]), match[2], match[3]
                    key = (chain, height)
                    assert key not in table, f"two producers for {key}"
                    table[key] = (validator, prefix, suffix)
    return table


def producer(table, chain, tx):
    validator, prefix, suffix = table[(chain, tx["block"])]
    block_hash = tx["block_hash"][2:]
    assert block_hash.startswith(prefix) and block_hash.endswith(suffix), "hash mismatch"
    return validator


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def wilson(k, n, z=1.959964):
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round((c - s) / d, 4), round((c + s) / d, 4)]


def mcnemar_exact(b, c):
    n = b + c
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def paper_numbers(rows, table, run):
    def sel(mode, workload):
        return [r for r in rows if r["mode"] == mode and r["workload"] == workload]
    numbers = {"wilson_95": {}, "mcnemar_exact_w3_vs_w0": {}, "head_start_ms": {},
               "seeds_with_overtaking": {}, "gas": {}, "proposer_blocks": {}}
    for mode in ("atomic-0", "atomic-3"):
        for workload in ("quiet", "burst"):
            adv = [r for r in sel(mode, workload) if r["advance_challenge"]]
            over = [r for r in adv if r["decision"] == "RECORDED"]
            numbers["wilson_95"][f"{mode}/{workload}/advance_overtaken"] = {
                "k": len(over), "n": len(adv), "ci": wilson(len(over), len(adv))}
            seeds = {r["seed"] for r in over}
            numbers["seeds_with_overtaking"][f"{mode}/{workload}"] = len(seeds)
            if mode == "atomic-0":
                lead = [r["close"]["submit_ms"] - r["challenge"]["ack_ms"] for r in over]
                numbers["head_start_ms"][workload] = {
                    "median": round(median(lead), 1), "min": round(min(lead), 1), "max": round(max(lead), 1)}
    guarded_prior = [r for r in rows if r["mode"] != "preflight" and r["challenge"]
                     and (r["challenge"]["block"], r["challenge"]["index"]) < (r["close"]["block"], r["close"]["index"])]
    numbers["wilson_95"]["guarded/closed_after_ordered_challenge"] = {
        "k": sum(r["decision"] == "RECORDED" for r in guarded_prior), "n": len(guarded_prior),
        "ci": wilson(sum(r["decision"] == "RECORDED" for r in guarded_prior), len(guarded_prior))}
    for workload in ("quiet", "burst"):
        zero = {r["case_id"]: r for r in sel("atomic-0", workload)}
        b = c = 0
        for r in sel("atomic-3", workload):
            z = zero[r["case_id"]]
            if z["advance_challenge"]:
                b += z["decision"] == "RECORDED" and r["decision"] == "BLOCKED"
                c += z["decision"] == "BLOCKED" and r["decision"] == "RECORDED"
        numbers["mcnemar_exact_w3_vs_w0"][workload] = {"recorded_to_blocked": b, "blocked_to_recorded": c,
                                                      "p": mcnemar_exact(b, c)}
    def gas(values):
        return sorted({v for v in values})
    numbers["gas"]["registerReady"] = gas(r["ready"]["gas"] for r in rows)
    numbers["gas"]["fileChallenge"] = gas(r["challenge"]["gas"] for r in rows if r["challenge"])
    for mode in ("preflight", "atomic-0"):
        for decision in ("RECORDED", "BLOCKED"):
            g = gas(r["close"]["gas"] for r in rows if r["mode"] == mode and r["decision"] == decision)
            if g:
                numbers["gas"][f"close/{mode}/{decision}"] = g
    per = Counter((chain, v) for (chain, _h), (v, _p, _s) in table.items())
    numbers["proposer_blocks"] = {f"chain-{c}/V{v}": n for (c, v), n in sorted(per.items())}
    rounds = 0
    for log in run.glob("chain-*/validator-*.log"):
        rounds += sum("round change" in line.lower() for line in log.read_text().splitlines())
    numbers["round_change_log_lines"] = rounds
    return numbers


def main(run):
    out = Path(__file__).resolve().parent / "data" / "derived"
    rows = [json.loads(line) for line in (run / "traces.jsonl").read_text().splitlines()]
    table = proposers(run)

    # 2. same-block order by proposer role
    same_block = Counter()
    for row in rows:
        challenge, close = row["challenge"], row["close"]
        if challenge is None or challenge["block"] != close["block"]:
            continue
        role = producer(table, row["chain"], close)
        first = "close_first" if close["index"] < challenge["index"] else "challenge_first"
        same_block[(row["mode"], role, first)] += 1
    proposer_rows = []
    for mode in ("preflight", "atomic-0", "atomic-1", "atomic-3"):
        for role in ROLE:
            c = same_block[(mode, role, "close_first")]
            h = same_block[(mode, role, "challenge_first")]
            if c + h:
                proposer_rows.append({"mode": mode, "proposer": ROLE[role],
                                      "close_first": c, "challenge_first": h})
    write(out / "same_block_by_proposer.csv", proposer_rows)

    # Block production share (all blocks containing a case transaction)
    produced = Counter(producer(table, r["chain"], r["close"]) for r in rows)
    write(out / "close_block_producers.csv",
          [{"proposer": ROLE[v], "close_blocks": produced[v]} for v in ROLE])

    # 3. audit-consumer replay over recorded closes followed by a challenge
    audit = []
    for row in rows:
        challenge, close = row["challenge"], row["close"]
        if row["decision"] != "RECORDED" or challenge is None:
            continue
        if (challenge["block"], challenge["index"]) < (close["block"], close["index"]):
            continue  # preflight closes after an ordered challenge are counted elsewhere
        interval = challenge["block"] - close["block"]
        audit.append({
            "mode": row["mode"], "workload": row["workload"], "seed": row["seed"],
            "offset_ms": row["offset_ms"], "advance": row["advance_challenge"],
            "ack_before_close_submit": challenge["ack_ms"] < close["submit_ms"],
            "event_policy_clears": True,
            "state_policy_clears": interval > 0,
            "actionable_blocks": interval,
        })
    write(out / "audit_replay_cases.csv", audit)
    summary = defaultdict(Counter)
    for a in audit:
        key = (a["mode"], a["workload"])
        summary[key]["overtaken_closes"] += 1
        summary[key]["ack_before_close"] += a["ack_before_close_submit"]
        summary[key]["event_clears_ack_before"] += a["ack_before_close_submit"]
        summary[key]["state_clears_ack_before"] += a["ack_before_close_submit"] and a["state_policy_clears"]
        summary[key]["state_clears_total"] += a["state_policy_clears"]
        if a["state_policy_clears"]:
            summary[key][f"interval_{min(a['actionable_blocks'], 3)}"] += 1
    write(out / "audit_replay_summary.csv",
          [{"mode": m, "workload": w, **{k: v for k, v in c.items()}}
           for (m, w), c in sorted(summary.items())])

    # 4. inclusion lag for uncontested closes
    lag = Counter((r["mode"], r["workload"], r["close"]["block"] - r["ready"]["block"])
                  for r in rows if r["challenge"] is None)
    write(out / "inclusion_lag.csv",
          [{"mode": m, "workload": w, "lag_blocks": d, "cases": n} for (m, w, d), n in sorted(lag.items())])

    # 5. per-case latency for uncontested closes (for ECDFs)
    write(out / "uncontested_latency.csv",
          [{"mode": r["mode"], "workload": r["workload"], "seed": r["seed"], "case_id": r["case_id"],
            "latency_ms": r["close"]["seen_ms"]} for r in rows if r["challenge"] is None])

    (out / "paper_numbers.json").write_text(json.dumps(paper_numbers(rows, table, run), indent=2) + "\n")

    for name in ("same_block_by_proposer", "audit_replay_summary", "inclusion_lag", "close_block_producers"):
        print(f"== {name}")
        print((out / f"{name}.csv").read_text())


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "results" / "campaign-20261110T035318937901Z")
