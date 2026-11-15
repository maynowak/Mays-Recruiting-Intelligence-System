"""Addition Agent package (RIS-MO-ADDITION-AGENT-E2E-01)."""

from agents.addition_agent.agent import (
    ADDITION_AGENT_ID,
    ADDITION_AGENT_VERSION,
    ADDITION_CAPABILITY,
    ADDITION_WORK_TYPE,
    AdditionAgent,
    AdditionInputError,
    add_operands,
    create_addition_handler,
)
from agents.addition_agent.registry import (
    get_addition_descriptor,
    is_addition_registered,
    register_addition_agent,
)

__all__ = [
    "ADDITION_AGENT_ID",
    "ADDITION_AGENT_VERSION",
    "ADDITION_CAPABILITY",
    "ADDITION_WORK_TYPE",
    "AdditionAgent",
    "AdditionInputError",
    "add_operands",
    "create_addition_handler",
    "get_addition_descriptor",
    "register_addition_agent",
    "is_addition_registered",
]
