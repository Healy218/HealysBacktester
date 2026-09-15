# V7 observed-empty stock capture years

Source: completed receipts under `nn_meta/data_v7/base-20260915r4/stock_1m`,
inspected September 15, 2026. Each listed symbol/year has two empty captures:
raw and all-adjusted. These are unclassified provider responses, not confirmed
missing eligible history. Listing dates, former roots and coverage still need
validation. No symbol was empty across all six requested years.

- Research reference: 449 symbols in [plain ticker list](../specs/v7-tickers-20260915.txt),
  exported from the frozen plan's `plan.catalog.symbols`.
- Fetch scope: 452 literal roots. Add SQ/FI/BITF; fetch BRK.B in place of BRKB.
- Empty: 270/5,424 captures (4.98%), representing 135 symbol/year pairs
  across 62/452 fetch symbols (13.72%).
- At least one nonempty year: all 452 fetch symbols. Partial-year and
  minute-level gaps have not been audited across this full inventory.

| Fetch symbol | Years returning zero rows in both price bases |
|---|---|
| ABVX | 2021, 2022 |
| ALAB | 2021, 2022, 2023 |
| AMDL | 2021, 2022, 2023 |
| AMPX | 2021 |
| APLD | 2021 |
| ARM | 2021, 2022 |
| ASST | 2021, 2022 |
| BITX | 2021, 2022 |
| BMNR | 2021, 2022, 2023, 2024 |
| BTDR | 2021, 2022 |
| BULL | 2021, 2022, 2023, 2024 |
| CAVA | 2021, 2022 |
| CEG | 2021 |
| CONL | 2021 |
| CORZ | 2021, 2023 |
| CRCL | 2021, 2022, 2023, 2024 |
| CRDO | 2021 |
| CRWV | 2021, 2022, 2023, 2024 |
| DJT | 2021, 2022, 2023 |
| ELV | 2021 |
| ETHA | 2021, 2022, 2023 |
| ETHE | 2021, 2022, 2023 |
| ETHU | 2021, 2022, 2023 |
| FI | 2022, 2026 |
| FIG | 2021 |
| FISV | 2024 |
| FLY | 2022, 2023, 2024 |
| GEV | 2021, 2022, 2023 |
| GLXY | 2021, 2022, 2023, 2024 |
| IBIT | 2021 |
| KVUE | 2021, 2022 |
| LUNR | 2021, 2022 |
| MBLY | 2021 |
| MSTU | 2021, 2022, 2023 |
| MSTX | 2021, 2022, 2023 |
| MULL | 2021, 2022, 2023 |
| NBIS | 2021, 2022, 2023 |
| NNE | 2021, 2022, 2023 |
| NVDL | 2021 |
| OKLO | 2021, 2022, 2023 |
| PENG | 2021, 2022, 2023 |
| POET | 2021 |
| QBTS | 2021 |
| RDDT | 2021, 2022, 2023 |
| RGTI | 2021 |
| SMR | 2021 |
| SNDK | 2021, 2022, 2023, 2024 |
| SOC | 2021, 2022, 2023 |
| SOUN | 2021 |
| SQ | 2026 |
| SWTX | 2026 |
| SYM | 2021 |
| TEM | 2021, 2022, 2023 |
| TLN | 2021, 2022, 2023 |
| TSLL | 2021 |
| USAR | 2021, 2022, 2023, 2024 |
| UVIX | 2021 |
| VG | 2023, 2024 |
| WBA | 2026 |
| WBD | 2021 |
| X | 2026 |
| XYZ | 2021, 2022, 2023, 2024 |
