# Data contract

## Contract boundary

The application consumes `company_signals`, not screenshots or presentation files. The POC adapter is CSV; a production adapter can use a licensed Similarweb API or managed feed without changing the output contract.

## Grain and key

One row per `domain` + `observation_month` + `geography` + `device_scope`.

## Required fields

| Field | Type | Rule |
|---|---|---|
| `domain` | string | Lowercase registered domain; non-null |
| `observation_month` | YYYY-MM | Non-null |
| `collection_date` | date | Non-null and not before observation month |
| `monthly_visits` | number | Non-negative |
| `mom_change_pct` | number | Signed percentage |
| `bounce_rate_pct` | number | 0 through 100 |
| `pages_per_visit` | number | Greater than zero |
| `avg_visit_duration_seconds` | integer | Non-negative |
| `record_status` | string | Controlled value; only `complete` is score-eligible |

## Publication guarantees

- Duplicate business keys are rejected.
- Invalid percentages and negative counts are rejected.
- Missing public values remain null.
- Every output retains source URL, collection date, scope, and observation month.
- Score configuration is version-controlled and published with the output snapshot.

