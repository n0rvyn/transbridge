from __future__ import annotations

import asyncio
import hashlib
import inspect
import json

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations
from pydantic import ValidationError

from .backend import Backend, ConnectorGarmin, LoginRequired, READ_METHODS, error_metadata
from .policy import PolicyDenied, ContractUnverified
from .writes import OPERATIONS, WriteFailure, execute, identity
from .connection import selected_region
from .errors import diagnostics, local_diagnostics, suppress_private_logs, contract_detail


def result(payload: dict, error: bool = False) -> CallToolResult:
    if error and "code" not in payload:
        payload = {**local_diagnostics(payload["error"]), **payload}
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
        structuredContent=payload, isError=error,
    )


def build_server(region: str | None = None) -> Server:
    suppress_private_logs()
    backend = Backend(region or selected_region())
    server = Server("garminops")

    async def catalog() -> list[Tool]:
        tools = [Tool(
            name="garmin_connection_status",
            description="Report development readiness, session presence and unresolved write contracts. Does not access Garmin.",
            inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
            annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
        )]
        tools.append(Tool(name="garmin_account_identity",
            description="Read the signed-in Garmin account identity. Browser profile names are unrelated.",
            inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
            annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True)))
        for name, (model, description) in OPERATIONS.items():
            tools.append(Tool(name="garmin_" + name, description=description,
                inputSchema=model.model_json_schema(),
                annotations=ToolAnnotations(readOnlyHint=False,
                    destructiveHint=name not in ("create_workout", "copy_workout", "schedule_workout", "create_goal", "create_calendar_note", "create_calendar_event", "create_gear"),
                    idempotentHint=False, openWorldHint=True)))
        for name in READ_METHODS:
            description = inspect.getdoc(getattr(ConnectorGarmin, name)) or name
            tools.append(Tool(
                name="garmin_" + name,
                description=(description + "\nRead-only. Development adapter; method-specific live evidence is recorded in docs/validation/READ_VERIFICATION.json. "
                             "Upstream pagination, date windows and chart defaults apply; do not claim completeness without checking them."),
                inputSchema=backend.models[name].model_json_schema(),
                annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                            idempotentHint=True, openWorldHint=True),
            ))
        return tools

    def gateway_schema(properties: dict, required: list[str]) -> dict:
        return {"type": "object", "properties": properties, "required": required,
                "additionalProperties": False}

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        originals = await catalog()
        tools = originals[:2]
        definitions = [
            ("search_tools", "Search the complete registered Garmin operation catalog. Returns metadata, not full schemas. Empty query lists all operations; pagination is explicit.",
             gateway_schema({"query": {"type": "string"}, "start": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}}, ["query"])),
            ("describe_tool", "Get the full parameter schema and schema_hash for an exact registered operation before calling it.",
             gateway_schema({"operation": {"type": "string"}}, ["operation"])),
            ("read_tool", "Execute an exact registered read operation using its described schema_hash and arguments. No arbitrary upstream dispatch.",
             gateway_schema({"operation": {"type": "string"}, "schema_hash": {"type": "string"}, "arguments": {"type": "object"}}, ["operation", "schema_hash", "arguments"])),
            ("write_tool", "Execute an exact registered plan/settings write using its described schema_hash and arguments. Existing account and policy checks apply; historical writes are forbidden.",
             gateway_schema({"operation": {"type": "string"}, "schema_hash": {"type": "string"}, "arguments": {"type": "object"}}, ["operation", "schema_hash", "arguments"])),
        ]
        for name, description, schema in definitions:
            tools.append(Tool(name="garmin_" + name, description=description, inputSchema=schema,
                              annotations=ToolAnnotations(readOnlyHint=name != "write_tool",
                                  destructiveHint=name == "write_tool", openWorldHint=name in ("read_tool", "write_tool"))))
        return tools

    def schema_hash(tool: Tool) -> str:
        return hashlib.sha256(json.dumps(tool.inputSchema, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> CallToolResult:
        nonlocal backend
        active = region or selected_region()
        if backend.region != active:
            backend = Backend(active)
        current = backend
        if name == "garmin_connection_status":
            return result({**current.status(), "discovery_mode": "registered_catalog", "exposed_tools": 6, "catalog_operations": len(await catalog())})
        if name in ("garmin_search_tools", "garmin_describe_tool", "garmin_read_tool", "garmin_write_tool"):
            entries = {tool.name: tool for tool in await catalog()}
            if name == "garmin_search_tools":
                if set(arguments) - {"query", "start", "limit"} or not isinstance(arguments.get("query"), str):
                    return result({"error": "invalid_arguments", "request_sent": False}, True)
                start, limit = arguments.get("start", 0), arguments.get("limit")
                if type(start) is not int or start < 0 or (limit is not None and (type(limit) is not int or limit < 1)):
                    return result({"error": "invalid_arguments", "request_sent": False}, True)
                query = arguments["query"].casefold()
                aliases = {"训练模板": "workout", "日历": "calendar", "排课": "schedule", "负荷": "load", "睡眠": "sleep", "跑步": "activities", "心率": "heart"}
                for word, replacement in aliases.items():
                    query = query.replace(word, replacement)
                terms = query.split()
                matches = [tool for tool in entries.values() if all(term in (tool.name + " " + tool.description).casefold() for term in terms)]
                page = matches[start:] if limit is None else matches[start:start + limit]
                return result({"total": len(matches), "catalog_total": len(entries), "start": start,
                               "next_start": start + len(page) if start + len(page) < len(matches) else None,
                               "operations": [{"operation": tool.name, "read_only": bool(tool.annotations.readOnlyHint),
                                               "summary": tool.description.splitlines()[0]} for tool in page]})
            expected = {"operation"} if name == "garmin_describe_tool" else {"operation", "schema_hash", "arguments"}
            if set(arguments) != expected or not isinstance(arguments.get("operation"), str):
                return result({"error": "invalid_arguments", "request_sent": False}, True)
            tool = entries.get(arguments["operation"])
            if tool is None:
                return result({"error": "operation_not_registered", "request_sent": False}, True)
            if name == "garmin_describe_tool":
                return result({"operation": tool.name, "description": tool.description, "inputSchema": tool.inputSchema,
                               "annotations": tool.annotations.model_dump(exclude_none=True), "schema_hash": schema_hash(tool)})
            if arguments["schema_hash"] != schema_hash(tool):
                return result({"error": "schema_mismatch", "request_sent": False}, True)
            if bool(tool.annotations.readOnlyHint) != (name == "garmin_read_tool"):
                return result({"error": "operation_category_mismatch", "request_sent": False}, True)
            if not isinstance(arguments["arguments"], dict):
                return result({"error": "invalid_arguments", "request_sent": False}, True)
            name, arguments = tool.name, arguments["arguments"]
        method = name.removeprefix("garmin_")
        if name != "garmin_" + method or method not in (*backend.models, *OPERATIONS, "account_identity"):
            return result({"error": "operation_not_registered", "request_sent": False}, True)
        try:
            if method == "account_identity":
                if arguments:
                    raise ValueError("Identity takes no arguments.")
                return result(await asyncio.to_thread(identity, current))
            if method in OPERATIONS:
                return result(await asyncio.to_thread(execute, current, method, arguments))
            value = await asyncio.to_thread(current.read, method, arguments)
            return result({"data": value, "region": f"garmin.{current.region}"})
        except LoginRequired:
            return result({"error": "login_required", "request_sent": False,
                           "action": f"Run garminops login --region {current.region} in your own terminal."}, True)
        except WriteFailure as exc:
            return result(exc.outcome, True)
        except (ValidationError, ValueError):
            return result({"error": "invalid_arguments", "request_sent": False}, True)
        except ContractUnverified as exc:
            return result({"error": "contract_unverified", "request_sent": False,
                           "detail": contract_detail(exc),
                           "action": "The operation contract requires further verification."}, True)
        except PolicyDenied:
            return result({"error": "policy_denied", "request_sent": False}, True)
        except Exception as exc:
            # Raw upstream error text can contain account data or credentials.
            metadata = error_metadata(exc)
            return result({**metadata, **diagnostics(exc, stage=getattr(exc, "garminops_stage", "operation"), operation=method, status=metadata.get("http_status"))}, True)

    return server


async def serve(region: str | None) -> None:
    server = build_server(region)
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


def run(region: str | None = None) -> None:
    asyncio.run(serve(region))
