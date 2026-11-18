# Addition Agent — Contracts

- WorkItem 1.0, AgentOrder 1.0, Transport V1.
- Payload `{left:int, right:int}`; result body `{left,right,sum}` with numeric values.
- Same ORDER_DISPATCH / ORDER_RESULT transport as `ats-agent`; HMAC over the envelope `messageId`.
