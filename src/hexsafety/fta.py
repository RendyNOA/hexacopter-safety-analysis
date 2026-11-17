"""Minimal fault tree engine.

Basic events fail independently with a constant failure rate (exponential model,
the "useful life" part of the bathtub curve):

    P(event has failed by time t) = 1 - exp(-lambda * t)

Gates:
    OR       - output fails if any input fails
    AND      - output fails if all inputs fail
    ATLEAST  - output fails if at least k of the n inputs fail (k-out-of-n)

The probability calculation is exact as long as no basic event appears twice in
the tree (true for every tree in this project; checked by `validate`).
"""
from __future__ import annotations

import itertools
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Union

PER_MILLION_HOURS = 1e-6


@dataclass
class Event:
    """Basic event. `rate_fpmh` = failures per 10^6 hours; None = not quantified."""

    id: str
    label: str
    rate_fpmh: float | None
    source: str = ""

    def prob(self, hours: float) -> float:
        if self.rate_fpmh is None:
            return 0.0
        return 1.0 - math.exp(-self.rate_fpmh * PER_MILLION_HOURS * hours)


@dataclass
class Gate:
    id: str
    label: str
    kind: str  # "OR", "AND", "ATLEAST"
    inputs: List["Node"] = field(default_factory=list)
    k: int = 1  # only for ATLEAST

    def __post_init__(self) -> None:
        if self.kind not in {"OR", "AND", "ATLEAST"}:
            raise ValueError(f"unknown gate kind {self.kind}")
        if self.kind == "ATLEAST" and not 1 <= self.k <= len(self.inputs):
            raise ValueError("ATLEAST gate needs 1 <= k <= number of inputs")


Node = Union[Event, Gate]


def basic_events(node: Node) -> List[Event]:
    if isinstance(node, Event):
        return [node]
    out: List[Event] = []
    for child in node.inputs:
        out.extend(basic_events(child))
    return out


def validate(top: Node) -> None:
    ids = [e.id for e in basic_events(top)]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"repeated basic events break the exact calculation: {dupes}")


def _atleast(probs: Sequence[float], k: int) -> float:
    """P(at least k of n independent events occur), by dynamic programming."""
    dist = [1.0] + [0.0] * len(probs)  # dist[j] = P(exactly j occurred)
    for p in probs:
        for j in range(len(dist) - 1, 0, -1):
            dist[j] = dist[j] * (1 - p) + dist[j - 1] * p
        dist[0] *= 1 - p
    return sum(dist[k:])


def probability(node: Node, hours: float, override: Dict[str, float] | None = None) -> float:
    """Exact top-event probability at time `hours` (independent, non-repeated events)."""
    if isinstance(node, Event):
        if override and node.id in override:
            return override[node.id]
        return node.prob(hours)
    ps = [probability(c, hours, override) for c in node.inputs]
    if node.kind == "OR":
        q = 1.0
        for p in ps:
            q *= 1 - p
        return 1 - q
    if node.kind == "AND":
        q = 1.0
        for p in ps:
            q *= p
        return q
    return _atleast(ps, node.k)


def minimal_cut_sets(node: Node) -> List[frozenset]:
    """Minimal cut sets (sets of basic events whose joint failure causes the top event)."""
    if isinstance(node, Event):
        return [frozenset([node.id])]
    child_sets = [minimal_cut_sets(c) for c in node.inputs]
    if node.kind == "OR":
        combined = [cs for sets in child_sets for cs in sets]
    else:
        k = len(node.inputs) if node.kind == "AND" else node.k
        combined = []
        for group in itertools.combinations(child_sets, k):
            for choice in itertools.product(*group):
                combined.append(frozenset().union(*choice))
    unique = sorted(set(combined), key=lambda s: (len(s), sorted(s)))
    return [s for s in unique if not any(o < s for o in unique)]


def importance(node: Node, hours: float) -> Dict[str, Dict[str, float]]:
    """Birnbaum and Fussell-Vesely importance for every quantified basic event."""
    top = probability(node, hours)
    out: Dict[str, Dict[str, float]] = {}
    for ev in basic_events(node):
        if ev.rate_fpmh is None:
            continue
        p1 = probability(node, hours, {ev.id: 1.0})
        p0 = probability(node, hours, {ev.id: 0.0})
        out[ev.id] = {
            "birnbaum": p1 - p0,
            "fussell_vesely": (top - p0) / top if top > 0 else 0.0,
        }
    return out


def monte_carlo(node: Node, hours: float, n: int = 200_000, seed: int = 7) -> float:
    """Independent check of `probability` by sampling failure times."""
    rng = random.Random(seed)
    events = basic_events(node)

    def failed(nd: Node, state: Dict[str, bool]) -> bool:
        if isinstance(nd, Event):
            return state[nd.id]
        res = [failed(c, state) for c in nd.inputs]
        if nd.kind == "OR":
            return any(res)
        if nd.kind == "AND":
            return all(res)
        return sum(res) >= nd.k

    hits = 0
    for _ in range(n):
        state = {}
        for ev in events:
            if ev.rate_fpmh is None or ev.rate_fpmh == 0:
                state[ev.id] = False
            else:
                state[ev.id] = rng.expovariate(ev.rate_fpmh * PER_MILLION_HOURS) <= hours
        hits += failed(node, state)
    return hits / n


def to_dict(node: Node) -> dict:
    """Serialise the tree (used by the browser demo)."""
    if isinstance(node, Event):
        return {"type": "event", "id": node.id, "label": node.label,
                "rate_fpmh": node.rate_fpmh, "source": node.source}
    return {"type": "gate", "id": node.id, "label": node.label, "kind": node.kind,
            "k": node.k, "inputs": [to_dict(c) for c in node.inputs]}
