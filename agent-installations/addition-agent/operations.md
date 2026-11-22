# Addition Agent — Operations

- No dedicated infrastructure; follows the ats-agent transport.
- Health: dispatch/result queues and DLQs must be 0; work row `COMPLETED` with `orderResultDelivery=SENT`; Orders `processing=COMPLETED` with `sum=42`.
- Live baseline (2026-11-18): addition order `ord_71c3c1003ce9492d5acbb601` / work `work-efc33036efaece37`, sum 42; ATS regression order `ord_ac7755a61dd172ed0a0046a9`, body 2.0.
- Deactivate by stopping traffic; do not remove shared queues/Lambdas.
