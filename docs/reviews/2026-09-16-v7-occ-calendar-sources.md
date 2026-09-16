# V7 official calendar source continuation

This records source discovery after the model-runner checkpoint `8097c08`.
These findings do not seal a settlement calendar or pass a readiness stage.

## Sources located and read

OCC's dated annual notices provide the missing year-specific tables:

| Year | Original OCC notice | Publication date | Detail |
|---|---|---|---|
| 2022 | [49729](https://infomemo.theocc.com/infomemos?number=49729) | December 9, 2021 | Updated annual notice includes June 20 Juneteenth; the earlier 49648 omits it. |
| 2023 | [51460](https://infomemo.theocc.com/infomemos?number=51460) | November 30, 2022 | Veterans Day is listed as Saturday November 11, not Friday November 10. |
| 2024 | [53701](https://infomemo.theocc.com/infomemos?number=53701) | December 7, 2023 | Separates OCC closure dates from October 14 / November 11 banking holidays. |
| 2025 | [55737](https://infomemo.theocc.com/infomemos?number=55737) | December 18, 2024 | Annual holiday and monthly expiration schedule; must incorporate the later mourning notice. |
| 2026 | [57897](https://infomemo.theocc.com/infomemos?number=57897) | December 12, 2025 | July 3 OCC closure; October 12 / November 11 banking holidays; June monthly expiry June 18. |

The [December 30, 2024 OCC notice 55826](https://infomemo.theocc.com/infomemos?number=55826)
explicitly treats January 9, 2025 as an OCC money-settlement/exercise business day
while equity exchanges are closed. It describes DTC/NSCC normal business and
specifies January 8 closing reference prices for January 9-expiring equity
options, with January 10 settlement. This is a promising primary source for the
previously identified exception; the memo still needs an archived original copy.

[OCC 54580, May 14, 2024](https://infomemo.theocc.com/infomemos?number=54580)
is the final updated T+1 conversion notice: the regulatory process had concluded;
T+2 through May 24 close, T+1 before May 28 open. Unlike an earlier prospective
announcement, it states that the rule changes will be effective May 28.

The FINRA [January 3, 2025 contrary-cutoff notice](https://www.finra.org/rules-guidance/notices/information-notice-20250103)
was successfully captured as original HTML. It concerns exercise instructions;
it must not be substituted for a complete securities settlement calendar.

## Acquisition result and limits

Exact request list:
`nn_meta/validation/v7-occ-calendar-requests-20260916.json`.
Output: `nn_meta/data_v7/occ-calendars-20260916`.

Sandbox networking failed; the authorized network retry completed. All seven
OCC direct downloads returned **HTTP 403**. A diagnostic confirmed Cloudflare's
browser challenge, not an empty or nonexistent PDF. No challenge was solved or
bypassed. The available browser-control tool reported no browser. The web reader
could retrieve the documents' text, but those views are not claimed as locally
captured original PDF bytes. Do not mark the corresponding raw receipts complete.

The eighth request, `finra-carter-contrary-cutoff`, captured **91,562 HTML bytes**
with an immutable receipt. Every capture attempt has ended; no job is left running.
The rejected OCC partial directories remain incomplete evidence.

Next steps: obtain accessible official copies or permitted archival source
captures, inspect the actual PDF tables/footnotes, resolve the 2023 FINRA/DTCC
conflict, and bind the resulting dated calendar to physical replay. OCC closure,
U.S. banking holiday and NSCC securities settlement service are distinct; do not
infer all three from one heading. Keep the 2025 special closure and 2022
Juneteenth amendment explicit. Calendar admission remains unfinished.
