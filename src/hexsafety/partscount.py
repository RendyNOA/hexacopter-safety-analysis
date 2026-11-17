"""MIL-HDBK-217F Notice 2 parts count prediction.

    lambda_part = N * lambda_g * pi_Q      (pi_L = 1 for mature microcircuits)
    lambda_assembly = sum(lambda_part)

All values in failures per 10^6 hours (FPMH), environment ARW
(Airborne, Rotary Winged). Every assembly part is treated as critical, which is
the parts count convention and gives an upper bound for the hazard of interest.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

DATA = Path(__file__).resolve().parents[2] / "data"
QUALITY_LEVELS = ("commercial", "milspec")


def load_categories(path: Path = DATA / "mil217f_partscount_ARW.csv") -> Dict[str, dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return {r["category_id"]: r for r in csv.DictReader(f)}


def load_bom(name: str) -> List[dict]:
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def predict(bom: List[dict], categories: Dict[str, dict], quality: str = "commercial") -> List[dict]:
    if quality not in QUALITY_LEVELS:
        raise ValueError(f"quality must be one of {QUALITY_LEVELS}")
    rows = []
    for line in bom:
        cat = categories[line["category_id"]]
        qty = int(line["qty"])
        lam_g = float(cat["lambda_g_fpmh_ARW"])
        pi_q = float(cat[f"piQ_{quality}"])
        rows.append({
            **line,
            "qty": qty,
            "lambda_g": lam_g,
            "pi_Q": pi_q,
            "lambda_fpmh": qty * lam_g * pi_q,
        })
    return rows


def total(rows: List[dict]) -> float:
    return sum(r["lambda_fpmh"] for r in rows)


def assemblies(quality: str = "commercial") -> Dict[str, List[dict]]:
    cats = load_categories()
    return {
        "ESC": predict(load_bom("bom_esc_sapog.csv"), cats, quality),
        "FMU": predict(load_bom("bom_fmu_v3.csv"), cats, quality),
    }
