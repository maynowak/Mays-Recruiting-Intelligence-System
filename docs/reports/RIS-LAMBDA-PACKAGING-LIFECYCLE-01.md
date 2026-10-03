# RIS-LAMBDA-PACKAGING-LIFECYCLE-01 — Deterministischer Bundle-Vertrag

STATUS: GREEN

- Date/Time: 2026-10-03 UTC
- Branch + HEAD: main, d0db48d + Packaging-Commits (s. Git)
- MO-Stand: 0 Änderungen.
- Scope: deterministisches Packaging + Installer-Ordnung + TF-Hash-Vertrag. Kein Architektur-Umbau, kein Layer/ECR/CI-System.
- Classification: GREEN (alle 16 Akzeptanzpunkte belegt oder begründet)
- Terraform/AWS: validate GREEN; gezielte Funktions-Updates (2 changed, Code-identisch); No-Ops leer; 0 destroys
- Git: Commits pro Stufe (s. Git); Repo clean (Zips ignoriert)
- Files Changed: `lambda/build_zip.py` (deterministische Bundles), `installer/ris.py` (package-Befehl), `tests/test_lambda_packaging.py` (neu, 7), `tests/test_ris_installer.py` (+3), Docs (Architektur/Roadmap), Reports
- Open: CI erstellt kein Bundle (nicht umgebaut, dokumentiert); 5 pre-existing Defekte; Mayaws-Fremdmutationen (beobachtet)
- Risks: 2 gezielte Funktions-Updates (Code-identisch, Active verifiziert)
- Next: Folgetore (kein Feature hier)
- Resume Point: nach Commit HARD STOP

## Discovery (A–D)

- A: 2× `aws_lambda_function` (agent: `lambda_config.filename` Default `lambda.zip` + `filebase64sha256`; reader: Pflicht-Var auf `lambda/dist/orders-reader.zip`). Keine S3-Keys/Layer/`archive_file`.
- B: Quellen agent = `lambda/handler.py` + `agents/` + `jobsearch/`; reader = `lambda/orders_reader.py`. Repo-Skript baute nur `lambda/`-Dir (ohne agents/ → live ImportModuleError — Lücke belegt).
- C: `lambda.zip` erzeugte NIEMAND (Installer/TF/CI nicht); TF/CI brauchen es VOR plan. CI (`ci-cd.yml`): init/validate/fmt + plan ohne Backend-Config und ohne ZIP → dort ebenfalls rot (nicht umgebaut, dokumentiert — anderer Scope: Creds/Backend fehlen dort ebenso).
- D: Plan bricht ohne ZIP ab (`file()`); Reihenfolge MUSS package→plan→apply sein (Vertrag, per `package`-Befehl + Tests).

## Vertrag/Reproduzierbarkeit/Determinismus (§5–6)

- Vertrag: Quelle gleich → Bytes gleich → Hash gleich → No-Op; Quelle anders → Hash anders → Update. Infrastruktur-/Source-/Packaging-/Dependency-Änderungen trennbar (Hash gehört zum Bundle).
- Determinismus: sortierte Einträge + `FIXED_ZIP_DATE (1980-01-01)` + fixe Perms + Ausschluss (`__pycache__/.git/.pytest_cache/.DS_Store`, `.pyc/.pyo`, nur `.py`). Keine absoluten Pfade, kein `.git`, kein Bytecode, keine Tests im Bundle (45 + 1 Dateien).

## TF-/Installer-/CI-Vertrag (§7–9)

- TF: `source_code_hash` auf echtem ZIP; No-Op bei Gleichheit, Update bei Änderung (beide live belegt).
- Installer: neuer `package`-Befehl (`--bundle agent|reader|all`, deterministisch, Exit-Codes getestet); Ordnung package→plan→apply dokumentiert+getestet. Kein zweiter Mechanismus (generischer Builder unangetastet).
- CI: erstellt nichts, erwartet nichts — Differenz dokumentiert (bewusst kein Ersatz; bräuchte zusätzlich Backend/Creds).

## Testmatrix (§10)

- A Clean (Build ok), B Content (exakt 1 Root-Datei Reader; Agent 45 .py), C Exclusions (kein Cache/Git/Bytecode/Docs/Specs), D Repro (2 Builds identisch) — PASS.
- E No-Op: kanonischer Rebuild == Live-State-Hash (nach kanonischem Apply) — PASS (vorher Mismatch durch mtime-Drift, ehrlich dokumentiert).
- F Change (Tmp-Kopie, Kommentar): Hash ändert — PASS. G Restore: Hash zurück — PASS (Repo unverändert verifiziert).
- H Live-Update: 2 gezielte Funktions-Updates (Code-identisch, nur Metadaten normalisiert), beide Active/Successful, Smoke 404-aus-Handler — PASS. Kein Produktions-Overkill (kein Testprojekt nötig: Hash-Vergleich trägt den Beweis).

## AWS-Safety (§11)

- Keine Testprojekt-Neuerstellung (Hash-Beweis genügt); Prod-Updates nur Code-identisch + gezielt; CloudTrail unauffällig (keine Fremdmutation in diesem Gate); /tmp-Artefakte entfernt.

## Ownership (§12)

- `terraform/lambda.zip` + `lambda/dist/orders-reader.zip`: generierte Build-Artefakte UND Terraform-Inputs (via `file()`); git-ignoriert (nie committen); erzeugt vom Installer-`package`-Befehl (oder Skript direkt); konsumiert von plan/apply; Löschung optional (jeder Plan braucht sie → behalten, jederzeit reproduzierbar).

## Checkpoint: RIS-LAMBDA-PACKAGING-LIFECYCLE-01

- date/time: 2026-10-03 ~12:00 UTC · branch: main · HEAD: s. Git · status: GREEN
- mechanism: `lambda/build_zip.py --bundle` (deterministisch) · owner: generiert/TF-Input · location: `terraform/lambda.zip`, `lambda/dist/orders-reader.zip` (ignoriert)
- determinism: Rebuild-identisch (D) · hash: Gleichheit↔No-Op, Änderung↔Update (E/F/G/H live)
- no-op: Funktionen-No-Op leer · installer: `package` implementiert+verwendet · CI: dokumentiert-OPEN
- AWS: 0/2/0 gezielt, Active verifiziert · tests: 7 Packaging + 3 Installer + Suite 349/8-Skip · docs: Report+Log+Arch/Roadmap · audit: aktualisiert
- gaps: CI-Package, 5 Defekte, Fremdmutationen (beobachtet) · commits: s. Git · status: clean · next: Folgetore

**HARD STOP.**
