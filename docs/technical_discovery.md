# Technical discovery questionnaire

## Data and entitlement

- Which Similarweb datasets and domains are licensed?
- Are Batch API responses or managed Data Feeds preferred?
- What history, geography, device, and granularity are entitled?
- Which identifiers connect domains to portfolio companies and peer groups?

## Platform and integration

- Is the target environment S3, Databricks, Snowflake, or another warehouse?
- What orchestration, catalog, and observability tools are standard?
- How does the analyst application consume curated data?
- What refresh deadline and recovery-time expectation apply?

## Governance and reliability

- Who owns the raw feed, semantic definitions, and scoring configuration?
- Which users may see company-level signals?
- How are late, missing, duplicated, or schema-changed deliveries handled?
- What audit trail is required for score changes and analyst overrides?

## Proposed failure behavior

The pipeline quarantines invalid rows, retains the last successful published snapshot, exposes freshness and quality flags, and never replaces a missing value with an invented estimate.

