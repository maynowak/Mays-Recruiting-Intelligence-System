# RIS-COGNITO-CLASSIC-BRANDING-02

**Status:** ANALYZE → READY
**Date:** 2026-10-22
**Scope:** Cognito Classic Hosted UI Branding for Mays-Jobsearch

## 1. Existing UI Customization
User Pool eu-central-1_ojbmoiYGM, Client 7ldhihlpdgsgcl3puvu4oi7ksv
`get-ui-customization` returns empty.
No CSS, logo, or branding currently applied.
ManagedLoginVersion: 1 → Classic Hosted UI

## 2. Branding Concept
Mays-Jobsearch identity:
- Navy background #0A1931
- Violet primary buttons #7B2CBF
- Turquoise accents #00C9A7
- Modern typography: System font stack
- Accessible contrast WCAG AA

Target elements:
- Body background
- Primary buttons
- Links
- Input focus states
- Header/footer

## 3. Classic UI CSS Customization
Cognito Classic Hosted UI supports CSS via `aws_cognito_user_pool_ui_customization`.
Supported selectors limited.

Example CSS:
```
body { background-color:#0A1931 !important; color:#E6E8F0 !important; }
a { color:#00C9A7 !important; }
input[type="submit"], button { background-color:#7B2CBF !important; color:#fff !important; border:none !important; }
input:focus { border-color:#00C9A7 !important; outline-color:#00C9A7 !important; }
```

## 4. Preservation
User Pool, App Client, domain, users, OAuth callbacks unchanged.
No pool replacement, no paid resources.

## 5. Preview & Verification
Preview via Cognito Hosted UI URL:
https://auth.mays-job-matcher.app/login?client_id=7ldhihlpdgsgcl3puvu4oi7ksv&response_type=code&redirect_uri=...

Verification points:
- Login page
- Signup page
- Forgot password
- Mobile layout
- OAuth redirects

## 6. Limitations Classic UI
- Limited CSS selectors
- No full HTML control
- Logo upload via separate `aws_cognito_user_pool_ui_customization` with `CSS` and optional `ImageFile`
- No JavaScript injection
- Branding resets on major AWS UI updates

## 7. Safe Implementation Options
1. Apply via Terraform `aws_cognito_user_pool_ui_customization` resource with CSS string.
2. Apply via AWS CLI `set-ui-customization`.
3. Preview in dev environment first.

No destructive changes.

Status GREEN for design, deployment pending approval.
