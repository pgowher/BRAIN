#!/usr/bin/env python3
"""Publication figures for the paper, drawn from the canonical BRAINS campaign.

  python3 paper/make_paper_figures.py [results/campaign-20261110T035318937901Z]

Writes vector PDFs (and SVGs) to paper/figures/. Run paper_analysis.py first;
fig_proposer reads paper/data/derived/same_block_by_proposer.csv.

Colour roles (validated with the dataviz validator, light surface):
  window w = 0 / 1 / 3 -> one-hue ordinal blue ramp (#5598e7, #256abf, #0d366b)
  preflight            -> neutral grey, dashed
  close first / challenge first -> categorical orange / blue
Identity never relies on colour alone: markers, line styles and direct labels.
"""
from collections import defaultdict
import csv
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

HERE = Path(__file__).resolve().parent
OUT = HERE / "figures"
COL = 3.487      # IEEEtran conference column width (in)
FULL = 7.16      # IEEEtran text width (in)

INK, INK2, MUTED, GRID = "#1d1f21", "#52514e", "#8a8984", "#e3e2de"
W = {"atomic-0": "#5598e7", "atomic-1": "#256abf", "atomic-3": "#0d366b"}
MARK = {"atomic-0": "o", "atomic-1": "s", "atomic-3": "D"}
LABEL = {"preflight": "Preflight", "atomic-0": "$w{=}0$", "atomic-1": "$w{=}1$", "atomic-3": "$w{=}3$"}
BLUE, ORANGE = "#2a78d6", "#eb6834"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "STIX Two Text", "Liberation Serif", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "axes.linewidth": .6, "axes.edgecolor": INK2, "axes.labelcolor": INK,
    "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
    "xtick.major.width": .6, "ytick.major.width": .6,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "pdf.fonttype": 42, "svg.fonttype": "none",
    "svg.hashsalt": "brain-2027",
})


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf", metadata={"CreationDate": None, "ModDate": None})
    fig.savefig(OUT / f"{name}.svg")
    plt.close(fig)


def load(run):
    return [json.loads(line) for line in (run / "traces.jsonl").read_text().splitlines()]


def order(tx):
    return tx["block"], tx["index"]


# ---------------------------------------------------------------- Fig. ordering
def fig_ordering(rows):
    """(a, b) share of challenged cases in which the close was ordered first, by offset."""
    from matplotlib.lines import Line2D
    fig, axes = plt.subplots(1, 2, figsize=(COL, 1.62), gridspec_kw={"wspace": .12})
    for col, workload in enumerate(("quiet", "burst")):
        ax = axes[col]
        ax.axvspan(-560, 0, color="#f1f0ec", zorder=0, lw=0)
        for mode in ("atomic-0", "atomic-1", "atomic-3"):
            share = defaultdict(lambda: [0, 0])
            for r in rows:
                if r["mode"] == mode and r["workload"] == workload and r["challenge"]:
                    cell = share[r["offset_ms"]]
                    cell[0] += order(r["close"]) < order(r["challenge"])
                    cell[1] += 1
            xs = sorted(share)
            ys = [share[x][0] / share[x][1] for x in xs]
            ax.plot(xs, ys, color=W[mode], marker=MARK[mode], ms=3.6, lw=1.3,
                    mec="white", mew=.5, zorder=3, label=LABEL[mode])
        ax.set_ylim(-.05, 1.05)
        ax.set_xlim(-560, 600)
        ax.set_xticks((-500, -250, 0, 250, 500))
        ax.set_yticks((0, .5, 1), ("0", "50%", "100%") if col == 0 else ())
        ax.set_title(f"({'a' if col == 0 else 'b'}) {workload.capitalize()}", loc="left", pad=3)
        ax.grid(axis="y", color=GRID, lw=.5)
        ax.set_axisbelow(True)
        if col == 0:
            ax.set_ylabel("Close ordered first")
    axes[0].set_xlabel("Challenge offset from nominal close (ms)", x=1.06, labelpad=1)
    handles = [Line2D([], [], color=W[m], marker=MARK[m], ms=3.6, mec="white", mew=.5, lw=1.3, label=LABEL[m])
               for m in ("atomic-0", "atomic-1", "atomic-3")]
    fig.legend(handles=handles, loc="upper center", ncol=3, bbox_to_anchor=(.57, 1.0),
               handlelength=2.0, columnspacing=1.4, borderaxespad=.2)
    fig.subplots_adjust(left=.15, right=.985, top=.76, bottom=.24)
    save(fig, "fig_ordering")


