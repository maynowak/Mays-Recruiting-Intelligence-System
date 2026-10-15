# Security Test Plan

1. Client A cannot use APIProfile B – verify registry binding.
2. Credential A cannot access Tenant B – verify tenant isolation.
3. Revoked credentials remain revoked after restore.
4. Suspended users cannot access RIS.
5. Deleted users cannot access RIS.
6. Deleted applications cannot execute agents.
7. Deleted Cognito M2M clients cannot obtain tokens.
8. Previously issued tokens cannot bypass server-side suspension.
9. Backup restoration does not reactivate deleted users.
10. Backup restoration does not reactivate revoked credentials.
11. Partial deletion failures are recoverable.
12. Deletion operations are idempotent.
13. Audit logs do not expose secrets.
14. Data export respects tenant boundaries.
15. Legal retention exceptions do not permit unauthorized productive use.
