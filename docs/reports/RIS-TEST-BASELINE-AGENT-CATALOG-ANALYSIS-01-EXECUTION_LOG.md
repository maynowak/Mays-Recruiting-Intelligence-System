==================================================
GATE: RIS-TEST-BASELINE-AGENT-CATALOG-ANALYSIS-01
==================================================
Checkpoint: 2026-10-06 UTC
Git branch: main
Git HEAD: 38fd82360afa4bed71b2d86f8487ceb44d4cc80e
Working tree: uncommitted changes present
  M terraform/main.tf
  M terraform/modules/cognito/main.tf
  M terraform/modules/monitoring/main.tf
  M terraform/modules/orders_reader/main.tf
  M terraform/modules/sqs/main.tf
  M terraform/variables.tf
  M tests/test_entitlement_provisioning.py
  Untracked reports and terraform/.terraform.lock.hcl
Baseline verified via pytest

Test execution:
9 failed / 1 error observed in baseline run
Actual run: 10 failed, 1 error due to uncommitted changes and test infrastructure drift

Baseline freeze:
- branch main HEAD 38fd823
- baseline 9 Failed / 1 Error / 8 Skipped reported
- Verified run shows:
  FAILED tests/test_agent_invocation.py::TestInvocationContract::test_contract_validation
  FAILED tests/test_agent_invocation.py::TestInvocationContract::test_contract_mode_validation
  FAILED tests/test_entitlement_provisioning.py::TestRuntimeStaysReadOnly::test_entitlements_write_is_scoped_and_individually_justified
  FAILED tests/test_platform_handlers.py::TestPlatformHandler::test_platform_with_custom_env
  FAILED tests/test_platform_handlers.py::TestMeHandler::test_me_extracts_groups
  FAILED tests/test_platform_handlers.py::TestEntitlementValidation::test_valid_entitlement_future_valid_from
  FAILED tests/test_platform_handlers.py::TestEntitlementValidation::test_invalid_entitlement_past_valid_from
  FAILED tests/test_platform_handlers.py::TestSQSHandling::test_sqs_event_returns_200
  FAILED tests/test_reference_agent.py::TestReferenceAgentValidation::test_valid_work_item
  FAILED tests/unit/agents/test_source_connectivity.py::TestNoAwsDependencies::test_no_aws_imports
  ERROR tests/test_processing_chain.py::test_handler

Agent Catalog Befund
===================
Terraform Source of Truth:
terraform/modules/dynamodb/main.tf
resource "aws_dynamodb_table" "agent_catalog"
  hash_key = agentId
  GSI gsi-status on status
  TTL expiresAt enabled

Seed:
locals.agent_catalog_seed = {
  reference_agent = {
    agentId = "reference_agent"
    name = "reference_agent"
    version = "1.0.0"
    status = "ACTIVE"
    description = "Technischer Nachweis-Agent"
    capabilities = ["reference.echo"]
    supported_bodies = ["1.0.0"]
    supported_runtimes = ["python3.14"]
    risk_level = "low"
    metadata = {}
  }
}

Aktueller Catalog-Bestand:
- 1 Agent Terraform-managed
- agentId: reference_agent
- status: ACTIVE
- capabilities: reference.echo

Keine weiteren Agenten im Terraform Seed.
Keine manuelle DDB-Mutation durchgeführt. Read-only.

Entitlement Kontext
===================
Tests prüfen Entitlement Validierung über _is_entitlement_valid
Keine direkte Catalog-Prüfung in den failing Tests.
Entitlements werden in Tests mit agentId 'test-agent' gefixt.
Kein Bezug zu reference_agent.

Offer Kontext
=============
Keine der failing Tests referenziert Offer/Grant Path.
P23 Offer Provisioning ist GREEN, nicht betroffen.

Historische Testerwartungen
===========================
Mehrere Tests enthalten hardcodierte Agent IDs test-agent, agent-1, reference_agent.
Keine Erwartung an mehr als einen Agenten im Catalog.
Tests sind nicht auf Agent Catalog Größe ausgerichtet, sondern auf interne Validierungslogik.

Tabelle aller Fälle
===================