# ---------------------------------------------------------------- Fig. proposer
def fig_proposer():
    rows = list(csv.DictReader((HERE / "data/derived/same_block_by_proposer.csv").open()))
    roles = ["Assessor ingress (V1)", "Challenger ingress (V2)", "Receipt observer (V3)", "Cross-check (V4)"]
    totals = {role: [0, 0] for role in roles}
    for r in rows:  # pooled over preflight, w=0 and w=1 (w=3 has no same-block pairs)
        totals[r["proposer"]][0] += int(r["close_first"])
        totals[r["proposer"]][1] += int(r["challenge_first"])
    fig, ax = plt.subplots(figsize=(COL, 1.28))
    gap = .004
    for y, role in enumerate(roles):
        c, h = totals[role]
        n = c + h
        fc, fh = c / n, h / n
        if fc:
            ax.barh(y, fc - (gap if fh else 0), color=ORANGE, height=.62, lw=0)
        if fh:
            ax.barh(y, fh - (gap if fc else 0), left=fc + (gap if fc else 0), color=BLUE, height=.62, lw=0)
        if fc >= .12:
            ax.text(fc / 2, y, f"{c}", ha="center", va="center", color="white", fontsize=7, weight="bold")
        if fh >= .12:
            ax.text(fc + fh / 2, y, f"{h}", ha="center", va="center", color="white", fontsize=7, weight="bold")
        ax.text(1.015, y, f"$n{{=}}{n}$", va="center", fontsize=6.5, color=INK2)
    ax.set_yticks(range(len(roles)), roles)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xticks((0, .5, 1), ("0", "50%", "100%"))
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Share of same-block close/challenge pairs", labelpad=1)
    ax.text(0, -.85, "■", color=ORANGE, fontsize=8, va="center")
    ax.text(.035, -.85, "close ordered first", fontsize=7, va="center")
    ax.text(.42, -.85, "■", color=BLUE, fontsize=8, va="center")
    ax.text(.455, -.85, "challenge ordered first", fontsize=7, va="center")
    fig.subplots_adjust(left=.33, right=.9, top=.84, bottom=.27)
    save(fig, "fig_proposer")


# ---------------------------------------------------------------- diagrams
def box(ax, x, y, w, h, text, *, fc="white", ec=INK2, lw=.7, fs=7, weight="normal", ls="-", color=INK, r=.03):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, ls=ls))
    if text:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, weight=weight,
                color=color, linespacing=1.05)


def arrow(ax, a, b, *, text=None, tx=None, ty=None, color=INK, ls="-", lw=.8, fs=6.3, rad=0.0,
          ha="center", style="-|>", ms=6):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=ms, color=color, lw=lw, ls=ls,
                                 shrinkA=1, shrinkB=1, connectionstyle=f"arc3,rad={rad}"))
    if text:
        ax.text(tx if tx is not None else (a[0] + b[0]) / 2, ty if ty is not None else (a[1] + b[1]) / 2,
                text, fontsize=fs, ha=ha, va="center", color=INK2, linespacing=1.0)


