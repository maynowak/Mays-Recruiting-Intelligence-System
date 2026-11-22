# Addition Agent — Tests

```powershell
python -m pytest tests/test_worker_pipeline.py tests/test_mo_dispatch_handoff.py -q
```

Live: dispatch `addition_agent` / `math.add` with `{left:17,right:25}`; expect work `COMPLETED` and result `sum=42`.
