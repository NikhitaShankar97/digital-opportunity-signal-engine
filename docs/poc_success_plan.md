# POC success plan

| Outcome | Measure | POC target | Evidence |
|---|---|---:|---|
| Faster screening | Time to produce a peer comparison | Under 5 minutes after a valid input file | Pipeline run log |
| Consistent decisions | Same input produces same score and explanation | 100% | Automated tests |
| Transparent logic | Scored companies with traceable components | 100% | YAML rules and output fields |
| Data trust | Invalid or incomplete records silently published | 0 | Validation report |
| Analyst usefulness | Pilot users who say the signal helps choose next research | At least 4 of 5 | Feedback survey |
| Integration readiness | Downstream app reads standardized output | Demonstrated | Streamlit data contract |

## POC exit decision

Proceed to a licensed production pilot if analysts find the ranking useful, technical owners approve the delivery contract, and automated refresh can meet agreed freshness and reliability expectations.