def fig_system():
    """Deployment and custody boundary (left); case state machine (right)."""
    fig = plt.figure(figsize=(FULL, 1.5))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 14.32)
    ax.set_ylim(0, 3.56)
    ax.axis("off")

    # off-chain custody
    box(ax, .08, .12, 2.5, 3.3, "", fc="#f6f5f2", ec=MUTED, ls=(0, (3, 2)), r=.08)
    ax.text(1.33, 3.22, "Off-chain custody", ha="center", fontsize=7.5, weight="bold")
    box(ax, .23, 2.18, 2.2, .72, "Assessor\nevidence bundle $E$", fs=7)
    box(ax, .23, 1.12, 2.2, .72, "Challenger\nadverse stream $A$", fs=7)
    box(ax, .23, .3, 2.2, .5, "Meter data, declarations", fs=6.5, color=INK2)
    ax.text(1.33, .87, "never on-chain", ha="center", fontsize=6, color=INK2, style="italic")

    # validators
    box(ax, 4.0, .12, 4.55, 3.3, "", fc="white", ec=MUTED, r=.08)
    ax.text(6.28, 3.22, "Besu QBFT, 4 validators, 1 s blocks", ha="center", fontsize=7.5, weight="bold")
    pos = {1: (5.05, 2.35), 2: (5.05, .85), 3: (7.5, 2.35), 4: (7.5, .85)}
    names = {1: "V1\nassessor ingress", 2: "V2\nchallenger ingress", 3: "V3\nreceipt observer",
             4: "V4\ncross-check"}
    for v, (x, y) in pos.items():
        box(ax, x - .8, y - .38, 1.6, .76, names[v], fs=6.6,
            fc="#eef4fc" if v in (1, 2) else "white", ec=BLUE if v in (1, 2) else INK2)
    for a, b in ((1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4)):
        (x1, y1), (x2, y2) = pos[a], pos[b]
        ax.plot([x1, x2], [y1, y2], color="#c9c7c0", lw=1.0, zorder=0)
    ax.text(6.28, 1.6, "gossip + round-robin\nproposer", ha="center", va="center", fontsize=6.2,
            color=INK2, bbox=dict(fc="white", ec="none", pad=.6))

    arrow(ax, (2.43, 2.54), (4.25, 2.4), text="registerReady\nrecordClose", tx=3.3, ty=2.88, fs=6)
    arrow(ax, (2.43, 1.48), (4.25, .9), text="fileChallenge", tx=3.3, ty=.82, fs=6)

    # state machine
    box(ax, 8.85, .12, 5.38, 3.3, "", fc="white", ec=MUTED, r=.08)
    ax.text(11.54, 3.22, "Case state in ErasureCloseout", ha="center", fontsize=7.5, weight="bold")
    s = {"Ready": (9.85, 2.0), "Closed": (12.95, 2.55), "Disputed": (12.95, .78)}
    for name, (x, y) in s.items():
        box(ax, x - .62, y - .26, 1.24, .52, name.upper(), fs=6.8, weight="bold",
            fc="#fdf0ea" if name == "Disputed" else "white", ec=ORANGE if name == "Disputed" else INK2)
    arrow(ax, (10.47, 2.12), (12.33, 2.55), text="close at $h\\geq e$,\nno prior challenge",
          tx=11.35, ty=2.73, fs=6)
    arrow(ax, (10.3, 1.74), (12.33, .84), text="challenge", tx=11.05, ty=1.1, fs=6)
    arrow(ax, (12.95, 2.29), (12.95, 1.04), text="later\nchallenge", tx=13.55, ty=1.66, fs=6, ha="center")
    ax.text(9.05, .6, "$e = h_{\\mathrm{ready}} + w$\nclose at $h<e$: TooEarly\nguarded close after\n"
            "a challenge: Blocked", fontsize=6, color=INK2, va="center", ha="left", linespacing=1.15)
    save(fig, "fig_system")


