#!/usr/bin/env python3
"""Idempotenter Seeder für den persistenten RIS Agent Catalog.

Gate RIS-B4-PERSISTENT-AGENT-CATALOG-WRITER-AND-SEEDER-01.

Warum dieser Seeder existiert: Discovery-07 hat belegt, dass für die
Tabelle `mays-ris-*-agent-catalog` **kein** Schreibpfad existierte.
Der Read Path (CatalogAdapter / handler._init_catalog) war vollständig,
fail-closed und leer. Dieser Seeder ist der explizite, manuelle
Provisioning-Schritt, der sie erstmals befüllt.

Architekturgrenze (unverändert):
    Runtime-Registry  ──hier, explizit, einmalig──>  CatalogWriter  ──>  DynamoDB
Es wird NICHTS automatisch persistiert. Dieser Seeder liest die
bestehende Runtime-Definition und schreibt sie einmalig in den
persistenten Catalog. Die Runtime-Registry selbst bleibt unberührt
(kein Import von register_* in den Worker-Pfad).

Seed-Agent: `reference_agent`
    Der bereits im Repo vorhandene kanonische Referenz-/Nachweis-Agent
    (agents/runtime/pipeline.py:53 REFERENCE_AGENT_ID, Capability
    "reference.echo", Beschreibung "Technischer Nachweis-Agent (Echo,
    keine Domain-Logik)"). Es wird KEIN neuer Agent-Typ erfunden — der
    Seeder übernimmt 1:1 die bestehende Descriptor-Definition.

Synthetik: keine personenbezogenen Daten, keine Credentials, keine
Secrets, keine Tokens. Der Eintrag beschreibt ausschließlich eine
Agent-Fähigkeit.

Idempotenz: `agentId` ist der Hash-Key der Tabelle. Ein erneuter Lauf
überschreibt dieselbe Zeile; es entsteht kein Duplikatbestand. Mit
``--skip-existing`` wird eine vorhandene Zeile unangetastet gelassen
(Konvention des Repo-Seeder seed_orders.py).

Retention: Die Tabelle hat TTL auf `expiresAt`, dieses Feld wird
bewusst NICHT geschrieben (sonst würde der Seed still verschwinden).
Retention-/Löschpfad ist ein separates Gate (Discovery-07) — der
Seeder erfindet dafür keine Architektur. Der Eintrag bleibt damit
dauerhaft und synthetisch bestehen; `scripts/unseed_agent_catalog.py`
entfernt ihn wieder über denselben Produktpfad.

Verwendung:
    python3 installer/scripts/seed_agent_catalog.py --dry-run
    python3 installer/scripts/seed_agent_catalog.py \
        --table mays-ris-dev-agent-catalog

Marshalling: boto3 **resource**-API (identisch zum produktiven
Lambda-Pfad und zu seed_orders.py) — plain dicts werden automatisch in
DynamoDB-Attributwerte übersetzt.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from agents.ecosystem.agent_status import is_executable_status  # noqa: E402
from agents.ecosystem.catalog_writer import (  # noqa: E402
    CatalogWriteError,
    CatalogWriter,
    catalog_item_from_descriptor,
)

SEED_AGENT_ID = "reference_agent"


def build_seed_descriptor():
    """Return the existing Reference-Agent descriptor, unchanged.

    Sourced from agents.runtime.pipeline so the seed can never drift
    from the canonical runtime definition. Nothing is hardcoded twice.
    """
    from agents.ecosystem.registry import (
        AgentDescriptor,
        AgentStatus,
        ExecutionProfile,
    )
    from agents.runtime.pipeline import (
        BODY_VERSION,
        REFERENCE_AGENT_ID,
        REFERENCE_CAPABILITY,
        RUNTIME_LAMBDA,
    )

    if REFERENCE_AGENT_ID != SEED_AGENT_ID:
        raise CatalogWriteError(
            f"seed agent id mismatch: module says {REFERENCE_AGENT_ID!r}, "
            f"seeder expects {SEED_AGENT_ID!r} — refusing to guess")

    return AgentDescriptor(
        agent_id=REFERENCE_AGENT_ID,
        name=REFERENCE_AGENT_ID,
        version="1.0.0",
        status=AgentStatus.ACTIVE,
        capabilities=[REFERENCE_CAPABILITY],
        supported_bodies=[BODY_VERSION],
        supported_runtimes=[RUNTIME_LAMBDA],
        execution_profile=ExecutionProfile.LAMBDA,
        risk_level="low",
        description="Technischer Nachweis-Agent (Echo, keine Domain-Logik)",
    )


def seed(table_name: str, skip_existing: bool = False,
         dry_run: bool = False,
         dynamodb=None) -> Dict[str, Any]:
    """Write the seed entry. Deterministic and idempotent."""
    descriptor = build_seed_descriptor()
    item = catalog_item_from_descriptor(descriptor)
    agent_id = item["agentId"]

    writer = CatalogWriter(table_name=table_name, dynamodb=dynamodb)

    if skip_existing and not dry_run:
        existing = writer.table.get_item(Key={"agentId": agent_id}).get("Item")
        if existing:
            return {"outcome": "skipped", "agentId": agent_id,
                    "status": existing.get("status")}

    if dry_run:
        return {"outcome": "dry-run", "agentId": agent_id, "item": item}

    written = writer.put_agent(item)

    # Read-back through the EXISTING read path, not from the write result.
    from agents.ecosystem.catalog_adapter import CatalogAdapter
    adapter = CatalogAdapter(table_name=table_name, dynamodb=dynamodb)
    read_back = adapter.get_all_agents().get(agent_id)

    return {
        "outcome": "written",
        "agentId": written["agentId"],
        "status": written["status"],
        "executable": is_executable_status(written["status"]),
        "capabilities": written["capabilities"],
        "readback_found": read_back is not None,
        "readback_status": (read_back or {}).get("status"),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Idempotenter Seeder für den persistenten RIS "
                    "Agent Catalog (Gate B4).")
    parser.add_argument("--table", default=os.environ.get(
        "AGENT_CATALOG_TABLE"),
        help="agent catalog table name "
             "(default: $AGENT_CATALOG_TABLE)")
    parser.add_argument("--skip-existing", action="store_true",
                        help="vorhandene Zeile unangetastet lassen")
    parser.add_argument("--dry-run", action="store_true",
                        help="nur projizieren, nicht schreiben")
    args = parser.parse_args(argv)

    if not args.table:
        parser.error("table name required (--table or $AGENT_CATALOG_TABLE)")

    try:
        result = seed(args.table, skip_existing=args.skip_existing,
                      dry_run=args.dry_run)
    except CatalogWriteError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1

    print(f"  Seed-Agent        : {result['agentId']}")
    print(f"  Outcome           : {result['outcome']}")
    if result["outcome"] != "dry-run":
        print(f"  Status            : {result.get('status')}")
        print(f"  Capabilities      : {result.get('capabilities')}")
        print(f"  Read-back gefunden: {result.get('readback_found')}")
        print(f"  Read-back Status  : {result.get('readback_status')}")
    else:
        item = result["item"]
        print(f"  Status (geplant)  : {item['status']}")
        print(f"  Capabilities      : {item['capabilities']}")
        print(f"  written fields    : {sorted(item)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
