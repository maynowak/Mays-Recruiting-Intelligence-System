# RIS: Geplante Umstellung von GPLv3 auf AGPL-3.0-only

**Status am 03.11.2026: GEPLANT – NOCH NICHT LIZENZRECHTLICH UMGESETZT**

## Ziel

Mays-RIS soll für neue, hierzu rechtlich befugte Veröffentlichungen dieselbe **AGPL-3.0-only**-Community-Lizenz wie Mays Jobsearch verwenden. Für ältere RIS-Versionen bleiben bereits eingeräumte GPLv3-Rechte bestehen. Durch bloßes Ändern der `LICENSE`-Datei entsteht **keine** wirksame Berechtigung, Fremdcode umzulisenzieren.

## Voraussetzungen vor Umstellung

1. Rechte aller betroffenen Autorinnen, Autoren und Beitragenden pro Datei/Version nachvollziehbar klären.
2. Übernommene GPL-Komponenten, Bibliotheken, Assets, Installer, Agenten und Terraform-Module abgrenzen; Fremdcode unter seiner Lizenz belassen oder nötige Erlaubnis einholen.
3. Kombinationen mit AGPL-/GPL-Bestandteilen fachlich bewerten. Eine API-Schnittstelle ist nicht automatisch eine rechtliche Trennlinie.
4. Umstellungs-Commit, Datum, betroffene Pfade, Ausnahmen, SPDX-Hinweise und Tag festhalten.
5. Erst danach die bestehende `LICENSE` durch den vollständigen, **unveränderten** Originaltext der GNU AGPLv3 ersetzen und Repo-Hinweise konsistent anpassen.
6. Release- und Lizenzdateien prüfen; geänderten Stand committen und veröffentlichen.

Die Original-AGPLv3 steht bei [GNU](https://www.gnu.org/licenses/agpl-3.0.html). Das bereits unter AGPL veröffentlichte Jobsearch-Repository enthält den vollständigen Text in [`LICENSE.md`](https://github.com/maynowak/mays-jobsearch/blob/main/LICENSE.md).

## Premium und Enterprise

AGPL lässt kommerzielle Nutzung zu und erzwingt **keine** Lizenzgebühr. Für kostenpflichtige gehostete Dienste gelten getrennte Verträge. Neue rechtlich eigenständige und gesondert lizenzierte Premium-Komponenten können proprietär entwickelt werden, soweit ihre Kombination mit GPL-/AGPL-Code dies erlaubt; sie gehören nicht automatisch zur GNU-Codebasis.

Referenzen: [GNU-Lizenzkompatibilität](https://www.gnu.org/licenses/license-compatibility.en.html), [GNU-Lizenz-FAQ](https://www.gnu.org/licenses/gpl-faq.en.html), [GNU-AGPLv3](https://www.gnu.org/licenses/agpl-3.0.html).
