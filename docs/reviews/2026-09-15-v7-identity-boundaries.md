# Reviewed V7 trading-identity boundaries

Seven dated Massive responses have no composite FIGI. The assignments below
are **inferences from primary-source trading-effective dates**, bound to the
old identity in the preceding captured monthly master. They fill only the
listed missing dates; they do not merge old and successor securities.

| Root | Missing dates assigned to old identity | First successor trading date | Evidence |
|---|---|---|---|
| AESI | 2023-10-02 | 2023-10-03 | [Old Atlas 8-K](https://www.sec.gov/Archives/edgar/data/1910950/000119312523249499/d451973d8k.htm) states that old shares were to be withdrawn before the October 3 opening. The legal transaction closed October 2; that is distinct from the trading change. |
| NUSI | 2024-11-08 | 2024-11-11 | [OCC memo 55511](https://infomemo.theocc.com/infomemos?number=55511), dated November 8, gives the effective date before the November 11 opening. Old option contracts became NUSI1; the new fund reused NUSI. |
| BEPC | 2024-12-20, 23, 24, 26, 27 | 2024-12-30 | [Successor issuer filing](https://www.sec.gov/Archives/edgar/data/1791863/000119312524285923/d795477d8k12b.htm), signed December 27, specifies the anticipated NYSE trading change on December 30. Captured Alpaca name-change evidence and the new Massive FIGI on December 30 agree. |

All supporting disclosures preceded the relevant month-end universe decision.
These facts are used to classify observed liquidity history, not as future
fundamental features. The old FIGI is taken from a verified monthly master;
no FIGI is inferred from a name, price continuity or a static alias table.

Additional corroboration for BEPC: [CDCC notice 2024-168](https://cdcc.ca/u_avis_en/168-24_en.pdf)
specifies the December 30 Canadian contract/CUSIP change. The NYSE assignment
above relies on the issuer's US filing, with December 30 confirmed by the dated
provider transition. Legal completion dates and trading-effective dates must
not be treated as interchangeable.

The machine-readable declaration is generated separately with hashes of this
review and the captured monthly anchors. The loader rejects existing identities,
changed evidence, dates outside the reviewed interval and mismatched anchors.
