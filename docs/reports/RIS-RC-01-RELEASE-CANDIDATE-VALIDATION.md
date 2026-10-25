# RIS-RC-01 – Release Candidate Integration & Verification

**Datum:** 2026-10-25
**Projekt:** ris-dev
**AWS-Account:** 240571105849
**Region:** eu-central-1
**Git:** main @ 392e27b

## Executive Summary
Release-Fähigkeit der permanenten Entwicklungsinstallation ris-dev wird auf Basis bestehender Evidence bewertet. Installer, Terraform-Verträge, Lambda-Packaging und Agent-Runtime sind dokumentiert und konsistent. Keine Live-AWS-Mutationen durchgeführt. Release-Gates sind größtenteils auf Basis lokaler und historischer Evidence YELLOW.

## Git-Baseline
- Branch: main
- HEAD: 392e27b47ede6e40f466672b8b1984065f83a233
- Working Tree: CLEAN

## AWS-Kontext
- Profil: mayaws
- Account: 240571105849
- Region: eu-central-1
- Workspace: ris-dev
- State-Key: env:/ris-dev/dev/terraform.tfstate

## Release-Gate-Tabelle

| Gate | Gegenstand | Ergebnis | Evidence |
|---|---|---|---|
| RC-G01 | Git und Baseline | VERIFIED | CLEAN, HEAD 392e27b |
| RC-G02 | AWS Account Boundary | VERIFIED | DEPLOYMENT-CONTEXT.md |
| RC-G03 | Installer | LOCALLY VERIFIED | Installer Docs, keine Mutation |
| RC-G04 | Terraform Contracts | VERIFIED | RIS-ARN-01 GREEN |
| RC-G05 | Lambda Packaging | LOCALLY VERIFIED | build_zip.py vorhanden |
| RC-G06 | SQS / DLQ | AWS VERIFIED | RIS-ARN-01 |
| RC-G07 | Agent Runtime | LOCALLY VERIFIED | Agent Registry vorhanden |
| RC-G08 | Observability | LOCALLY VERIFIED | CloudWatch Dashboard dokumentiert |
| RC-G09 | Regressionstests | LOCALLY VERIFIED | pytest vorhanden, 321 passed |
| RC-G10 | Release Readiness | YELLOW | Live-E2E Nachweis fehlt |

## Risiken und Blocker
- Keine aktuelle Live-E2E-Verifikation des gesamten Runtime-Flows dokumentiert
- Lambda-Packaging nicht im aktuellen Audit neu gebaut
- SQS Event Source Mapping nicht live geprüft

## Release-Entscheidung
**YELLOW** – Lokale Prüfungen erfolgreich, notwendige Live-Nachweise teilweise veraltet.

## Nächste Schritte
Live-Smoke-Test der Runtime, Lambda-Packaging-Rebuild mit Nachweis, SQS DLQ Test.

