# RIS-R08-SECURITY-05A — Root Cause

The canonical paths are `lambda/handler.py:_enqueue_agent_work`,
`_process_work_item`, and `agents/runtime/pipeline.py:process_record`.
Worker `_register_processing` previously recreated a missing WorkItem with a
conditional `PutItem`, but no durable erasure state was consulted. The
existing `gsi-user` cancellation query is eventually consistent and is not an
admission boundary. The producer and worker can therefore race erasure.

Scope remains RIS only; SQS/DynamoDB/external-agent atomicity is not claimed.
