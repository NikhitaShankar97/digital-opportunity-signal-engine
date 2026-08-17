CREATE OR REPLACE TABLE analytics.company_signals AS
SELECT
  lower(domain) AS domain,
  observation_month,
  CAST(monthly_visits AS DOUBLE) AS monthly_visits,
  CAST(mom_change_pct AS DOUBLE) AS mom_change_pct,
  CAST(bounce_rate_pct AS DOUBLE) AS bounce_rate_pct,
  CAST(pages_per_visit AS DOUBLE) AS pages_per_visit,
  CAST(avg_visit_duration_seconds AS INT) AS avg_visit_duration_seconds,
  record_status,
  current_timestamp() AS processed_at
FROM read_files('/Volumes/similarweb/raw/observations/', format => 'csv', header => true);

