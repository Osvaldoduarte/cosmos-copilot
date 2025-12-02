import asyncio
from typing import Dict, Any

# --- Estado Global ---
STATE_LOCK = asyncio.Lock()
CONVERSATION_STATE_STORE: Dict[str, Any] = {}
