"""Opt-in MCP roundtrip for one future synthetic planning note on an authorized account."""
import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from verify_garmin_live import returned_ids


async def verify(args):
    root = args.plugin.resolve()
    config = json.loads((root/'mcp.json').read_text())['mcpServers']['garmin']
    params = StdioServerParameters(command=config['command'], cwd=str(root),
        args=[x.replace('${PLUGIN_ROOT}', str(root)) for x in config['args']] + ['--region', args.region])
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()
            pending = set()
            async def call(name, arguments=None, capture=False):
                result = await client.call_tool('garmin_'+name, arguments or {})
                payload = result.structuredContent or {}
                if capture:
                    pending.update(returned_ids(payload, 'id'))
                if result.isError:
                    raise RuntimeError(name+' failed; inspect returned resource IDs before repeating.')
                return payload
            identity = await call('account_identity')
            if identity['account_id'] != args.expected_account:
                raise RuntimeError('Account mismatch; no resource operations sent.')
            base = {'expected_account': args.expected_account}
            async def calendars():
                months = {day[:7] for day in (args.start_date, args.move_date)}
                return {month:(await call('get_scheduled_workouts', {'year':int(month[:4]), 'month':int(month[5:])}))['data'] for month in months}
            async def activities():
                rows = []
                while True:
                    page = (await call('get_activities', {'start':len(rows), 'limit':100}))['data']
                    if not page:
                        return rows
                    rows.extend(page)
            before = await calendars(); history = await activities()
            name = 'OPENCON_TEST_'+uuid4().hex
            report = {}
            try:
                created = await call('create_calendar_note', base | {'name':name, 'content':'Synthetic future planning note.', 'day':args.start_date}, capture=True)
                report['create_verified'] = created['verified']
                gid = created['data']['id']
                read = await call('get_calendar_note', {'note_id':gid})
                report['read_verified'] = read['data'] == created['data']
                updated = await call('update_calendar_note', base | {'note_id':gid, 'changes':{'noteName':name+'_EDITED', 'date':args.move_date}})
                report['update_verified'] = updated['verified']
            finally:
                errors = []
                for gid in sorted(pending):
                    try:
                        deleted = await call('delete_calendar_note', base | {'note_id':gid})
                        report['delete_verified'] = deleted['verified']
                    except Exception:
                        errors.append(gid)
                report['original_calendars_restored'] = await calendars() == before
                report['activity_list_unchanged'] = await activities() == history
                if errors:
                    report['cleanup_required_ids'] = errors
                print(json.dumps(report), flush=True)
                if errors or not all(report.values()):
                    raise RuntimeError('Verification or cleanup incomplete; inspect before another write.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin', type=Path, required=True)
    parser.add_argument('--region', choices=['com','cn'], required=True)
    parser.add_argument('--expected-account', required=True)
    parser.add_argument('--start-date', required=True)
    parser.add_argument('--move-date', required=True)
    asyncio.run(verify(parser.parse_args()))
