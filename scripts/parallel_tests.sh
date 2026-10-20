#!/usr/bin/env bash
# Parallel-Installationstests — VOLLSERIE.
# Jede Pruefung benennt: Ziel-Installation, Praefix/Erwartungswert, Ist-Wert.
# Nutzung:
#   ./scripts/parallel_tests.sh ris-a                 # Vollserie fuer A (~45 Checks)
#   ./scripts/parallel_tests.sh ris-b                 # Vollserie fuer B
#   ./scripts/parallel_tests.sh both                  # Parallel-/Trennungs-Serie
#   ./scripts/parallel_tests.sh destroy-check ris-a   # vollstaendiger Abbau-Nachweis
#   ./scripts/parallel_tests.sh ris-dev               # Vollserie dauerhafte Dev-Installation (aktuell)
#   ./scripts/parallel_tests.sh static                # Regression: fmt/validate/Unit-Tests
#   FULL=1 ./scripts/parallel_tests.sh ris-a          # zusaetzlich komplette pytest-Suite
set -u
TARGET="${1:-}"; P2="${2:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TERRA="$ROOT/terraform"
export TF_DATA_DIR="${TF_DATA_DIR:-/tmp/tfS3}"
export AWS_PROFILE="${AWS_PROFILE:-mayaws}"
export ROOT
E2E_CF="E1R3BHTJNMC6XW"           # fremd, vorgefunden — NIE anfassen
BACKEND_BUCKET="mays-ris-tf-state-dev"
LOCK_TABLE="mays-ris-tf-lock"
PASS=0; FAIL=0; WARN=0; SID=""; FAILED_IDS=()

ok()  { printf '  PASS [%s] %s\n' "$SID" "$1"; PASS=$((PASS+1)); }
bad() { printf '  FAIL [%s] %s\n' "$SID" "$1"; FAIL=$((FAIL+1)); FAILED_IDS+=("$SID"); }
warn() { printf '  WARN [%s] %s\n' "$SID" "$1"; WARN=$((WARN+1)); }
sec() { SID="$1"; echo "-- $1 $2"; }

expect()    { if [ "$2" = "$3" ]; then ok "$1 → $2"; else bad "$1 → erwartet='$2' ist='${3:-leer}'"; fi; }
expect_ge() { if [ -n "${3:-}" ] && [ "$3" -ge "$2" ] 2>/dev/null; then ok "$1 → $3 (≥$2)"; else bad "$1 → ist='${3:-leer}' (erwartet ≥$2)"; fi; }
expect_contains() { if [[ "${3:-}" == *"$2"* ]]; then ok "$1 → enthält '$2'"; else bad "$1 → '${3:-leer}' enthält nicht '$2'"; fi; }

awst() { aws "$@" --output text 2>/dev/null; }
cnt()  { local o="${1:-}"; if [ -z "$o" ] || [ "$o" = "None" ]; then echo 0
         else echo "$o" | tr '\t' '\n' | sed '/^$/d;/^None$/d' | wc -l; fi; }
lines(){ local o="${1:-}"; if [ -z "$o" ] || [ "$o" = "None" ]; then true
         else echo "$o" | tr '\t' '\n' | sed '/^$/d;/^None$/d'; fi; }
tf() { ( cd "$TERRA" && terraform "$@" ); }

