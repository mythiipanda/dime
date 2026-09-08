# SPEC-004: Percentile columns on leaders

Problem: analysts read percentiles, not raw ranks. CTG and dunksandthrees
both dual-layer every cell. Our tables show rank alone.

Change: leaders rows gain a percentile derived from rank over row count.
No warehouse migration. Computed at read time.

Surface: dual-layer cells show value plus tiny percentile. Heat toggle
already scales by column max.

Verify: eval asserts percentile sits between 0 and 100 for rank 1 and
last. Screenshot shows the second layer.