def fig_race(run):
    """Worked trace: same case and schedule under w=0 and w=3 (seed 20261111, offset -500 ms)."""
    rows = {r["mode"]: r for r in load(run)
            if r["seed"] == 20261111 and r["workload"] == "quiet" and r["offset_ms"] == -500
            and r["mode"] in ("atomic-0", "atomic-3")}
    fig, axes = plt.subplots(2, 1, figsize=(COL, 1.9), sharex=True, gridspec_kw={"hspace": .5})
    for ax, mode in zip(axes, ("atomic-0", "atomic-3")):
        r = rows[mode]
        ch, cl, rd = r["challenge"], r["close"], r["ready"]
        hr = rd["block"]
        ax.set_ylim(0, 2.62)
        ax.set_yticks(())
        ax.spines["left"].set_visible(False)
        # driver lane (y=1.45)
        ax.plot([0, 3.25], [1.78, 1.78], color=GRID, lw=.8, zorder=0)
        ax.axvline(r["nominal_from_ready_ms"] / 1000, color=MUTED, ls=(0, (2, 2)), lw=.7, zorder=0)
        ax.text(r["nominal_from_ready_ms"] / 1000 + .05, 2.42, "nominal close", fontsize=6, color=INK2,
                va="center")
        ax.plot(ch["ack_ms"] / 1000, 1.78, marker="v", color=BLUE, ms=5, zorder=3)
        ax.text(-.03, 2.08, f"chal. ack. {ch['ack_ms']:.0f} ms", fontsize=6,
                ha="left", va="center", color=INK)
        ax.plot(cl["submit_ms"] / 1000, 1.78, marker="v", color=ORANGE, ms=5, zorder=3)
        ax.text(cl["submit_ms"] / 1000 + .06, 1.45,
                f"close sent {cl['submit_ms']:.0f} ms", fontsize=6, ha="left", va="center")
        # ledger lane (y=.45): committed blocks at their receipt-observation times
        blocks = sorted({ch["block"], cl["block"]})
        seen = {ch["block"]: ch["seen_ms"] / 1000, cl["block"]: cl["seen_ms"] / 1000}
        for b in range(hr + 1, max(blocks) + 1):
            t = seen.get(b, (seen[blocks[0]] + (b - blocks[0])))
            members = sorted([("challenge", ch) if ch["block"] == b else None,
                              ("close", cl) if cl["block"] == b else None],
                             key=lambda m: m[1]["index"] if m else 99)
            members = [m for m in members if m]
            width = .3 + .26 * max(len(members), 1)
            ax.add_patch(Rectangle((t - width, .08), width, .62, fc="white", ec=INK2, lw=.6))
            ax.text(t - width / 2, .88, f"$h_r{{+}}{b - hr}$", ha="center", fontsize=6.3, color=INK2)
            for i, (kind, tx) in enumerate(members):
                ax.add_patch(Rectangle((t - width + .06 + i * .29, .17), .25, .44,
                                       fc=ORANGE if kind == "close" else BLUE, lw=0))
                ax.text(t - width + .185 + i * .29, .39, "Cl" if kind == "close" else "Ch",
                        ha="center", va="center", fontsize=6, color="white", weight="bold")
        verdict = ("close Recorded; block-end status Disputed" if mode == "atomic-0"
                   else "close Blocked; challenge already ordered")
        ax.set_title(f"$w{{=}}{r['grace_blocks']}$: {verdict}", loc="left", pad=3, fontsize=7.5)
    axes[1].set_xlim(-.05, 3.35)
    axes[1].set_xticks((0, 1, 2, 3))
    axes[1].set_xlabel("Time since readiness receipt observed (s)", labelpad=1)
    fig.subplots_adjust(left=.03, right=.985, top=.92, bottom=.17)
    save(fig, "fig_race")


def main(run):
    rows = load(run)
    fig_ordering(rows)
    fig_proposer()
    fig_system()
    fig_race(run)
    print("wrote", sorted(p.name for p in OUT.glob("*.pdf")))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "results" / "campaign-20261110T035318937901Z")
