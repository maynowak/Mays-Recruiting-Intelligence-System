# RIS-COGNITO-JOBSEARCH-CONFIRMATION-EMAIL-AUDIT-01

**Mode:** READ-ONLY · EVIDENCE-DRIVEN
**Date:** 2026-10-23
**Status:** INCONCLUSIVE

## Executive Summary
User `info@mays-job-matcher.app` exists in Jobsearch User Pool `eu-central-1_ZURSMpD2O` with status UNCONFIRMED. SignUp event confirms Cognito generated verification code and attempted EMAIL delivery. No delivery confirmation evidence found. Email sending configuration uses COGNITO_DEFAULT. SES identity `info@mays-job-matcher.app` verified, domain `mays-job-matcher.app` verification PENDING. SES quota shows 1 email sent in last 24h. Root cause not conclusively proven with available read-only evidence.

## Confirmed User Evidence
- User Pool ID: eu-central-1_ZURSMpD2O
- Username/Email: info@mays-job-matcher.app
- UserSub: 63e45812-70e1-708e-909e-3e37ee6d189c
- UserCreateDate: 2026-10-23T10:17:11.880+02:00 UTC
- UserLastModifiedDate: 2026-10-23T10:17:11.880+02:00 UTC
- UserStatus: UNCONFIRMED
- Enabled: true
- email_verified: false

## AWS Live Configuration
- EmailSendingAccount: COGNITO_DEFAULT
- AutoVerifiedAttributes: [email]
- UsernameAttributes: [email]
- EmailVerificationSubject: Verify your email for Mays Jobsearch
- EmailVerificationMessage: Your verification code is {####}
- VerificationMessageTemplate.DefaultEmailOption: CONFIRM_WITH_CODE
- AdminCreateUserConfig.AllowAdminCreateUserOnly: false
- LambdaConfig: {}

## Terraform vs AWS
Terraform not managing this pool. Pool created via AWS CLI. Configuration matches expected email required, auto verification, self-registration enabled.

## Email Sending Configuration
- Cognito uses COGNITO_DEFAULT → SES managed by Cognito
- SES Identities:
  - info@mays-job-matcher.app : VerificationStatus Success
  - mays-job-matcher.app : VerificationStatus Pending
- SES Send Quota eu-central-1: Max24HourSend 200, SentLast24Hours 1
- No SES sandbox restriction observed.

## Available Delivery Evidence
CloudTrail SignUp event 2026-10-23T08:17:12Z
- clientId: 5hb3f6dj5ialg77jf4blur9g6g
- userSub: 63e45812-70e1-708e-909e-3e37ee6d189c
- responseElements.codeDeliveryDetails:
  - destination: HIDDEN
  - deliveryMedium: EMAIL
  - attributeName: email
- userConfirmed: false

No CloudTrail SES SendRawEmail events found in lookup window.
No CloudWatch Logs evidence inspected.

## Timeline
2026-10-23T10:17:11+02:00 UserCreateDate
2026-10-23T08:17:12Z CloudTrail SignUp event → code delivery attempted

## Root Cause Assessment
| Hypothese | Evidence | Bewertung |
|---|---|---|
| Cognito-E-Mail-Konfiguration fehlerhaft | EmailSendingAccount COGNITO_DEFAULT, Template gesetzt | RULED OUT |
| Versandlimit erreicht | SentLast24Hours 1 / Max200 | RULED OUT |
| SES-Konfiguration problematisch | Domain verification Pending, Email identity Success | OPEN |
| Versandversuch fehlgeschlagen | SignUp zeigt codeDeliveryDetails, no error | CONFIRMED attempt, delivery not confirmed |
| E-Mail zugestellt, aber nicht sichtbar | Keine Zustellbelege | OPEN |
| Frontend fehlerhaft | SignUp via CloudTrail, kein Frontend Log | RULED OUT |

## Evidence Gaps
- Keine SES Send/Bounce/Delivery Logs eingesehen
- Kein CloudWatch Logs Insights zu SES/Cognito
- Kein SQS DLQ Evidence
- Kein Nachweis über tatsächliche Zustellung an info@mays-job-matcher.app
- Domain Verification Pending könnte SPF/DKIM beeinflussen

## Minimal Corrective Action
1. Freigabe für read-only SES Event Publishing prüfen
2. SES Configuration Set mit SNS Notification für Bounces/Complaints aktivieren
3. Domain mays-job-matcher.app Verification abschließen
4. E-Mail-Inbox prüfen inkl. Spam/Junk
5. ResendConfirmationCode mit Freigabe testen

Status: INCONCLUSIVE – Ursache nicht belegbar mit aktuellem Read-Only Umfang.
