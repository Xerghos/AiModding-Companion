from enum import Enum

class AiMode(Enum):
    STANDARD = "standard"
    ROUTER_STRICT = "router_strict"
    CREATIVE = "creative"
    REASONING = "reasoning"

class SwarmAgent(Enum):
    ROUTER = "ROUTER"
    ARCHITECT = "ARCHITECT"
    CODER = "CODER"
    REVIEWER = "REVIEWER"
    WRITER = "WRITER"
    GUARDIAN = "GUARDIAN"

class QuotaExceededException(Exception): pass
class SafetyBlockedException(Exception): pass
class ProviderError(Exception): pass