# Dated sectors and training inputs — September 16, 2026

Active V7 remains the 593-ticker /591-security no-OTC study. No ranking, strategy,
feature-column count, stock-price source or full-launch condition changed.

## Dated sectors

Forty-eight missing company-reference queries were captured with shared quota
accounting. All 339,640 eligible security sessions now have a frozen record:
317,561 classified, 22,079 unknown, zero without a prior identity reference.
Unknowns primarily reflect missing SIC in foreign-company metadata; they remain
visible, not filled with today's classifications. The nine sector fields remain.

The deterministic taxonomy uses dated security type, coarse SIC groups and an
explicit crypto business phrase. Broad-index fund names are distinguished from
other funds. This V7 taxonomy differs from the old hand-picked V6 symbol map;
it is a research grouping, not GICS. Rules and source links are embedded in
`nn_meta/v7/sectors.py` and the frozen store's `policy.json`.

References are provider historical reconstructions. Massive describes its dated
company endpoint as returning details as of the query date:
[provider description](https://www.massive.com/blog/announcing-our-new-point-in-time-company-details-api).
SIC definitions come from the [SEC code list](https://www.sec.gov/search-filings/standard-industrial-classification-sic-code-list).
These sources support dated classification inputs; they do not establish original
publication vintages for prices or dividends.

Mappings join on composite FIGI, become usable strictly after the reference day,
and remain explicit per eligible session. A missing newer classification is
retained as unknown. Same-identity/date GPS/GAP alias metadata is reconciled only
when one lacks classification and the other supplies it; conflicting populated
classifications raise. Full-row construction now consumes these dated records
with provenance and rejects other identities, future references and absent sessions.

Store: `nn_meta/validation/v7-sectors-20260916-final`; receipt bound in the active
manifest. Earlier component output remains historical after loader changes.

## Training preprocessing

Fold selection spans immutable factorized shards, enforces exact integer clocks
and global row uniqueness, and purges through settlement. Resumption verifies
source order, fold, calendar, code, source payloads and selected-artifact hashes.

Preprocessing merges missingness-aware float64 moments using bounded batches.
Entirely unobserved training features remain inactive even when validation supplies
a value. Exact 1%/99% return quantiles use a separate on-disk partitioned vector;
return weights normalize by their training mean. No validation observations fit
these quantities. Finite checks reject infinities and float32 overflow. Default
100 GiB disk reserve is checked before allocating the dense target vector.
The new CLI uses the declared three expanding folds and the repository artifact
disk. This prepares inputs; it does not implement model selection or full training.

Dense-reference numerical tests, missingness/leakage checks, sector chronology,
ticker reuse, row provenance and exact resume/mutation checks passed. Full suite: **1,777 tests +18 subtests passed**, 18 warnings, 82.59s;
`/tmp/v7-sectors-training-20260916-final-tests.log`. Includes preserved unrelated
V6 working-tree changes. Full-history LightGBM binned memory, integrated resource/recovery and
V6 coexistence are still unmeasured. No readiness gate is waived.

Readiness `nn_meta/validation/v7-readiness-20260916-sectors.json` passes three
input/inventory gates and refuses the eight substantive missing stages.
