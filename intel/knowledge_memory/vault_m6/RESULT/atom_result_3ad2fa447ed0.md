---
id: atom_result_3ad2fa447ed0
type: RESULT
visibility: PUBLIC
rights_status: LINK_ONLY
---

# AI_ENERGY_INFRA: is AI data center growth driving US electricity demand increase?

US electric power consumption per capita (World Bank EG.USE.ELEC.KH.PC) ranged 12393.4-13392.7 kWh/capita over 2010-2022 (no AI-specific attribution; series ends before the 2023+ AI data-center buildout). Separately, live-acquired evidence now connects: (1) global data centers consumed ~415 TWh in 2024 (1.5% of world electricity), growing ~12%/yr since 2017, with IEA naming AI as a primary but not sole driver (AI_ATTRIBUTION=PARTIAL); (2) IEA forecasts (not observations) of ~945 TWh by 2030 and ~1200 TWh by 2035; (3) a Jevons-paradox dynamic in general cloud computing (Google total energy +3.7x 2016-2022 despite near-optimal PUE), AI_ATTRIBUTION=INDIRECT; (4) ~130 GW stuck in PJM's interconnection queue with ~$3.5B estimated forgone savings, attributed jointly to data centers and electrification (AI_ATTRIBUTION=PARTIAL), framed as a generation/interconnection-queue shortage, not a transmission bottleneck. No source in this corpus gives a numeric AI-only (vs. general cloud/crypto) share of data center electricity demand.

## Related
- [[claim_1d9458f4e7e2cf69]]
- [[claim_5787125ab5f0110b]]
- [[claim_7f1bc452c4ffc128]]
- [[claim_afe7cc7b19317ee0]]
- [[claim_d170f52f567053e9]]
- [[series_67a90dc183bd74a1]]
- [[series_af37f1207e7ff042]]
- [[series_d018d1290acd5f20]]

## Sources
- event:evt_a6a4027d9878143d
- https://api.worldbank.org/v2/country/USA/indicator/EG.USE.ELEC.KH.PC?date=2010:2022&format=json&per_page=100
- https://arxiv.org/html/2411.11540v1
- https://gridlab.org/interconnection-bottlenecks-cost-pjm-customers-3-5-billion/
- https://www.iea.org/reports/energy-and-ai/executive-summary