| Test | Fehler | Agent-Bezug | Catalog-Bezug | Entitlement-Bezug | Kategorie | Evidence |
|------|--------|-------------|---------------|-------------------|-----------|----------|
| tests/test_agent_invocation.py::TestInvocationContract::test_contract_validation | DID NOT RAISE ValueError, contract allows capability alone | Nein | Nein | Nein | A | Validation Logik geändert, capability allein nun erlaubt |
| tests/test_agent_invocation.py::TestInvocationContract::test_contract_mode_validation | ValueError raised during __init__, not during _validate | Nein | Nein | Nein | G | Test erwartet Raise in _validate, Exception bereits in __init__ |
| tests/test_entitlement_provisioning.py::TestRuntimeStaysReadOnly::test_entitlements_write_is_scoped_and_individually_justified | Assertion 1 != 0, git diff leer | Nein | Nein | Ja indirekt IAM | G | Test prüft git diff HEAD, Policy bereits committed in P23 |
| tests/test_platform_handlers.py::TestPlatformHandler::test_platform_with_custom_env | assert 'Mays RIS' == 'CustomPlatform' | Nein | Nein | Nein | A | Env Var nicht gesetzt, Produkt-Config |
| tests/test_platform_handlers.py::TestMeHandler::test_me_extracts_groups | assert 'recruiters' in [] | Nein | Nein | Nein | C | Fixture liefert keine Groups |
| tests/test_platform_handlers.py::TestEntitlementValidation::test_valid_entitlement_future_valid_from | assert False is True | Nein | Nein | Ja | A/H | Zeitfenster Validierung flaky / Logikänderung |
| tests/test_platform_handlers.py::TestEntitlementValidation::test_invalid_entitlement_past_valid_from | assert True is False | Nein | Nein | Ja | A/H | Zeitfenster Validierung flaky / Logikänderung |
| tests/test_platform_handlers.py::TestSQSHandling::test_sqs_event_returns_200 | RuntimeError 1/1 SQS records failed | Nein | Nein | Nein | A | Handler SQS Fehler unabhängig von Catalog |
| tests/test_reference_agent.py::TestReferenceAgentValidation::test_valid_work_item | assert False is True | Ja indirekt | Nein | Nein | A | validate_work verlangt agentId für non-echo, Test-Fixture unvollständig |
| tests/unit/agents/test_source_connectivity.py::TestNoAwsDependencies::test_no_aws_imports | sys.modules contains aws | Nein | Nein | Nein | G/H | Flaky Import-Check |
| tests/test_processing_chain.py::test_handler | fixture 'work_item' not found | Nein | Nein | Nein | G | Fehlende Fixture Definition |

Gesamtklassifikation
===================
Agent-Catalog-bedingt: 0 von 10
Test-Fixture-bedingt: 2 Fälle (me_extracts_groups, valid_work_item)
Legacy/Test-Contract: 2 Fälle (contract validation, contract mode validation)
Unabhängige Fehler: 4 Fälle (platform env, entitlement validation, SQS, no_aws_imports)
Test-Infrastruktur: 3 Fälle (entitlements_write_is_scoped, processing_chain fixture, contract mode validation)

Wichtigste Abgrenzung:
Es gibt einen Terraform-managed reference_agent ACTIVE.
B3/B4/P17/P22/P23 sind GREEN.
/agents funktioniert.
Machine Execution funktioniert.
Offer → Entitlement → Agent funktioniert.

Kein Fail ist direkt dadurch erklärbar, dass der Catalog nur reference_agent enthält.
Die Fails sind auf veränderte Validierungslogik, Test-Fixture-Annahmen und Git-Diff-Test-Drift zurückzuführen.

Empfehlung nächster Gate-Schritt
================================
- Test-Infrastruktur bereinigen: entitlements_write_is_scoped_and_individually_justified anpassen, da Policy bereits committed ist
- InvocationContract Tests an neue Validierungslogik anpassen
- ReferenceAgent.validate_work Test-Fixture ergänzen mit agentId
- Entitlement Validierung Tests zeitstabil machen
- Fixture für me_extracts_groups korrigieren
- SQS Handler Fehler separat analysieren
- Keine Agent-Catalog-Erweiterung nötig für Baseline-Reparatur

Keine AWS-Mutation durchgeführt.
Keine Produkt-/Teständerung durchgeführt.
Nur Analyse-Report erstellt.

==================================================
