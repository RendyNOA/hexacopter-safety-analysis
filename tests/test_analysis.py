"""Run with:  python -m pytest -q   (or python tests/test_analysis.py)"""
import csv
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hexsafety import fta, model, partscount  # noqa: E402


def test_or_and_atleast_math():
    a, b, c = (fta.Event(x, x, r) for x, r in (("A", 100.0), ("B", 200.0), ("C", 300.0)))
    h = 1000.0
    pa, pb, pc = (e.prob(h) for e in (a, b, c))
    assert math.isclose(fta.probability(fta.Gate("o", "o", "OR", [a, b]), h), 1 - (1 - pa) * (1 - pb))
    assert math.isclose(fta.probability(fta.Gate("x", "x", "AND", [a, b]), h), pa * pb)
    two_of_three = pa * pb + pa * pc + pb * pc - 2 * pa * pb * pc
    assert math.isclose(fta.probability(fta.Gate("k", "k", "ATLEAST", [a, b, c], k=2), h), two_of_three)


def test_exponential_matches_rate():
    e = fta.Event("E", "E", 123.0)  # 123 failures per 10^6 h
    assert math.isclose(e.prob(1.0), 1 - math.exp(-123e-6))
    assert fta.Event("O", "open", None).prob(1e6) == 0.0


def test_every_bom_line_has_a_category_and_quantities_match_source():
    cats = partscount.load_categories()
    esc = partscount.load_bom("bom_esc_sapog.csv")
    fmu = partscount.load_bom("bom_fmu_v3.csv")
    for line in esc + fmu:
        assert line["category_id"] in cats, line
    # Sapog ESC schematic: 86 electrical parts (pads, fiducials, test points excluded); FMUv3 REV D BOM: 151 parts, 3 MEMS sensors excluded (OI-04)
    assert sum(int(x["qty"]) for x in esc) == 86
    assert sum(int(x["qty"]) for x in fmu) == 148


def test_parts_count_totals():
    r = model.rates("commercial")
    assert math.isclose(r["ESC"], 280.558, rel_tol=1e-4)
    assert math.isclose(r["FMU"], 406.013, rel_tol=1e-4)


def test_layout_ranking_holds_for_any_open_rotor_rate():
    for extra in (0.0, 10.0, 100.0, 1000.0):
        p = {c: fta.probability(model.build(c, motor=extra), 1.0) for c in model.CONFIGS}
        assert p["hexa_pnpnpn"] > p["quad_x"] > p["hexa_ppnnpn"]


def test_cut_sets_ppnnpn():
    mcs = fta.minimal_cut_sets(model.build("hexa_ppnnpn"))
    singles = {next(iter(s)) for s in mcs if len(s) == 1}
    assert "ESC5" in singles and "ESC6" in singles and "ESC1" not in singles
    assert frozenset({"ESC1", "ESC2"}) in mcs


def test_monte_carlo_agrees_with_analytic():
    with open(ROOT / "results" / "monte_carlo_check.csv") as f:
        for row in csv.DictReader(f):
            assert abs(float(row["analytic"]) - float(row["monte_carlo"])) < 0.01


def test_browser_engine_matches_python():
    node = shutil.which("node")
    if not node:
        return
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    engine = re.search(r"/\*ENGINE-START\*/(.*?)/\*ENGINE-END\*/", html, re.S).group(1)
    model_json = re.search(r"/\*MODEL-JSON-START\*/(.*?)/\*MODEL-JSON-END\*/", html, re.S).group(1)
    cases = [(c, q, h, m) for c in model.CONFIGS for q in partscount.QUALITY_LEVELS
             for h in (0.25, 1.0, 500.0) for m in (None, 40.0)]
    js = engine + f"\nconst M={model_json};\nconst cases={json.dumps(cases)};\n" + \
        "console.log(JSON.stringify(cases.map(([c,q,h,m])=>prob(buildTree(M,c,q,{motor:m,prop:null,bat:null,imu:null}),h))));"
    out = json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout)
    for (c, q, h, m), pj in zip(cases, out):
        pp = fta.probability(model.build(c, q, motor=m), h)
        assert math.isclose(pj, pp, rel_tol=1e-9), (c, q, h, m, pj, pp)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
