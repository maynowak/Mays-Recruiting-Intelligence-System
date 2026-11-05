# RIS-R08-SECURITY-05D — Runtime Wiring

`lambda/handler.py:_enqueue_agent_work` now requires verified user/tenant
context and a configured transactional WorkItems table. `_process_work_item`
always passes the table and `require_subject_fence=True` to `process_record`.
No production callback or optional local ledger is used as the fence.
Missing configuration fails closed instead of queueing unprotected work.
