# RIS-DEV2-TEST-IDENTITY-02A — Secret-Free Human Identity Design

**Result:** **DESIGN PASS / OFFLINE VALIDATION NEXT / APPLY BLOCKED**

## 1. Decision

`ris-dev2` now opts out of provisioning a managed M2M client and resource
server. The existing managed Cognito behavior remains the default for every
other environment.

The DEV2 Human client remains a public client (`generate_secret = false`) with
Authorization Code + PKCE and the explicit localhost callback/logout URLs.

## 2. Minimal implementation

Added three root variables:

- `identity_m2m_enabled` — default `true`, preserving existing environments;
- `identity_m2m_fallback_issuer` — non-secret issuer reference;
- `identity_m2m_fallback_client_id` — non-secret audience reference.

The DEV2 overlay sets `identity_m2m_enabled = false` and retains the existing
external M2M issuer/audience only for the already-deployed machine authorizer.
It does not create a new M2M client or secret.

The Cognito module conditionally omits only its managed M2M resource server and
M2M client. Its Human pool/client/groups/prefix-domain behavior is unchanged.

## 3. API compatibility boundary

The existing M2M authorizer and `/v1/m2m/agents/{agentId}/execute` route remain
declared so the plan has no destructive route/authorizer removal. In DEV2
Human-only mode, that preserved authorizer continues to reference the existing
external M2M issuer/audience. No new managed M2M resource is created and no
Human token is accepted by that machine authorizer.

The Human authorizer alone switches to the new DEV2 managed pool. All Human
routes—including Profile, CV and ApplicationV1 routes—continue to use the
existing Human authorizer resource.

## 4. Environment isolation

`identity_m2m_enabled` defaults to `true`; no general M2M path is removed for
other managed environments. External identity mode remains reference-only and
unchanged. No production module is split or replaced.

No generated secret is read, printed, committed or placed in the overlay.
Fallback values are identifiers/issuer URLs only.

## 5. Apply boundary

This phase changes Terraform configuration only. It does not create a pool,
client, user, token, authorizer, partner binding or credential. The prior
`RIS-DEV2-TEST-IDENTITY-01` plan is marked `SUPERSEDED — DO NOT APPLY`.
