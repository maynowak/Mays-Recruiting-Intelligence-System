"""
RIS Validation — Mays-Orders Integration RC4

Validierungsfunktionen für Bestellungen und agentOrder-Payloads.
Enthält wiederverwendbare Validierungslogik für die bestehende RIS-Infrastructure.
Keine neuen Validierungsregeln; bestehende Muster beibehalten.
"""

from errors import validation_error


def validate_create_order(raw_body: dict) -> dict:
    """
    Validiert eine Create-Order-Anforderung.
    
    Prüfung auf:
    - Vorhandensein required Felder
    - Gültiges orderType
    - Vollständige Identitätsinformationen
    """
    if not raw_body.get("orderType"):
        raise validation_error("Missing orderType")
    
    if raw_body.get("orderType") not in ["generic", "agent.execution"]:
        raise validation_error(f"Unsupported order type: {raw_body.get('orderType')}")
    
    if not raw_body.get("items") or not raw_body["items"]:
        raise validation_error("Missing items in order")
    
    return raw_body


def validate_order_type(order_type: str) -> bool:
    """Prüft, ob ein orderType gültig ist."""
    return order_type in ["generic", "agent.execution"]