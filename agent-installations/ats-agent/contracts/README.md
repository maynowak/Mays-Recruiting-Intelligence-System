# ATS Agent — Contracts

Version matrix:

| Contract | Version | Source |
|---|---|---|
| WorkItem | 1.0 | `agents/runtime/work_item.py` |
| AgentOrder | 1.0 | `agents/orders/agent_order.py` |
| Transport V1 | 1 | `agents/transport/order_transport.py` |
| ATS upstream contract | 1.2 | `docs/contracts/JOBSEARCH-ATS-ANALYSIS-V1.md` |
| ATSAnalysisResultBody | 2.0 | `docs/contracts/ATS-ANALYSIS-RESULT-BODY-V1.md` |

Required transport messages:

- `ORDER_DISPATCH`: `mays-orders` → `ris`; requires `orderId`, `correlationId`, inline `payload`, `execution.workId`, `identity.contextRef` = `apiProfileId`.
- `ORDER_RESULT`: `ris` → `mays-orders`; HMAC-SHA256 over the **envelope `messageId`** and the exact body; `serviceSignature` SQS attribute.

The result body is the strict V2 projection; `analysis.metadata.titleTokens` is deliberately absent because the transport secret scan rejects `token` keys. Do not re-add it without changing the scan contract.

Order correlation:

- `correlationId` = `agentOrder.metadata.requestId`.
- `expectedWorkId` on the order must equal `execution.workId`.
- Orders result correlation is re-checked against the stored order; mismatches are permanent rejects.
