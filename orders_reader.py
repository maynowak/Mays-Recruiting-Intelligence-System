"""
RIS Orders Reader — Mays-Orders Integration RC4

Verantwortlich für das Lesen und Validieren von Mays-Orders Bestellungen.
Enthält das Mapping von Mays-Orders-Format nach RIS-interne Format.
Niemals Schreiboperationen durchführen; Lesen und Validierung ausschließlich.
"""

from validation import validate_create_order, validate_order_type
from order_service import OrderService
from errors import validation_error, order_not_found
from order_types import DEFAULT_ORDER_TYPE, GSI1_PK, GSI2_NAME, GSI2_PK_PREFIX, ORDER_ID_PREFIX, ORDER_SK, TABLE_INDEX_NAME
import json
import logging

logger = logging.getLogger(__name__)

# Builder-Pin: 016cdfd (unverändert, RC4-kompatibel)
BUILDER_PIN = "016cdfd"

# Mapping von Mays-Orders SKUs zu RIS Dienst-Namen
SKU_SERVICE_MAP = {
    "ATS": "ats",
    "CV-PARSING": "cv_parsing",
    # Erweiterungen nur nach expliziter Vereinbarung
}


def map_mo_order_to_ris_payload(order_data: dict) -> dict:
    """
    Konvertiert einen Mays-Orders Order-Dict in den RIS-internen Payload.
    
    Liefert:
    - orderType: "agent.execution"
    - items mit sku-Klassifizierung
    - orderDescription: JSON-serialisiertes RIS-agentOrder (max 1.024 Zeichen)
    """
    # 1. orderType festlegen
    order_type = "agent.execution"
    
    # 2. SKU zu Service mapping
    items = order_data.get("items", [])
    for item in items:
        sku = item.get("sku", "")
        service = SKU_SERVICE_MAP.get(sku)
        if service:
            item["service"] = service
            break  # V1: Erste Position verwenden
    
    # 3. agentOrder nach RIS-Schema zusammenbauen
    agent_order = {
        "service": SKU_SERVICE_MAP.get(items[0].get("sku", ""), "generic") if items else "generic",
        "capability": order_data.get("capability", "default"),
        "inputData": order_data.get("inputData", {})
    }
    
    # 4. orderDescription serialisieren (Länge beachten)
    description_payload = {
        "agentOrder": agent_order,
        "mappings": {
            "source": "mays-orders-v1",
            "sku_present": [item.get("sku") for item in items if item.get("sku")]
        }
    }
    
    # 5. Länge prüfen und trimmen
    description_json = json.dumps(description_payload, sort_keys=True)
    MAX_DESC = 1024
    if len(description_json) > MAX_DESC:
        description_json = description_json[:MAX_DESC - 1] + "..."
    
    return {
        "orderType": order_type,
        "items": items,
        "orderDescription": description_json
    }


def parse_ris_order_description(order_description: str) -> dict:
    """
    Parst den orderDescription-Feld zurück zu einem validierten dict.
    """
    try:
        payload = json.loads(order_description)
    except json.JSONDecodeError as e:
        raise validation_error(f"Ungültige JSON in orderDescription: {e}")
    
    # Validation gegen RIS-Schema
    agent_order = payload.get("agentOrder", {})
    if not agent_order.get("service"):
        raise validation_error("agentOrder.service fehlt in orderDescription")
    
    if not agent_order.get("capability"):
        raise validation_error("agentOrder.capability fehlt in orderDescription")
    
    return {
        "service": agent_order["service"],
        "capability": agent_order["capability"],
        "inputData": agent_order.get("inputData", {}),
        "mappings": payload.get("mappings", {})
    }


def validate_order_description(length: int = 1024) -> bool:
    """Prüft, ob eine orderDescription den Spezifikationen entspricht."""
    # Einfache Validierung der Struktur
    pass  # Wird im konkreten Anwendungsfall ergänzt