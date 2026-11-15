# MO-RIS-AWS-PLAN-REVIEW-02 — R2 Attempt: Profile Blocked

**Datum:** 2026-11-14
**Modus:** READ-ONLY Diagnose. Kein Plan, kein Apply, keine Mutation.
**Ergebnis:** **R2 BLOCKED — `AWS_PROFILE_NOT_FOUND`.**

## 1. Ausgeführter Schritt

```
aws sts get-caller-identity --profile devmemo
→ The config profile (devmemo) could not be found
```

## 2. Evidenz (lokal, ohne Zugangsdaten)

| Prüfung | Ergebnis |
|---|---|
| `aws configure list-profiles` | **nur `default`** |
| `AWS_CONFIG_FILE` / `AWS_SHARED_CREDENTIALS_FILE` | nicht gesetzt (Standardpfad) |
| `~/.aws/config` | 49 B, nur `[default]` + `region = eu-central-1` + `output = json` |
| `~/.aws/credentials` | nur `[default]` (Keys redigiert) |
| `~/.aws/cli` | nur `session.db` (CLI-Historie, kein Profil) |

Das Profil `devmemo` ist auf diesem Rechner in keiner Konfigurationsdatei
vorhanden — weder in `config` noch in `credentials`.

## 3. Diagnose des Default-Profils (nur zur Abgrenzung)

```
aws sts get-caller-identity
→ Account 262370457690, arn:aws:iam::262370457690:user/devnemo
```

Damit gilt: Selbst wenn `default` ersatzweise verwendet würde, läge das Konto
**nicht** bei `240571105849`. Das Identity Gate würde also ohnehin scheitern.

## 4. Warum hier gestoppt wird

Der Auftrag ist eindeutig: keine ersatzweise Verwendung von `default`, `mayaws`
oder anderen Profilen. Ein Plan gegen `262370457690` würde 18 Ressourcen in einem
Konto zeigen, in dem sie nicht entstehen sollen — eine Zahl mit Autorität, aber
ohne Wahrheit.

**Keine AWS-Mutation, kein Plan, kein Apply, kein Secret-Zugriff.**

## 5. Was für den nächsten Versuch nötig ist

Eine der drei folgenden Klärungen:

1. **Exakter Profilname**, wie ihn `aws configure list-profiles` auf diesem
   Rechner anzeigt (falls er nach dem Commit angelegt wurde).
2. **Profil anlegen** in dieser Shell, z. B. `aws configure --profile devmemo`
   (Zugangsdaten nicht in den Chat schreiben).
3. **Ausdrückliche Entscheidung**, das `default`-Profil als Ziel zu verwenden —
   dann aber mit der Konsequenz, dass das Zielkonto `262370457690` wäre und die
   bisherige Datei-Evidenz (`240571105849`) nicht mehr gilt.

## 6. Nächste Schritte nach Klärung (unverändert)

1. `sts get-caller-identity` → Konto bestätigen.
2. RIS-dev2-State lesen (Serial, Lineage, Workspace), `ris-dev` **nicht**.
3. Orders-Test-State identifizieren und Ownership nachweisen.
4. Default-off-Plan und Integration-enabled-Plan je Repo.
5. Plan-Dateien + SHA-256 sichern, Änderungen dokumentieren.

**Status: R2 BLOCKED — `AWS_PROFILE_NOT_FOUND`.**

Kein Apply, kein Destroy, kein Deployment, kein Merge, keine Secrets.

---

## 7. Nachtrag: Zielumgebung `ris-dev2` — zusätzlicher Konflikt

Beim Abgleich mit den lokalen Reports (kein AWS-Zugriff) ergibt sich ein
**zweiter, unabhängiger Blocker**:

`docs/AI_AUDITLOG.md` → `[RIS-DEV2-STACK-DESTROY-01]`, Datum **2026-11-09**:

> Workspace `ris-dev2` (**Account `262370457690`**, `eu-central-1`) wurde
> vollständig abgebaut: **177 Ressourcen**, State **serial 36**, **state
> resources 0**. Bootstrap bewusst behalten: `ris-dev2-tf-state-dev`,
> `ris-dev2-tf-lock`. `ris-dev` blieb unangetastet.

Der Report `docs/reports/RIS-DEV2-STACK-DESTROY-01.md` sagt ausdrücklich, dass
`ris-dev2` **später** kontrolliert neu aufgebaut werden *kann* — es wurde seither
**nicht** wieder aufgebaut (keine Rebuild-Evidenz in Auditlog oder Reports).

Damit steht der R2-Auftrag im Widerspruch zur Evidenz:

| Auftrag R2 | Lokale Evidenz |
|---|---|
| Zielumgebung `ris-dev2` | **zerstört**, 0 Ressourcen |
| State-Key `env:/ris-dev2/dev/terraform.tfstate` | existiert, aber leer (serial 36) |
| Erwartetes Konto `240571105849` | Destroy lief in **`262370457690`** |

**Konsequenz für einen Plan:** Mit `enable_agent_transport = true` gegen den
leeren `ris-dev2`-State plant Terraform **nicht 18**, sondern die **gesamte
RIS-Plattform plus 18** (≈ 195 Ressourcen). Diese Zahl wäre korrekt — aber sie
widerspricht der Erwartung „18 Creates" und würde bei einem ungeprüften Apply
ein komplettes System neu errichten.

**Status: R2 BLOCKED — `ACCOUNT_TOPOLOGY_CONFLICT`** (zusätzlich zum fehlenden
Profil).

### Drei auflösbare Varianten

| Variante | Ziel | Konsequenz |
|---|---|---|
| **A** | `ris-dev2` in `240571105849` neu aufbauen | vollständiger RIS-Stack + 18 Integration; großer Plan, bewusste Neuinstallation |
| **B** | Bestehendes `ris-agent` in `262370457690` nutzen (185 Ressourcen, drift 0) | 18 Integration + **Cross-Account** zu Orders (`240571105849`) |
| **C** | Beide Systeme in `262370457690` | Orders-Backend müsste dort existieren — existiert nicht; neue Backend-Anlage nötig |

Variante **B** ist die einzige, die ohne Neuaufbau und ohne Backend-Migration
auskäme, verlangt aber Cross-Account-Policies (Queue-Prinzipale, ggf. KMS).
Variante **A** ist architektonisch am nächsten an der bisherigen Datei-Evidenz,
bedeutet aber einen vollständigen Neuaufbau.

**Ohne Entscheidung wird kein Plan erzeugt.**
