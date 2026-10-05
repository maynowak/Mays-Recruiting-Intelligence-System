#!/usr/bin/env python3
"""Gegenstück zum Seeder: entfernt den Seed-Eintrag aus dem persistenten
RIS Agent Catalog.

Gate RIS-B4-PERSISTENT-AGENT-CATALOG-WRITER-AND-SEEDER-01.

Warum: Die agent_catalog-Tabelle hat TTL auf `expiresAt`, dieses Feld
wird vom Seeder bewusst NICHT geschrieben, damit der synthetische
Eintrag nicht still verschwindet. Retention-/Löschpfad ist ein
separates Gate (Discovery-07) — dieser Seeder darf deshalb nicht so
tun, als gäbe es eine Retention-Architektur. Stattdessen gibt es
diesen expliziten, manuellen Unseed.

Der Unseed geht bewusst über denselben Produktpfad (CatalogWriter /
boto3 resource-API) und löscht NUR die über den Seeder erzeugten
agentIds. Andere Catalog-Einträge werden nie berührt; ist die Tabelle
nach dem Lauf nicht leer, wird das gemeldet und der Exit-Code ist 1.

Verwendung:
    python3 installer/scripts/unseed_agent_catalog.py --table <name>
    python3 installer/scripts/unseed_agent_catalog.py --table <name> --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from agents.ecosystem.catalog_writer import (  # noqa: E402
    CatalogWriteError,
    CatalogWriter,
)

#: Nur die agentIds, die dieser Seeder erzeugt. Bewusst eine Positiv-
#: liste: kein "alles loeschen", kein Pattern-Match.
SEED_AGENT_IDS = ("reference_agent",)


def unseed(table_name: str, agent_ids=SEED_AGENT_IDS,
           dry_run: bool = False, dynamodb=None) -> dict:
    writer = CatalogWriter(table_name=table_name, dynamodb=dynamodb)
    removed, missing = [], []
    for agent_id in agent_ids:
        if dry_run:
            removed.append(agent_id)
            continue
        writer.table.delete_item(Key={"agentId": agent_id})
        removed.append(agent_id)

    remaining: List[str] = []
    if not dry_run:
        from agents.ecosystem.catalog_adapter import CatalogAdapter
        remaining = sorted(
            CatalogAdapter(table_name=table_name,
                           dynamodb=dynamodb).scan_all_agent_ids())
    return {"removed": removed, "missing": missing,
            "remaining": remaining}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Entfernt die Seed-Eintraege aus dem persistenten "
                    "RIS Agent Catalog (Gate B4).")
    parser.add_argument("--table", default=os.environ.get(
        "AGENT_CATALOG_TABLE"),
        help="agent catalog table name "
             "(default: $AGENT_CATALOG_TABLE)")
    parser.add_argument("--dry-run", action="store_true",
                        help="nur melden, nicht loeschen")
    args = parser.parse_args(argv)

    if not args.table:
        parser.error("table name required (--table or $AGENT_CATALOG_TABLE)")

    try:
        result = unseed(args.table, dry_run=args.dry_run)
    except CatalogWriteError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1

    prefix = "dry-run: " if args.dry_run else ""
    print(f"  {prefix}entfernt : {result['removed']}")
    if not args.dry_run:
        print(f"  verbleibend     : {result['remaining'] or '(leer)'}")
        if result["remaining"]:
            print("FEHLER: Tabelle nicht leer — fremde Eintraege "
                  "unberuehrt.", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
