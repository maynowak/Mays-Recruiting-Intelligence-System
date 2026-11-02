# Datenschutzhinweis-Entwurf — RIS-Kontospeicherung v1

**Arbeitsentwurf — nicht juristisch freigegeben, nicht veröffentlichen**
**Version:** 1.0-draft · 2026-11-01

Dieser Entwurf betrifft nur die optionale Speicherung von Profil-, CV- und
Suchprofildaten in Mays-RIS. Er ersetzt nicht die bestehende Erklärung für
Stellensuche, Browserverarbeitung oder KI-Funktionen.

## Was und warum wird gespeichert?

Nach einer ausdrücklichen Speicheraktion können Konto-/Namensdaten, CV-
Metadaten und eine ausgewählte PDF, manuelle Suchprofile, CV-Suchprofile und
ATS-Varianten gespeichert werden. Zweck ist der spätere Abruf, die Änderung,
der Export und die Löschung der ausgewählten Daten.

Die konkrete Rechtsgrundlage und Frist werden vor produktiver Freischaltung
festgelegt. Eine Speicheraktion ist nicht automatisch eine Einwilligung für
AI-Analyse, Providerübermittlung oder jede andere Verarbeitung.

## Abgrenzung und Zugriff

Browserseitige CV-Auslese, Stellensuche und optionale KI-Analyse sind eigene
Verarbeitungsvorgänge. Die Analyse speichert nicht automatisch einen CV im
RIS-Konto. RIS verarbeitet die Kontodaten in der vorgesehenen AWS-
Infrastruktur mit serverseitiger Konto-, Tenant- und Partnerprüfung. Ein
vertrauliches RIS-Partner-Credential darf nicht im Browser liegen.

Tatsächliche Empfänger, Regionen, Unterauftragsverarbeiter und
Drittlandgarantien müssen vor Veröffentlichung anhand der produktiven
Konfiguration ergänzt werden.

## Aufbewahrung, Änderung, Export und Löschung

Es gilt keine pauschal freigegebene Frist. Jede Ressource erhält eine
zweckgebundene Retention-Regel. S3-Versionen, Backups und Logs können eigene
Fristen haben. Das Löschen des aktuellen Dokuments beweist nicht automatisch
die Löschung alter Versionen oder Backups.

Nach Freigabe sollen Nutzer Profile ändern, ausgewählte CVs/Profile löschen
und Auskunft/Export anfordern können. Eine vollständige Löschung wird nur für
den tatsächlich geprüften Umfang bestätigt; verbleibende Backups, gesetzliche
Pflichten oder externe Systeme werden gesondert ausgewiesen.

## Besondere Kategorien in CVs

Lebensläufe können Gesundheitsdaten, politische/religiöse Informationen,
Gewerkschaftszugehörigkeit, biometrische Angaben oder andere besondere
Kategorien enthalten. Nicht benötigte sensible Angaben sollten entfernt
werden. Vor produktiver Speicherung ist eine gesonderte Art.-9-Prüfung und
gegebenenfalls eine ausdrückliche, spezifische Entscheidung erforderlich.

## Kontolöschung und Vorbehalt

Eine Kontolöschung startet einen kontrollierten Prozess für Konto-, Profil-
und Dokumentdaten. Profilkinder, S3-Versionen/Marker, technische Restdaten,
Backups und Datenschutzbelege können eigene Behandlung benötigen. Ein
Teilstatus darf nicht als vollständige physische Löschung bezeichnet werden.

Dieser Text ist technische/redaktionelle Vorlage, keine Rechtsberatung, keine
Einwilligungserklärung und keine Freigabe für produktive Speicherung.
