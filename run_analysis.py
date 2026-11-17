"""Reproduce every number, table and figure in docs/report.md.

    python run_analysis.py

Outputs go to results/ and figures/. The browser demo (index.html) is rebuilt
with the same data so both always agree.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from hexsafety import fta, model, partscount  # noqa: E402

RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
FLIGHT_HOUR = 1.0  # results are reported per flight hour (probability for a 1 h flight)


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def parts_tables() -> dict:
    out = {}
    for quality in partscount.QUALITY_LEVELS:
        for name, rows in partscount.assemblies(quality).items():
            out[(name, quality)] = rows
            if quality == "commercial":
                write_csv(RESULTS / f"parts_count_{name}.csv", rows,
                          ["ref_designators", "part_number", "description", "qty", "category_id",
                           "lambda_g", "pi_Q", "lambda_fpmh", "classification_note"])
    return out


def summary() -> list[dict]:
    rows = []
    for quality in partscount.QUALITY_LEVELS:
        r = model.rates(quality)
        for cfg, label in model.CONFIGS.items():
            top = model.build(cfg, quality)
            p = fta.probability(top, FLIGHT_HOUR)
            imp = fta.importance(top, FLIGHT_HOUR)
            fmu_share = imp["FMU"]["fussell_vesely"]
            rows.append({
                "config": cfg, "label": label, "parts_quality": quality,
                "lambda_FMU_fpmh": round(r["FMU"], 3), "lambda_ESC_fpmh": round(r["ESC"], 3),
                "P_loss_of_control_per_flight_hour": p,
                "one_in_N_flight_hours": round(1 / p),
                "FMU_share_FV": round(fmu_share, 4),
                "propulsion_electronics_share_FV": round(1 - fmu_share, 4),
            })
    write_csv(RESULTS / "summary.csv", rows, list(rows[0].keys()))
    return rows


def cut_sets() -> None:
    lines = []
    for cfg, label in model.CONFIGS.items():
        top = model.build(cfg)
        mcs = fta.minimal_cut_sets(top)
        by_order = {}
        for s in mcs:
            by_order.setdefault(len(s), []).append(sorted(s))
        lines.append(f"## {label}\n")
        for order, sets in sorted(by_order.items()):
            lines.append(f"Order {order}: {len(sets)} cut sets")
            for s in sets[:12]:
                lines.append("  {" + ", ".join(s) + "}")
            if len(sets) > 12:
                lines.append(f"  ... ({len(sets) - 12} more)")
        lines.append("")
    (RESULTS / "minimal_cut_sets.txt").write_text("\n".join(lines), encoding="utf-8")


def verify_monte_carlo() -> list[dict]:
    """Analytic vs Monte Carlo at a long exposure so the sampled estimate is precise."""
    hours = 500.0
    rows = []
    for cfg in model.CONFIGS:
        top = model.build(cfg)
        rows.append({"config": cfg, "hours": hours,
                     "analytic": fta.probability(top, hours),
                     "monte_carlo": fta.monte_carlo(top, hours, n=60_000, seed=11)})
    write_csv(RESULTS / "monte_carlo_check.csv", rows, list(rows[0].keys()))
    return rows


def demo_model(tables: dict) -> dict:
    cats = partscount.load_categories()

    def slim(rows):
        return [{k: r[k] for k in ("ref_designators", "part_number", "description", "qty",
                                    "category_id", "classification_note")} for r in rows]

    return {
        "categories": {k: {"description": v["description"], "section": v["mil217f_section"],
                           "lambda_g": float(v["lambda_g_fpmh_ARW"]),
                           "piQ": {"commercial": float(v["piQ_commercial"]),
                                   "milspec": float(v["piQ_milspec"])},
                           "piQ_level": {"commercial": v["piQ_commercial_level"],
                                         "milspec": v["piQ_milspec_level"]}}
                       for k, v in cats.items()},
        "boms": {"ESC": slim(tables[("ESC", "commercial")]), "FMU": slim(tables[("FMU", "commercial")])},
        "configs": model.CONFIGS,
        "reference": {cfg: {q: fta.probability(model.build(cfg, q), FLIGHT_HOUR)
                            for q in partscount.QUALITY_LEVELS} for cfg in model.CONFIGS},
    }


def build_demo(data: dict) -> None:
    page = ROOT / "index.html"
    html = page.read_text(encoding="utf-8")
    start, end = "/*MODEL-JSON-START*/", "/*MODEL-JSON-END*/"
    i, j = html.index(start) + len(start), html.index(end)
    html = html[:i] + json.dumps(data, separators=(",", ":")) + html[j:]
    page.write_text(html, encoding="utf-8")


def figures(sumrows: list[dict], tables: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    SERIES = {"quad_x": "#2a78d6", "hexa_pnpnpn": "#eb6834", "hexa_ppnnpn": "#1baf7a"}
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID,
                         "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                         "figure.facecolor": SURF, "axes.facecolor": SURF})

    def style(ax):
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(length=0)

    com = [r for r in sumrows if r["parts_quality"] == "commercial"]

    # 1. Configuration comparison: rate split into FMU and propulsion electronics
    fig, ax = plt.subplots(figsize=(8.5, 3.6))
    labels = [r["label"] for r in com][::-1]
    p = [r["P_loss_of_control_per_flight_hour"] for r in com][::-1]
    fmu = [x * r["FMU_share_FV"] for x, r in zip(p, com[::-1])]
    prop = [x - f for x, f in zip(p, fmu)]
    ax.barh(labels, fmu, color="#2a78d6", height=0.55, label="Flight computer (FMU)",
            edgecolor=SURF, linewidth=1.5)
    ax.barh(labels, prop, left=fmu, color="#eb6834", height=0.55,
            label="Propulsion electronics (ESCs)", edgecolor=SURF, linewidth=1.5)
    for y, val in enumerate(p):
        ax.text(val + 0.00001, y, f"{val:.2e}  (1 in {round(1/val):,} h)", va="center", color=INK, fontsize=9)
    ax.set_xlim(0, max(p) * 1.45)
    ax.set_xlabel("Probability of loss of controlled flight per flight hour (quantified items only)")
    ax.set_title("Same parts, different rotor layout", loc="left", color=INK, fontsize=12, fontweight="bold")
    ax.legend(loc="lower left", bbox_to_anchor=(0, -0.42), ncol=2, frameon=False, fontsize=8.5)
    style(ax)
    fig.tight_layout()
    fig.savefig(FIGURES / "config_comparison.png", dpi=160)
    plt.close(fig)

    # 2. Where the failure rate comes from (category totals per assembly)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, name in zip(axes, ("FMU", "ESC")):
        agg = {}
        for r in tables[(name, "commercial")]:
            agg[r["category_id"]] = agg.get(r["category_id"], 0) + r["lambda_fpmh"]
        items = sorted(agg.items(), key=lambda kv: kv[1])[-8:]
        short = {"C_CER_CHIP": "Ceramic capacitors", "R_FILM": "Film resistors", "IC_LIN_10000": "Linear ICs",
                 "IC_MOS_UP32": "32-bit MCUs", "R_NETWORK": "Resistor networks", "XTAL": "Crystals",
                 "Q_SIFET_LF": "MOSFETs", "IC_MOS_LOGIC_1000": "Logic ICs", "R_FILM_POWER": "Shunt resistor",
                 "CONN_RECT": "Connectors", "D_TVS": "TVS diodes", "C_FEEDTHRU": "Feed-through caps",
                 "IC_MOS_SRAM_256K": "F-RAM", "OPTO_LED": "LEDs", "D_SWITCHING": "Switching diodes"}
        ax.barh([short.get(k, k) for k, _ in items], [v for _, v in items], color="#2a78d6", height=0.6)
        for y, (_, v) in enumerate(items):
            ax.text(v + 0.3, y, f"{v:.1f}", va="center", fontsize=8.5, color=INK)
        tot = partscount.total(tables[(name, "commercial")])
        ax.set_title(f"{name}: {tot:.1f} failures / 10^6 h", loc="left", color=INK, fontsize=11, fontweight="bold")
        ax.set_xlabel("failures per 10^6 h (commercial parts, ARW)")
        style(ax)
    fig.tight_layout()
    fig.savefig(FIGURES / "parts_breakdown.png", dpi=160)
    plt.close(fig)

    # 3. What-if: ranking stays the same whatever the open motor+propeller rate turns out to be
    fig, ax = plt.subplots(figsize=(8, 3.6))
    xs = list(range(0, 201, 5))
    for cfg, label in model.CONFIGS.items():
        ys = [fta.probability(model.build(cfg, motor=x, prop=0.0), FLIGHT_HOUR) for x in xs]
        ax.plot(xs, ys, color=SERIES[cfg], linewidth=2, label=label)
        ax.text(xs[-1] + 3, ys[-1], label.split(" (")[0], va="center", fontsize=8.5, color=INK)
    ax.set_xlim(0, 260)
    ax.set_xlabel("What-if: motor + propeller failure rate per rotor (failures / 10^6 h) - OPEN ITEM, not data")
    ax.set_ylabel("P(loss of control) per flight hour")
    ax.set_title("The layout ranking does not depend on the missing data", loc="left", color=INK,
                 fontsize=12, fontweight="bold")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIGURES / "open_item_whatif.png", dpi=160)
    plt.close(fig)


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    FIGURES.mkdir(exist_ok=True)
    tables = parts_tables()
    rows = summary()
    cut_sets()
    mc = verify_monte_carlo()
    data = demo_model(tables)
    (RESULTS / "model.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    build_demo(data)
    figures(rows, tables)
    for r in rows:
        print(f"{r['parts_quality']:10s} {r['config']:12s} P/fh={r['P_loss_of_control_per_flight_hour']:.3e} "
              f"(1 in {r['one_in_N_flight_hours']:,} h)  FMU share={r['FMU_share_FV']:.0%}")
    for r in mc:
        print(f"MC check {r['config']:12s} analytic={r['analytic']:.4f} mc={r['monte_carlo']:.4f}")


if __name__ == "__main__":
    main()
