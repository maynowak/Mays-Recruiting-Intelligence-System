"""
RIS Agent Order — Mays-Orders Integration RC4

Verarbeitet den agentOrder-Validierungs- und Serialisierungslogik.
Enthält die zentrale Validierungslogik für Bestellpositionen.
Keine Duplikate von Dispatch- oder Queue-Logik; nutzt bestehende RIS-Komponenten.
"""

from validation import validate_create_order, validate_order_type, validation_error
from order_service import OrderService
from errors import conflicted_update, invalid_transition, json_default, order_not_found
from order_types import DEFAULT_ORDER_TYPE
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


def validate_agent_order(agent_order: dict) -> dict:
    """
    Validiert einen agentOrder nach RIS-Schema.
    
    Erforderliche Felder:
    - service: RIS-Dienst-Name (z.B. "ats", "cv_parsing")
    - capability: Capability-String
    - inputData: Eingabedaten-Objekt
    """
    # Grundlegende Validierung
    if not agent_order.get("service"):
        raise validation_error("agentOrder.service ist erforderlich")
    
    if not agent_order.get("capability"):
        raise validation_error("agentOrder.capability ist erforderlich")
    
    if not agent_order.get("inputData"):
        raise validation_error("agentOrder.inputData ist erforderlich")
    
    # SKU zu Service Mapping prüfen (falls vorhanden)
    service = agent_order.get("service", "")
    if service not in SKU_SERVICE_MAP.values() and service != "generic":
        logger.warning(f" unbekannter service: {service}")
    
    return {
        "service": service,
        "capability": agent_order["capability"],
        "inputData": agent_order["inputData"]
    }


def map_sku_to_service(sku: str) -> str:
    """Mappe Mays-Orders SKU zu RIS Service-Namen."""
    return SKU_SERVICE_MAP.get(sku, "generic")


def create_agent_order_payload(order_data: dict) -> dict:
    """
    Erstellt einen validierten agentOrder-Payload aus Mays-Orders-Daten.
    
    V1: Exakt eine ausführbare Agentenposition pro Bestellung.
    """
    # 1. SKU extrahieren und zu Service mapppen
    items = order_data.get("items", [])
    service = "generic"
    if items and items[0].get("sku"):
        service = map_sku_to_service(items[0].get("sku", ""))
    
    # 2. agentOrder zusammenbauen
    agent_order = {
        "service": service,
        "capability": order_data.get("capability", "default"),
        "inputData": order_data.get("inputData", {})
    }
    
    # 3. Validierung
    validated = validate_agent_order(agent_order)
    
    return validated


# WICHTIG: Kein zweiter Dispatcher, keine zusätzlichen Queues,
# keine RIS-Sonderfelder in Mays-Orders.
# Bestehende Komponenten (OrdersPort, Dispatch, AgentBody, Result-Consumer)
# werden uneingeschränkt weiterverwendet.