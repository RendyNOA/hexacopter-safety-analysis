"""Fault trees for the top event TE-1 "Loss of controlled flight".

Level 1  TE-1 Loss of controlled flight (the drone can no longer be flown to a
         controlled landing) -> can hit people, start a fire, destroy the drone.
Level 2  Flight computing lost | Attitude sensing lost | Propulsion power lost |
         Thrust / control authority lost
Level 3  Parts-count failure rates (FMU, ESC) and open items (motor, propeller,
         battery, MEMS IMU) that still need supplier data.

Rotor-layout rules (from published controllability analyses, see docs/report.md):
  * Quad X              : losing any rotor -> loss of control.
  * Hexa PNPNPN (classic): losing any one rotor -> not fully controllable.
  * Hexa PPNNPN          : one failure of rotors 1-4 is tolerable, rotors 5-6 are
                           not; any double failure is counted as loss of control
                           (conservative). Credit requires SR-02 (failure detection
                           and control re-allocation) to be verified.
"""
from __future__ import annotations

from typing import Dict, Optional

from .fta import Event, Gate, Node, validate
from .partscount import assemblies, total

CONFIGS = {
    "quad_x": "Quadcopter X (4 rotors)",
    "hexa_pnpnpn": "Hexacopter, classic PNPNPN (6 rotors)",
    "hexa_ppnnpn": "Hexacopter, PPNNPN (6 rotors)",
}

PC_SOURCE = "MIL-HDBK-217F N2 parts count, ARW; BOM: {bom}"


def rates(quality: str = "commercial") -> Dict[str, float]:
    a = assemblies(quality)
    return {"FMU": total(a["FMU"]), "ESC": total(a["ESC"])}


def _channel(i: int, esc: float, motor: Optional[float], prop: Optional[float]) -> Gate:
    return Gate(f"CH{i}", f"Rotor {i} thrust lost", "OR", [
        Event(f"ESC{i}", f"ESC {i}", esc, PC_SOURCE.format(bom="Sapog reference ESC")),
        Event(f"MOT{i}", f"Motor {i}", motor, "OPEN OI-01" if motor is None else "user input"),
        Event(f"PRP{i}", f"Propeller {i}", prop, "OPEN OI-02" if prop is None else "user input"),
    ])


def build(config: str, quality: str = "commercial", motor: Optional[float] = None,
          prop: Optional[float] = None, battery: Optional[float] = None,
          imu: Optional[float] = None) -> Node:
    if config not in CONFIGS:
        raise ValueError(f"config must be one of {list(CONFIGS)}")
    r = rates(quality)
    n = 4 if config == "quad_x" else 6
    ch = [_channel(i, r["ESC"], motor, prop) for i in range(1, n + 1)]

    if config == "hexa_ppnnpn":
        thrust = Gate("G_THRUST", "Thrust / control authority lost", "OR", [
            ch[4], ch[5],
            Gate("G_TOL", "2 or more of the tolerable rotors 1-4 lost", "ATLEAST", ch[:4], k=2),
        ])
    else:
        thrust = Gate("G_THRUST", "Thrust / control authority lost", "OR", ch)

    top = Gate("TE1", "TE-1 Loss of controlled flight", "OR", [
        Gate("G_FCC", "Flight computing lost", "OR", [
            Event("FMU", "FMU board (Pixhawk FMUv3)", r["FMU"], PC_SOURCE.format(bom="Pixhawk FMUv3 REV D")),
        ]),
        Gate("G_ATT", "Attitude sensing lost", "OR", [
            Event("IMU", "IMU sensing (MEMS, redundant board)", imu, "OPEN OI-04/OI-05" if imu is None else "user input"),
        ]),
        Gate("G_PWR", "Propulsion power lost", "OR", [
            Event("BAT", "LiPo battery", battery, "OPEN OI-03" if battery is None else "user input"),
        ]),
        thrust,
    ])
    validate(top)
    return top
