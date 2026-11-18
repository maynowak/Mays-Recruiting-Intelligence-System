# <Agent> — Tests

Local:

```powershell
<pytest command>
```

Live (approved test scope only):

1. Create the agent order with synthetic data.
2. Work item `COMPLETED` and `orderResultDelivery=SENT`.
3. Orders `processing=COMPLETED`; expected result fields.
4. Owner 200 / foreign 404 / invalid token 401.
5. Duplicate dispatch no second write.
6. Queues and DLQs return to 0.
