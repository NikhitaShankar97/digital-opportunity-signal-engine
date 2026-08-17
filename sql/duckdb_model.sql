CREATE OR REPLACE TABLE company_signals AS
SELECT *,
       CASE WHEN record_status = 'complete' THEN TRUE ELSE FALSE END AS is_score_eligible
FROM read_csv_auto('data/raw/similarweb_observations.csv', header = true);

