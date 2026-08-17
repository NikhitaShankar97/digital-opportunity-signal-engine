# Free-only implementation choices

## Recommended for this POC

1. Run the full pipeline locally with DuckDB, Python, and Streamlit.
2. Use Databricks Free Edition only if the account offers a permanently free workspace without paid compute activation.
3. Deploy the app on Streamlit Community Cloud from a public GitHub repository.
4. Keep S3 optional. AWS account eligibility, payment-method requirements, and overage exposure can vary; do not create a bucket solely to complete this four-hour POC.

## Credential rules

- Never place passwords, tokens, or AWS keys in code, CSV files, screenshots, or chat.
- Use local credential configuration, environment variables, or Streamlit secrets.
- `.env` and `.streamlit/secrets.toml` are excluded through `.gitignore`.
- Do not claim paid Similarweb API access. Production examples assume a future licensed entitlement.

