# <Agent> — Contracts

| Contract | Version | Source |
|---|---|---|
| WorkItem | 1.0 | agents/runtime/work_item.py |
| AgentOrder | 1.0 | agents/orders/agent_order.py |
| Transport V1 | 1 | agents/transport/order_transport.py |
| Result body | <version> | <path> |

Required messages: ORDER_DISPATCH (mays-orders → ris) and ORDER_RESULT
(ris → mays-orders). State correlation (`orderId`, `correlationId`,
`execution.workId`) and the HMAC basis (envelope `messageId`) explicitly.
