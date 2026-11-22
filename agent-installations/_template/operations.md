# <Agent> — Operations

- Activation: approved plan, secret verified, synthetic profile/entitlement,
  isolated canary.
- Health: queues/DLQs 0; work `COMPLETED`/`SENT`; Orders `processing=COMPLETED`;
  owner 200 / foreign 404.
- Deactivation: stop traffic, revoke test data, reuse shared transport teardown.
- Recovery: fix secret/profile/entitlement, redrive from DLQ; recycle Lambdas
  after secret changes.
