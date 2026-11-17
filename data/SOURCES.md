# Data sources

| File | Source | Version |
|---|---|---|
| bom_fmu_v3.csv | Pixhawk Hardware repo, `FMUv3_REV_D/BOM/Bill of Materials-FMU3_REV_D(FMU3_REV_D).xlsx` | commit bbf3de5 (2022-05-18), CC BY-SA 3.0 |
| bom_esc_sapog.csv | Pixhawk Hardware repo, `sapog_reference_hardware/sapog_reference_hardware.sch` (Eagle XML, parts list) | commit bbf3de5, CC BY-SA 3.0 |
| mil217f_partscount_ARW.csv | MIL-HDBK-217F Notice 2, Appendix A (parts count), pages A-2 to A-11 — each row has its page in the `handbook_page` column | First drafted from RAMSTK v0.19.0 (commit 68c1112); checked against the handbook on 2026-11-17: 11 rows matched, 10 rows and 1 quality factor corrected (RAMSTK carries pre-Notice-2 values for passive parts) |
| π_Q commercial microcircuits = 10 | MIL-HDBK-217F Notice 2, page A-4 ("Other commercial or unknown screening levels") | — |

Environment index used: ARW (Airborne, Rotary Winged) = 10th column of the handbook's
environment order GB, GF, GM, NS, NU, AIC, AIF, AUC, AUF, ARW, SF, MF, ML, CL.
