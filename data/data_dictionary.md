# Data dictionary

All business metrics are manually transcribed from Similarweb's public website experience. They are estimates, not first-party analytics and not paid API output.

| Field | Meaning | Unit / rule |
|---|---|---|
| `monthly_visits` | Estimated visits for the displayed month | Whole visits |
| `mom_change_pct` | Change from the previous month | Percentage; signed |
| `bounce_rate_pct` | Estimated single-page session rate | 0–100 |
| `pages_per_visit` | Estimated engagement depth | Positive decimal |
| `avg_visit_duration_seconds` | Average visit duration | Seconds |
| `organic_search_share_pct` | Share of desktop visits attributed to organic search | 0–100 |
| `leading_channel` | Highest-ranked publicly displayed acquisition channel | Text |
| `leading_channel_share_pct` | Share of desktop visits for that leading channel | 0–100; not assumed comparable in quality across channel types |
| `organic_search_within_search_pct` | Organic portion of search traffic | 0–100 |
| `record_status` | Intake readiness | `complete` or a documented pending reason |

Geography and marketing-channel observations are explicitly desktop-only. Missing public values remain null.
