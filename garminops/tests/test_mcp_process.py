import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_real_mcp_process_discovery_status_and_unknown_write(tmp_path, monkeypatch):
    # Isolated HOME proves this test neither loads a personal session nor calls Garmin.
    import os
    env = dict(os.environ, HOME=str(tmp_path))
    params = StdioServerParameters(command=sys.executable,
        args=["-m", "garminops.cli", "serve", "--region", "com"], env=env)
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()
            tools = await client.list_tools()
            names = {t.name for t in tools.tools}
            assert names == {"garmin_connection_status", "garmin_account_identity", "garmin_search_tools", "garmin_describe_tool", "garmin_read_tool", "garmin_write_tool"}
            catalog = (await client.call_tool("garmin_search_tools", {"query": ""})).structuredContent
            assert catalog["total"] == 151
            ids = {row["operation"] for row in catalog["operations"]}
            assert {"garmin_get_workouts", "garmin_get_scheduled_workouts", "garmin_update_measurement_system"} <= ids
            assert "garmin_delete_activity" not in ids
            page = (await client.call_tool("garmin_search_tools", {"query": "", "start": 150, "limit": 10000})).structuredContent
            assert len(page["operations"]) == 1 and page["next_start"] is None
            chinese = (await client.call_tool("garmin_search_tools", {"query": "训练模板"})).structuredContent
            assert "garmin_get_workouts" in {row["operation"] for row in chinese["operations"]}
            description = (await client.call_tool("garmin_describe_tool", {"operation": "garmin_get_workouts"})).structuredContent
            call = {"operation": description["operation"], "schema_hash": description["schema_hash"], "arguments": {}}
            crossed = await client.call_tool("garmin_write_tool", call)
            assert crossed.structuredContent["error"] == "operation_category_mismatch"
            stale = await client.call_tool("garmin_read_tool", {**call, "schema_hash": "stale"})
            assert stale.structuredContent["error"] == "schema_mismatch"
            unknown = await client.call_tool("garmin_describe_tool", {"operation": "garmin_delete_activity"})
            assert unknown.structuredContent["error"] == "operation_not_registered"
            missing_gateway = await client.call_tool("garmin_read_tool", call)
            assert missing_gateway.structuredContent["error"] == "login_required"
            status = await client.call_tool("garmin_connection_status", {})
            assert not status.isError
            assert status.structuredContent["region"] == "garmin.com"
            assert status.structuredContent["session_file_present"] is False
            assert status.structuredContent["delivery_target"] == "desktop local plugin with local Garmin login"
            assert status.structuredContent["chatgpt_remote_connection"] == "outside requested desktop-local scope"
            issue = status.structuredContent["known_issues"][0]
            assert issue["id"] == "KI-001" and issue["release_blocker"] is False
            assert issue["testing"] == "stopped by user; explicit reopening required"
            assert status.structuredContent["deferred_todos"] == ["garmin.cn business validation", "Connect+-exclusive features"]
            missing = await client.call_tool("garmin_get_workouts", {})
            assert missing.isError
            assert missing.structuredContent["error"] == "login_required"
            denied = await client.call_tool("garmin_delete_activity", {"activity_id": "123"})
            assert denied.isError


async def test_running_mcp_follows_single_selected_region(tmp_path):
    import json, os
    env=dict(os.environ,HOME=str(tmp_path))
    params=StdioServerParameters(command=sys.executable,
        args=['-m','garminops.cli','serve'],env=env)
    config=tmp_path/'.config/transbridge/garmin/connection.json'
    config.parent.mkdir(parents=True)
    async with stdio_client(params) as (r,w):
        async with ClientSession(r,w) as c:
            await c.initialize()
            before=await c.call_tool('garmin_connection_status',{})
            assert before.structuredContent['region']=='garmin.com'
            config.write_text(json.dumps({'region':'cn'}))
            after=await c.call_tool('garmin_connection_status',{})
            assert after.structuredContent['region']=='garmin.cn'
            missing=await c.call_tool('garmin_get_workouts',{})
            assert missing.structuredContent['error']=='login_required'
            assert '--region cn' in missing.structuredContent['action']