# Segment-sichere Präfixe: "$1-" statt "$1", damit "ris-dev" NICHT "ris-development-*" matcht.
# (Ein nachgestellter Bindestrich trennt Namenssegmente; "ris-dev-" ≠ "ris-development-".)
_seg() { case "$1" in *-) echo "$1" ;; *) echo "$1-" ;; esac; }
LAMBDAS()  { cnt "$(awst lambda list-functions --region eu-central-1 --query "Functions[?starts_with(FunctionName,\`$(_seg "$1")\`)].FunctionName")"; }
RUNTIMES() { lines "$(awst lambda list-functions --region eu-central-1 --query "Functions[?starts_with(FunctionName,\`$(_seg "$1")\`)].Runtime")" | sort -u | tr '\n' ','; }
TABLES()   { cnt "$(awst dynamodb list-tables --region eu-central-1 --query "TableNames[?starts_with(@,\`$(_seg "$1")\`)]")"; }
APIS()     { cnt "$(awst apigatewayv2 get-apis --region eu-central-1 --query "Items[?starts_with(Name,\`$(_seg "$1")\`)].Name")"; }
QUEUES()   { awst sqs list-queues --region eu-central-1 --query 'QueueUrls' | tr '\t' '\n' | grep -c "$(_seg "$1")" || true; }
BUCKETS()  { cnt "$(awst s3api list-buckets --query "Buckets[?starts_with(Name,\`$(_seg "$1")\`)].Name")"; }
POOLS()    { cnt "$(awst cognito-idp list-user-pools --region eu-central-1 --max-results 60 --query "UserPools[?starts_with(Name,\`$(_seg "$1")\`)].Name")"; }
DASHES()   { cnt "$(awst cloudwatch list-dashboards --region eu-central-1 --query "DashboardEntries[?starts_with(DashboardName,\`$(_seg "$1")\`)].DashboardName")"; }
ALARM_CNT(){ awst cloudwatch describe-alarms --region eu-central-1 --alarm-name-prefix "$1" --query 'MetricAlarms|length(@)'; }
ALARM_BAD(){ awst cloudwatch describe-alarms --region eu-central-1 --alarm-name-prefix "$1" --query "MetricAlarms[?StateValue=='ALARM']|length(@)"; }
LOGGRPS()  { cnt "$(awst logs describe-log-groups --region eu-central-1 --query "logGroups[?starts_with(logGroupName,'/aws/lambda/$(_seg "$1")')].logGroupName")"; }
LOGRET()   { awst logs describe-log-groups --region eu-central-1 --log-group-name-prefix "/aws/lambda/$1" --query 'logGroups[].retentionInDays'; }
API_ID()   { awst apigatewayv2 get-apis --region eu-central-1 --query "Items[?Name=='$1'].ApiId"; }
API_EP()   { awst apigatewayv2 get-apis --region eu-central-1 --query "Items[?Name=='$1'].ApiEndpoint"; }
ROUTES()   { awst apigatewayv2 get-routes --region eu-central-1 --api-id "$1" --query 'Items[].RouteKey'; }
ROUTES_ORDERS() { lines "$(ROUTES "$1")" | grep -c '^[A-Z]*[A-Z ]*/orders' || true; }
ROUTES_NONE(){ cnt "$(awst apigatewayv2 get-routes --region eu-central-1 --api-id "$1" --query "Items[?AuthorizationType=='NONE'].RouteKey")"; }
POOLID()   { awst cognito-idp list-user-pools --region eu-central-1 --max-results 60 --query "UserPools[?Name=='$1'].Id"; }
HTTP()     { curl -s -o /dev/null -w "%{http_code}" "$1" 2>/dev/null; }

TF_VARS=( -var="filename=$TERRA/../lambda/dist/orders-reader.zip"
          -var="health_writer_zip_path=$TERRA/../lambda/dist/health-writer.zip"
          -var="health_publisher_zip_path=$TERRA/../lambda/dist/health-publisher.zip" )

# ============================================================ EINZEL-SERIE
# Component naming is "<project>-mays-orders[-...]" (see AGENTS.md, "Orders integration").
# Only the standalone legacy families "mays-ris-dev-*" and "mays-orders-*" are foreign;
# "<project>-mays-orders-..." belongs to the project itself and must NOT be flagged.
suite_single() {
  local P="$1" WS="$2" other="$3" other_label="$4"
  local FOREIGN="mays-ris-dev- $other"
  echo "### VOLLSERIE ZIEL=$P (workspace $WS) — getestet: $P besitzt genau $P-* und nichts Fremdes"

  # ---- S1 Zustand / Ownership / Sicherheits-Gates
  sec S1.1 "VORBEDINGUNG Workspace-Wahl (der Fehler aus T-3)"
  local WS_GOT; WS_GOT="$(tf workspace show 2>/dev/null)"
  expect "terraform workspace show" "$WS" "$WS_GOT"
  [ "$WS_GOT" = "$WS" ] || { echo "  ABBRUCH: falscher Workspace — Assertions wären wertlos"; FAIL=$((FAIL+1)); return; }

  sec S1.2 "STATE: erwartete Ressourcenzahl (ohne data.*)"
  local SC; SC="$(tf state list 2>/dev/null | grep -vE '(^|\.)data\.' | wc -l)"
  expect "terraform state Ressourcen" "169" "$SC"

  sec S1.3 "STATE_OWNERSHIP: kein Fremd-Präfix im $P-State (Kern der Parallel-Behauptung)"
  tf state pull > "/tmp/state_${P}.json" 2>/dev/null || true
  local OWN_BAD; OWN_BAD="$(python3 - "$FOREIGN" "/tmp/state_${P}.json" <<'PY'
import json,sys
foreign,path=sys.argv[1].split(),sys.argv[2]
try: d=json.load(open(path))
except Exception: print("ERR"); raise SystemExit
def strs(o):
    if isinstance(o,str): yield o
    elif isinstance(o,dict):
        for v in o.values(): yield from strs(v)
    elif isinstance(o,list):
        for v in o: yield from strs(v)
import re
def hit(s,f):
    # prefixes with trailing '-' match as substring (mays-ris-dev-, mays-orders-);
    # bare project names (ris-a/ris-b) need token boundaries so ris-api is not a hit
    if f.endswith("-"): return f in s
    return re.search(r"(?<![A-Za-z0-9-])"+re.escape(f)+r"(?![A-Za-z0-9-])", s) is not None
bad=set()
for r in d.get("resources",[]):
    for inst in r.get("instances",[]):
        for s in strs(inst.get("attributes",{})):
            for f in foreign:
                if hit(s,f): bad.add(s)
print(len(bad))
for b in sorted(bad)[:5]: print("   fremd:",b,file=sys.stderr)
PY
)"
  if [ "$OWN_BAD" = "ERR" ]; then bad "state pull nicht lesbar"; else expect "Fremd-Namen im State (erwartet 0)" "0" "$OWN_BAD"; fi
  # Komponenten heißen "<project>-mays-orders[-...]"; ein bareres "<project>-orders"
  # (ohne "mays-") ist der Altname-Suffix und darf nicht mehr vorkommen.
  expect "Altname '${P}-orders' im State (erwartet 0)" "0" \
    "$(grep -o "${P}-orders[-/\"\"]" "/tmp/state_${P}.json" | wc -l || true)"

  sec S1.4 "PLAN_SAFETY_GATE: frischer Plan enthält 0 Fremd-Namen"
  tf plan -input=false -lock=false "${TF_VARS[@]}" -var="project_name=$P" \
     -out="/tmp/plansafe_${P}.tfplan" >"/tmp/plansafe_${P}.log" 2>&1
  tf show -json "/tmp/plansafe_${P}.tfplan" > "/tmp/plansafe_${P}.json" 2>/dev/null || true
  local PLANSAFE; PLANSAFE="$(python3 - "$FOREIGN" "/tmp/plansafe_${P}.json" <<'PY'
import json,sys
foreign,path=sys.argv[1].split(),sys.argv[2]
try: d=json.load(open(path))
except Exception: print("ERR"); raise SystemExit
import re
def hit(s,f):
    if f.endswith("-"): return f in s
    return re.search(r"(?<![A-Za-z0-9-])"+re.escape(f)+r"(?![A-Za-z0-9-])", s) is not None
txt=json.dumps(d.get("resource_changes",[]))
print(sum(1 for f in foreign if hit(txt,f)))
PY
)"
  if [ "$PLANSAFE" = "ERR" ]; then bad "plan json nicht lesbar"; else expect "Fremd-Präfix in geplanten Changes" "0" "$PLANSAFE"; fi

  sec S1.5 "IDEMPOTENZ: Konfiguration == State"
  tf plan -detailed-exitcode -input=false -lock=false "${TF_VARS[@]}" -var="project_name=$P" \
     >"/tmp/idem_${P}.log" 2>&1
  local PE=$?
  if [ "$PE" = "0" ]; then ok "plan -detailed-exitcode = 0 (kein Drift)"; else bad "plan exit=$PE (0 erwartet)"; fi

  sec S1.6 "OUTPUT: Terraform-Output == Live-Ressourcenname"
  local OUT; OUT="$(tf output -raw dynamodb_work_items_table_name 2>/dev/null)"
  expect "output dynamodb_work_items_table_name" "${P}-dev-work-items" "$OUT"

  sec S1.7 "BACKEND: State-Objekt dieses Workspace in S3"
  # Installer-Konvention: key = "<env>/terraform.tfstate", workspace_key_prefix = "env:"
  # -> env:/<project>/<env>/terraform.tfstate (siehe installer/ris.py backend_config()).
  local SKEY="env:/${WS}/dev/terraform.tfstate"
  local SO; SO="$(awst s3api head-object --bucket "$BACKEND_BUCKET" --key "$SKEY" --query 'LastModified')"
  if [ -n "$SO" ] && [ "$SO" != "None" ]; then
    ok "$SKEY vorhanden ($SO)"
  else
    # Fallback: ältere Installationen ohne <env>/-Segment (env:/<project>/terraform.tfstate)
    SKEY="env:/${WS}/terraform.tfstate"
    SO="$(awst s3api head-object --bucket "$BACKEND_BUCKET" --key "$SKEY" --query 'LastModified')"
    if [ -n "$SO" ] && [ "$SO" != "None" ]; then ok "$SKEY vorhanden ($SO)"; else bad "State-Objekt env:/$WS/... fehlt"; fi
  fi

  # ---- S2 Inventar
  sec S2.1 "INVENTAR Lambdas $P (6) + Runtime python3.14"
  expect_ge "Anzahl Lambdas" 6 "$(LAMBDAS "$P")"
  expect "Runtimes aller $P-Lambdas" "python3.14," "$(RUNTIMES "$P")"

  sec S2.2 "INVENTAR DynamoDB: 10 Kern + Orders-Tabelle == <project>-mays-orders + Backend-Lock"
  expect "Kern-Tabellen ${P}-dev-*" "10" "$(TABLES "${P}-dev")"
  local OC; OC="${P}-mays-orders"
  local OSTAT; OSTAT="$(awst dynamodb describe-table --table-name "$OC" --region eu-central-1 --query 'Table.TableStatus')"
  expect "Orders-Tabelle '$OC' (Vertrag: Name == <project>-mays-orders)" "ACTIVE" "$OSTAT"
  expect "Backend-Lock" "ACTIVE" "$(awst dynamodb describe-table --table-name "$LOCK_TABLE" --region eu-central-1 --query 'Table.TableStatus')"

  sec S2.3 "INVENTAR HTTP-APIs $P (2)"
  expect "Anzahl APIs (${P}-dev-api + ${P}-mays-orders-api)" "2" "$(APIS "$P")"

  sec S2.4 "INVENTAR SQS: 6 Queues + DLQ-Redrive"
  expect "Anzahl Queues" "6" "$(QUEUES "$P")"
  local RDRV; RDRV="$(awst sqs get-queue-attributes --queue-url "https://sqs.eu-central-1.amazonaws.com/240571105849/${P}-dev-work-queue" --attribute-names RedrivePolicy --query 'Attributes.RedrivePolicy' 2>/dev/null)"
  expect_contains "Work-Queue hat DLQ-Redrive" "${P}-dev-dlq" "$RDRV"

  sec S2.5 "INVENTAR S3 (5) + kein öffentlicher Zugriff"
  expect "Anzahl Buckets" "5" "$(BUCKETS "$P")"
  local PUB; PUB="$(awst s3api get-public-access-block --bucket "${P}-dev-documents" --query 'PublicAccessBlockConfiguration.BlockPublicAcls' 2>/dev/null)"
  expect "Bucket ${P}-dev-documents BlockPublicAcls" "True" "$PUB"

  sec S2.6 "INVENTAR Cognito: 2 Pools + Gruppe 'staff' + email-verification"
  expect "Anzahl Pools" "2" "$(POOLS "$P")"
  local OPID; OPID="$(POOLID "${P}-mays-orders-users")"
  expect "Gruppe 'staff' im Orders-Pool" "1" "$(cnt "$(awst cognito-idp list-groups --region eu-central-1 --user-pool-id "$OPID" --query 'Groups[?GroupName==`staff`].GroupName')")"
  local RPID; RPID="$(POOLID "${P}-dev-users")"
  expect_contains "RIS-Pool ${P}-dev-users AutoVerifiedAttributes" "email" "$(awst cognito-idp describe-user-pool --region eu-central-1 --user-pool-id "$RPID" --query 'UserPool.AutoVerifiedAttributes')"

  sec S2.7 "INVENTAR Monitoring: 2 Dashboards, 13 Alarme (7 Kern + 6 Orders), 0 im Zustand ALARM"
  expect "Dashboards" "2" "$(DASHES "$P")"
  expect "Alarme gesamt" "13" "$(ALARM_CNT "$P-")"
  expect "Orders-Alarme Prefix ${P}-mays-orders-" "6" "$(ALARM_CNT "${P}-mays-orders-")"
  expect "Alarme im Zustand ALARM" "0" "$(ALARM_BAD "$P-")"

  sec S2.8 "INVENTAR CloudTrail: 1 Trail, multi-region, HomeRegion eu-central-1"
  expect "Trail-Namen" "1" "$(cnt "$(awst cloudtrail describe-trails --region eu-central-1 --query "trailList[?starts_with(Name,\`$(_seg "$P")\`)].Name")")"
  expect "IsMultiRegionTrail" "True" "$(awst cloudtrail describe-trails --region eu-central-1 --query "trailList[?starts_with(Name,\`$(_seg "$P")\`)].IsMultiRegionTrail")"
  expect "HomeRegion" "eu-central-1" "$(awst cloudtrail describe-trails --region eu-central-1 --query "trailList[?starts_with(Name,\`$(_seg "$P")\`)].HomeRegion")"

  sec S2.9 "INVENTAR Log-Groups: alle $P-Lambdas + Retention (Kern 14d, Orders 7d)"
  expect "Log-Groups" "6" "$(LOGGRPS "$P")"
  expect "Retention ${P}-dev-orders-reader" "7" "$(LOGRET "${P}-dev-orders-reader")"
  expect "Retention ${P}-dev-agent" "14" "$(LOGRET "${P}-dev-agent")"
  local NRET; NRET="$(lines "$(LOGRET "$(_seg "$P")")" | grep -c '^None$' || true)"
  expect "Log-Groups ohne Retention" "0" "$NRET"

  # ---- S3 API/Vertrag/Auth
  sec S3.1 "ROUTEN Kern-API: 4 Orders-Routen vorhanden"
  local CID; CID="$(API_ID "${P}-dev-api")"
  expect "Orders-Routen auf ${P}-dev-api" "4" "$(ROUTES_ORDERS "$CID")"
  expect_contains "Route POST /orders vorhanden" "POST /orders" "$(ROUTES "$CID")"
  expect_contains "Route PATCH /orders/…/status vorhanden" "PATCH /orders/{orderId}/status" "$(ROUTES "$CID")"

  sec S3.2 "ROUTEN Orders-API: 4, alle JWT"
  local OID; OID="$(API_ID "${P}-mays-orders-api")"
  expect "Routen auf ${P}-mays-orders-api" "4" "$(cnt "$(ROUTES "$OID")")"
  expect "Routen ohne Authorizer (NONE) auf ${P}-mays-orders-api" "0" "$(ROUTES_NONE "$OID")"

  sec S3.3 "AUTH: keine ungeschützte Route auf der Kern-API, 2 Authorizer"
  expect "Routen mit AuthorizationType NONE" "0" "$(ROUTES_NONE "$CID")"
  expect "Authorizer (jwt-human + jwt-m2m)" "2" "$(awst apigatewayv2 get-authorizers --region eu-central-1 --api-id "$CID" --query 'Items|length(@)')"

  sec S3.4 "AUTH-SMOKE Kern-API: geschützte Routen ohne Token"
  local EP; EP="$(API_EP "${P}-dev-api")"
  if [ -z "$EP" ] || [ "$EP" = "None" ]; then bad "Endpoint ${P}-dev-api nicht gefunden"; else
    expect "GET /health" "401" "$(HTTP "$EP/health")"
    expect "GET /platform" "401" "$(HTTP "$EP/platform")"
    expect "GET /me" "401" "$(HTTP "$EP/me")"
    expect "GET /orders (Facade)" "401" "$(HTTP "$EP/orders")"
  fi
  local OEP; OEP="$(API_EP "${P}-mays-orders-api")"
  if [ -z "$OEP" ] || [ "$OEP" = "None" ]; then bad "Endpoint ${P}-mays-orders-api nicht gefunden"; else
    expect "GET /orders (Orders-API)" "401" "$(HTTP "$OEP/orders")"
  fi

  # ---- S4 Verkabelung (ARN/URL, kein Name-Hardcoding)
  local OC="${P}-mays-orders" OQ="${P}-mays-orders-orders-queue"
  sec S4.1 "VERKABELUNG Reader: Env zeigt auf $OC (kein Cross-Talk)"
  local ORD QURL
  ORD="$(awst lambda get-function-configuration --function-name "${P}-dev-orders-reader" --region eu-central-1 --query 'Environment.Variables.ORDERS_TABLE')"
  QURL="$(awst lambda get-function-configuration --function-name "${P}-dev-orders-reader" --region eu-central-1 --query 'Environment.Variables.ORDERS_SQS_QUEUE_URL')"
  expect "ORDERS_TABLE" "$OC" "$ORD"
  expect_contains "ORDERS_SQS_QUEUE_URL" "$OQ" "$QURL"

  sec S4.2 "VERKABELUNG ESM: orders→worker Enabled/5, work→agent Enabled"
  local E1 E2
  E1="$(awst lambda list-event-source-mappings --region eu-central-1 --query "EventSourceMappings[?contains(EventSourceArn,\`$OQ\`)].[State,BatchSize]" | tr '\t' '/')"
  expect_contains "ESM orders-queue" "Enabled/5" "$E1"
  E2="$(awst lambda list-event-source-mappings --region eu-central-1 --query "EventSourceMappings[?contains(EventSourceArn,\`${P}-dev-work-queue\`)].State")"
  expect_contains "ESM work-queue" "Enabled" "$E2"

  sec S4.3 "VERKABELUNG IAM Least Privilege des Readers"
  local ROLE="${P}-dev-orders-reader" POL DOC
  POL="$(awst iam list-role-policies --role-name "$ROLE" --query 'PolicyNames[0]')"
  DOC="$(awst iam get-role-policy --role-name "$ROLE" --policy-name "$POL" --query 'PolicyDocument')"
  expect_contains "dynamodb:PutItem" "dynamodb:PutItem" "$DOC"
  expect_contains "dynamodb:Query" "dynamodb:Query" "$DOC"
  expect_contains "sqs:SendMessage" "sqs:SendMessage" "$DOC"
  expect_contains "gebunden auf table/$OC" ":table/$OC" "$DOC"
  expect_contains "gebunden auf :$OQ" ":$OQ" "$DOC"

  # ---- S5 Ownership / Schonung Fremder
  sec S5.1 "OWNERSHIP: $P besitzt keine Alt-Ressourcen (mays-ris-dev-* / mays-orders-*)"
  expect "Lambdas mit Alt-Präfix" "0" "$(cnt "$(awst lambda list-functions --region eu-central-1 --query 'Functions[?starts_with(FunctionName,`mays-ris-dev`) || starts_with(FunctionName,`mays-orders`)].FunctionName')")"
  expect "Tabellen mit Alt-Präfix" "0" "$(cnt "$(awst dynamodb list-tables --region eu-central-1 --query 'TableNames[?starts_with(@,`mays-ris-dev`) || starts_with(@,`mays-orders`)]')")"

  sec S5.2 "TRENNUNG: $other_label ist entweder abwesend ODER vollständig eigenständig"
  local OTHER_L; OTHER_L="$(LAMBDAS "$other")"
  if [ "$OTHER_L" = "0" ]; then
    ok "$other_label abwesend (Einzelbetrieb) → Lambdas=0"
    expect "Tabellen $other" "0" "$(TABLES "$other")"
    expect "APIs $other" "0" "$(APIS "$other")"
    expect "Dashboards $other" "0" "$(DASHES "$other")"
  else
    expect_ge "$other_label Lambdas (Parallelbetrieb)" 6 "$OTHER_L"
    expect "$other_label Reader ORDERS_TABLE (kein Cross-Talk)" "$other" \
      "$(awst lambda get-function-configuration --function-name "${other}-dev-orders-reader" --region eu-central-1 --query 'Environment.Variables.ORDERS_TABLE')"
    expect "$other_label Dashboards eigener Satz" "2" "$(DASHES "$other")"
    expect "$P-Reader bleibt auf $P" "$P" \
      "$(awst lambda get-function-configuration --function-name "${P}-dev-orders-reader" --region eu-central-1 --query 'Environment.Variables.ORDERS_TABLE')"
  fi

  sec S5.3 "SCHONUNG: fremde vorgefundene Ressourcen unberührt"
  expect "fremde e2e-Distribution $E2E_CF" "1" "$(awst cloudfront list-distributions --query 'DistributionList.Items[].Id' | grep -c "$E2E_CF" || true)"
  expect "fremder e2e-OAC" "1" "$(cnt "$(awst cloudfront list-origin-access-controls --query "OriginAccessControlList.Items[?starts_with(Name,\`mays-ris-e2e\`)].Name")")"

  # ---- S6 Code-Kontrakte (pytest)
  sec S6.1 "CODE-KONTRAKT pytest (health / credential / api-contract / installer)"
  run_pytest_pair "$P" "tests/test_p20_health_contract.py" "Health-Contract"
  run_pytest_pair "$P" "tests/test_p17_credential_lifecycle.py" "Credential-Lifecycle"
  run_pytest_pair "$P" "tests/test_p20_api_contract_consistency.py" "API-Contract-Konsistenz"
  run_pytest_baseline "$P" "tests/test_ris_installer.py" "Installer-Unit-Tests"

  if [ "${FULL:-0}" = "1" ]; then
    sec S6.2 "CODE-SUITE komplett (FULL=1)"
    ( cd "$ROOT" && python3 -m pytest tests/ -q -p no:cacheprovider >"/tmp/full_pytest_${P}.log" 2>&1 )
    if [ $? = 0 ]; then ok "$(tail -1 "/tmp/full_pytest_${P}.log")"; else bad "vollständige pytest-Suite: $(tail -2 "/tmp/full_pytest_${P}.log" | head -1)"; fi
  fi
}

KNOWN_BASELINE_TESTS="test_install_dry_run_performs_no_mutation test_validate_skips_workspace_without_backend"

run_pytest_baseline() {
  local P="$1" FILE="$2" LABEL="$3"
  local LOG="/tmp/pt_${P}_$(basename "$FILE" .py).log"
  ( cd "$ROOT" && python3 -m pytest "$FILE" -q -p no:cacheprovider >"$LOG" 2>&1 )
  local RC=$?
  if [ "$RC" = "0" ]; then ok "$LABEL: $(tail -1 "$LOG")"; return; fi
  local unknown=""
  local t
  for t in $(grep '^FAILED ' "$LOG" | sed -E 's/.*::([^ ]+).*/\1/' | sort -u); do
    case " $KNOWN_BASELINE_TESTS " in *" $t "*) ;; *) unknown="$unknown $t" ;; esac
  done
  if [ -z "$unknown" ]; then
    warn "$LABEL: $(tail -2 "$LOG" | head -1) — ausschliesslich dokumentierte Baseline-Defekte (AGENTS.md Z.39), kein Parallel-Regress"
  else
    bad "$LABEL: unerwartete Fehlschlaege:$unknown"
  fi
}

run_pytest_pair() {
  local P="$1" FILE="$2" LABEL="$3"
  local LOG="/tmp/pt_${P}_$(basename "$FILE" .py).log"
  ( cd "$ROOT" && python3 -m pytest "$FILE" -q -p no:cacheprovider >"$LOG" 2>&1 )
  if [ $? = 0 ]; then ok "$LABEL: $(tail -1 "$LOG")"; else bad "$LABEL: $(tail -2 "$LOG" | head -1)"; fi
}

# ============================================================ DUAL-SERIE
suite_both() {
  local A="ris-a" B="ris-b"
  echo "### VOLLSERIE ZIEL=both — getestet: beide koexistieren, ohne Überschneidung, ohne Cross-Talk"

  sec B1.1 "KOEXISTENZ: beide Kern-APIs antworten gleichzeitig geschützt"
  local p; for p in $A $B; do
    expect "$p /health ohne Token" "401" "$(HTTP "$(API_EP "${p}-dev-api")/health")"
  done

  sec B2.1 "VOLLSTÄNDIGKEIT je Installation"
  expect "$A-Lambdas" "6" "$(LAMBDAS $A)";      expect "$B-Lambdas" "6" "$(LAMBDAS $B)"
  expect "$A-Kern-Tables" "10" "$(TABLES "${A}-dev")"; expect "$B-Kern-Tables" "10" "$(TABLES "${B}-dev")"
  expect "$A-Queues" "6" "$(QUEUES $A)";        expect "$B-Queues" "6" "$(QUEUES $B)"
  expect "$A-Dashboards" "2" "$(DASHES $A)";    expect "$B-Dashboards" "2" "$(DASHES $B)"
  expect "$A-Alarme" "13" "$(ALARM_CNT "$A-")"; expect "$B-Alarme" "13" "$(ALARM_CNT "$B-")"

  sec B3.1 "CROSS-TALK: Reader je Installation auf die eigene Tabelle/Queue"
  local OA OB QA QB
  OA="$(awst lambda get-function-configuration --function-name ${A}-dev-orders-reader --region eu-central-1 --query 'Environment.Variables.ORDERS_TABLE')"
  OB="$(awst lambda get-function-configuration --function-name ${B}-dev-orders-reader --region eu-central-1 --query 'Environment.Variables.ORDERS_TABLE')"
  QA="$(awst lambda get-function-configuration --function-name ${A}-dev-orders-reader --region eu-central-1 --query 'Environment.Variables.ORDERS_SQS_QUEUE_URL')"
  QB="$(awst lambda get-function-configuration --function-name ${B}-dev-orders-reader --region eu-central-1 --query 'Environment.Variables.ORDERS_SQS_QUEUE_URL')"
  expect "$A-Reader ORDERS_TABLE" "$A" "$OA"
  expect "$B-Reader ORDERS_TABLE" "$B" "$OB"
  expect_contains "$A-Reader Queue" "${A}-orders-queue" "$QA"
  expect_contains "$B-Reader Queue" "${B}-orders-queue" "$QB"

  sec B4.1 "NAMENSEINDEUTIGKEIT: Schnittmenge A∩B == 0 (Lambda/Tabelle/Queue/API)"
  local NA NB TA TB
  NA="$(lines "$(awst lambda list-functions --region eu-central-1 --query 'Functions[?starts_with(FunctionName,`ris-a`)].FunctionName')" | sort)"
  NB="$(lines "$(awst lambda list-functions --region eu-central-1 --query 'Functions[?starts_with(FunctionName,`ris-b`)].FunctionName')" | sort)"
  expect "Schnittmenge Lambdas" "0" "$(comm -12 <(echo "$NA") <(echo "$NB") | wc -l)"
  TA="$(lines "$(awst dynamodb list-tables --region eu-central-1 --query 'TableNames[?starts_with(@,`ris-a`)]')" | sort)"
  TB="$(lines "$(awst dynamodb list-tables --region eu-central-1 --query 'TableNames[?starts_with(@,`ris-b`)]')" | sort)"
  expect "Schnittmenge Tabellen" "0" "$(comm -12 <(echo "$TA") <(echo "$TB") | wc -l)"

  sec B5.1 "ZUSTANDS-OWNERSHIP: kein A-Präfix im B-State und umgekehrt"
  local CROSS
  CROSS="$(python3 - <<'PY'
import json,subprocess,os
env=dict(os.environ)
def pull(ws):
    r=subprocess.run(["terraform","state","pull"],cwd=os.path.join(os.environ["ROOT"],"terraform"),
        env={**env,"TF_WORKSPACE":ws},capture_output=True,text=True)
    return r.stdout
out=0
for ws,foreign in (("ris-a","ris-b"),("ris-b","ris-a")):
    try: d=json.loads(pull(ws))
    except Exception: continue
    t=json.dumps(d.get("resources",[]))
    if f'"{foreign}-' in t or f'{foreign}-' in t: out+=1
print(out)
PY
)"
  expect "Installationen mit Fremd-Präfix im eigenen State" "0" "$CROSS"

  sec B6.1 "MONITORING-UNABHÄNGIGKEIT: kein ALARM-Zustand, keiner überschrieben"
  expect "ALARM-Zustand $A" "0" "$(ALARM_BAD "$A-")"
  expect "ALARM-Zustand $B" "0" "$(ALARM_BAD "$B-")"

  sec B7.1 "A-Idempotenz bleibt, solange B existiert"
  ( cd "$TERRA" && TF_WORKSPACE=ris-a terraform plan -detailed-exitcode -input=false -lock=false "${TF_VARS[@]}" -var="project_name=ris-a" >/tmp/both_idem_a.log 2>&1 )
  if [ $? = 0 ]; then ok "plan A exit 0 (kein Drift durch B)"; else bad "plan A exit≠0 (Drift durch B)"; fi
}

# ============================================================ DESTROY-CHECK
suite_destroy() {
  local P="$1"
  echo "### VOLLSERIE ZIEL=destroy-check $P — getestet: $P ist restlos entfernt, Backend+Fremde intakt"
  sec D1.1 "WEG: keine Lambda/Tabelle/API/Queue"
  expect "$P-Lambdas" "0" "$(LAMBDAS "$P")"
  expect "$P-Tabellen" "0" "$(TABLES "$P")"
  expect "$P-APIs" "0" "$(APIS "$P")"
  expect "$P-Queues" "0" "$(QUEUES "$P")"
  sec D1.2 "WEG: keine Buckets/Pools/Dashboards/Alarme/Log-Groups"
  expect "$P-Buckets" "0" "$(BUCKETS "$P")"
  expect "$P-Pools" "0" "$(POOLS "$P")"
  expect "$P-Dashboards" "0" "$(DASHES "$P")"
  expect "$P-Alarme" "0" "$(ALARM_CNT "$P-")"
  expect "$P-LogGroups" "0" "$(LOGGRPS "$P")"
  sec D1.3 "WEG: Trail, OAC, IAM-Rollen"
  expect "$P-Trails" "0" "$(cnt "$(awst cloudtrail describe-trails --region eu-central-1 --query "trailList[?starts_with(Name,'$P')].Name")")"
  expect "$P-OACs" "0" "$(cnt "$(awst cloudfront list-origin-access-controls --query "OriginAccessControlList.Items[?starts_with(Name,\`$P\`)].Name")")"
  expect "$P-IAM-Rollen" "0" "$(cnt "$(awst iam list-roles --query "Roles[?starts_with(RoleName,\`$P\`)].RoleName")")"
  sec D1.4 "STATE leer"
  if [ -f "$TERRA/terraform.tfstate.d/$P/terraform.tfstate" ]; then
    local N; N="$(tf workspace select "$P" >/dev/null 2>&1 && tf state list 2>/dev/null | wc -l)"
    expect "State $P Ressourcen" "0" "$N"
  else ok "kein lokaler State-Verzeichniseintrag für $P"; fi
  sec D2.1 "ERHALTEN: Backend + fremde Ressourcen"
  expect "Backend-Lock" "ACTIVE" "$(awst dynamodb describe-table --table-name "$LOCK_TABLE" --region eu-central-1 --query 'Table.TableStatus')"
  local RB; RB="$(awst s3api head-bucket --bucket "$BACKEND_BUCKET" 2>/dev/null; echo $?)"
  expect "Backend-State-Bucket erreichbar" "0" "$(echo "$RB" | tail -c 2)"
  expect "fremde e2e-Distribution" "1" "$(awst cloudfront list-distributions --query 'DistributionList.Items[].Id' | grep -c "$E2E_CF" || true)"
}

# ============================================================ STATIK/REGRESSION
suite_static() {
  echo "### VOLLSERIE ZIEL=static — getestet: Konfiguration + Unit-Tests (keine AWS-Mutation)"
  sec R1.1 "terraform fmt -check"
  if ( cd "$TERRA" && terraform fmt -check -recursive >/tmp/fmt.log 2>&1 ); then ok "fmt sauber"; else bad "fmt: $(head -3 /tmp/fmt.log)"; fi
  sec R1.2 "terraform validate"
  if ( cd "$TERRA" && terraform validate >/tmp/validate.log 2>&1 ); then ok "$(tail -1 /tmp/validate.log)"; else bad "validate: $(head -5 /tmp/validate.log)"; fi
  sec R1.3 "Installer-Unit-Tests"
  run_pytest_baseline static tests/test_ris_installer.py "Installer-Unit-Tests"
  sec R1.4 "API-/Health-/Credential-Kontrakte"
  run_pytest_pair static tests/test_p20_api_contract_consistency.py "API-Contract"
  run_pytest_pair static tests/test_p20_health_contract.py "Health-Contract"
  run_pytest_pair static tests/test_p17_credential_lifecycle.py "Credential-Lifecycle"
  sec R1.5 "BAU: Lambda-Bundles vorhanden"
  for z in lambda/dist/orders-reader.zip lambda/dist/health-writer.zip lambda/dist/health-publisher.zip terraform/lambda.zip; do
    if [ -f "$ROOT/$z" ]; then ok "Bundle $z ($(du -h "$ROOT/$z" | cut -f1))"; else bad "Bundle $z fehlt"; fi
  done
}

case "$TARGET" in
  ris-a)         suite_single ris-a ris-a ris-b "Installation RIS-B" ;;
  ris-b)         suite_single ris-b ris-b ris-a "Installation RIS-A" ;;
  ris-dev)       suite_single ris-dev ris-dev ris-a "Installation RIS-A (abwesend)" ;;
  ris-development) echo "FEHLER: 'ris-development' existiert nicht mehr (Destroy 2026-10-20). Nutze 'ris-dev'."; exit 2 ;;
  both)          suite_both ;;
  destroy-check) [ -n "$P2" ] || { echo "Präfix fehlt: destroy-check <ris-a|ris-b>"; exit 2; }; suite_destroy "$P2" ;;
  static)        suite_static ;;
  *) echo "Nutzung: $0 <ris-a|ris-b|ris-dev|both|destroy-check <p>|static>"; exit 2 ;;
esac

echo "### ERGEBNIS ($TARGET${P2:+ $P2}): $PASS bestanden, $FAIL fehlgeschlagen, $WARN Warnungen"
if [ "$FAIL" != "0" ]; then echo "### FEHLGESCHLAGEN: ${FAILED_IDS[*]}"; exit 1; fi
exit 0
