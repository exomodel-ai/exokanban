"""
ExoKanban MCP Agent Client

Routes free-text prompts through an agentic loop that calls MCP tools in
sequence, enabling multi-step reasoning (e.g. find_card → update_card → move_card
from a single natural-language prompt), unlike the single-call master_prompt.

Transport (controlled by MCP_URL env var):
  - In-process (default, no server needed): imports the FastMCP app directly
    from mcp_server. Tools run in the same process sharing the DB session.
  - HTTP: set MCP_URL=http://localhost:8000/mcp. Requires python mcp_server.py
    to be running. Useful when the server is on a separate machine or process.

Usage in main.py:
    from mcp_client import run_agentic_prompt
    result, new_card_id = await run_agentic_prompt(msg, self._current_card_id)
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastmcp import Client
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

load_dotenv()

logger = logging.getLogger(__name__)

_MODEL_ID  = os.getenv("MY_LLM_MODEL", "google_genai:gemini-2.5-flash-lite")
_MCP_URL   = os.getenv("MCP_URL", "")
_MCP_TOKEN = os.getenv("MCP_AUTH_TOKEN", "")

_SYSTEM_PROMPT = (
    "You are a Kanban board AI agent. Evaluate the user request and call the "
    "appropriate MCP tool(s) to fulfill it. You may chain multiple tools in "
    "sequence when the task requires it (e.g. find a card, then update it, "
    "then move it).\n\n"
    "RULES:\n"
    "- For tools that accept a 'prompt' argument, pass the user's original "
    "wording verbatim — never paraphrase it.\n"
    "- Output the tool result as-is when it is already well-formatted text.\n"
    "- If the request is out of scope, reply: "
    "'I cannot fulfill this request based on the available tools.'"
)

_JSON_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _schema_to_model(schema: dict, tool_name: str) -> type[BaseModel]:
    """Builds a Pydantic BaseModel from a JSON Schema properties dict."""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields: dict = {}
    for prop, spec in properties.items():
        py_type = _JSON_TYPE_MAP.get(spec.get("type", "string"), str)
        desc = spec.get("description", "")
        default = ... if prop in required else spec.get("default", None)
        fields[prop] = (py_type, Field(default, description=desc))
    return create_model(f"_{tool_name}_args", **fields)


def _build_lc_tools(mcp_tools, client: Client) -> list[StructuredTool]:
    """Converts MCP tool definitions to async LangChain StructuredTools."""
    lc_tools = []
    for mt in mcp_tools:
        name = mt.name
        desc = mt.description or name
        schema = mt.inputSchema or {"type": "object", "properties": {}}

        # Capture name and client in the closure by default-arg binding.
        async def _acall(_name=name, _client=client, **kwargs) -> str:
            result = await _client.call_tool(_name, kwargs)
            if result.is_error:
                return f"Error: {result.data}"
            return result.data or ""

        lc_tools.append(
            StructuredTool(
                name=name,
                description=desc,
                coroutine=_acall,
                args_schema=_schema_to_model(schema, name),
            )
        )
    return lc_tools


def _extract_card_id(messages: list) -> Optional[int]:
    """Scans agent messages for the last tool call that contained a card_id."""
    card_id = None
    for msg in messages:
        calls = getattr(msg, "tool_calls", None) or []
        for call in calls:
            args = call.get("args", {}) if isinstance(call, dict) else getattr(call, "args", {})
            if "card_id" in args:
                try:
                    card_id = int(args["card_id"])
                except (TypeError, ValueError):
                    pass
    return card_id


def _final_text(messages: list) -> str:
    """Extracts the last non-empty text content from the agent message list."""
    for msg in reversed(messages):
        content = getattr(msg, "content", "")
        if content and isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            texts = [p.get("text", "") for p in content if isinstance(p, dict)]
            joined = " ".join(t for t in texts if t).strip()
            if joined:
                return joined
    return ""


async def run_agentic_prompt(
    prompt: str,
    current_card_id: Optional[int] = None,
) -> tuple[str, Optional[int]]:
    """
    Routes a free-text prompt through an agentic MCP tool loop.

    Returns (result_text, new_current_card_id). new_current_card_id is the
    card_id seen in the last tool call that used one, or current_card_id if
    none was encountered.
    """
    transport = _MCP_URL if _MCP_URL else None
    client_kwargs = {}
    if _MCP_URL and _MCP_TOKEN:
        client_kwargs["auth"] = _MCP_TOKEN

    if transport is None:
        # In-process: import the FastMCP app — no HTTP server required.
        from mcp_server import mcp as _mcp_app  # noqa: PLC0415
        transport = _mcp_app

    async with Client(transport, **client_kwargs) as client:
        mcp_tools = await client.list_tools()
        lc_tools = _build_lc_tools(mcp_tools, client)

        llm = init_chat_model(_MODEL_ID)
        agent = create_agent(llm, tools=lc_tools, system_prompt=_SYSTEM_PROMPT)

        context_prefix = f"(current card id: {current_card_id}) " if current_card_id else ""
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": context_prefix + prompt}]},
            config={"recursion_limit": 15},
        )

    messages = result.get("messages", [])
    text = _final_text(messages)

    if not text:
        logger.warning("MCP agent returned empty response for prompt: %s", prompt[:80])
        text = "The agent processed the request but did not return a text response."

    new_card_id = _extract_card_id(messages) or current_card_id
    return text, new_card_id
