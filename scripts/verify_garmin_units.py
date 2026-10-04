"""Opt-in live MCP measurement-system verification with exact value restoration."""
import argparse
import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client



async def verify(args):
    root = args.plugin.resolve()
    config = json.loads((root/'mcp.json').read_text())['mcpServers']['garmin']
    params = StdioServerParameters(command=config['command'], cwd=str(root),
        args=[part.replace('${PLUGIN_ROOT}', str(root)) for part in config['args']] +
             ['--region', args.region])
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()
            async def call(name, arguments=None):
                result = await client.call_tool('garmin_'+name, arguments or {})
                if result.isError:
                    raise RuntimeError(name+' returned a tool error; inspect current state before repeating.')
                return result.structuredContent
            identity = await call('account_identity')
            if identity['account_id'] != args.expected_account:
                raise RuntimeError('Account mismatch; no resource operations sent.')
            original = (await call('get_user_profile'))['data']
            prior_units = original['userData']['measurementSystem']
            if not isinstance(prior_units,str) or not prior_units or prior_units == args.measurement_system:
                raise ValueError('Choose a different explicit unit system; original must be restorable.')
            base = {'expected_account': args.expected_account}
            async def activities():
                values = []
                while True:
                    page = (await call('get_activities', {'start': len(values), 'limit': 100}))['data']
                    if not page:
                        return values
                    values.extend(page)
            history = await activities()
            report = {}
            try:
                changed = await call('update_measurement_system', base | {
                    'measurement_system': args.measurement_system})
                report['requested_change_verified'] = changed['verified']
                report['fresh_unit_read_verified'] = (await call('get_unit_system'))['data'] == args.measurement_system
            finally:
                restored = await call('update_measurement_system', base | {
                    'measurement_system': prior_units})
                report['restore_verified'] = restored['verified']
            report['entire_profile_restored'] = (await call('get_user_profile'))['data'] == original
            report['fresh_unit_read_restored'] = (await call('get_unit_system'))['data'] == prior_units
            report['activity_list_unchanged'] = await activities() == history
            print(json.dumps(report))
            if not all(report.values()):
                raise RuntimeError('Post-test state differs; inspect before further changes.')


def main():
    parser = argparse.ArgumentParser(description='Modify then restore one measurement-system field on an explicitly authorized test account through MCP.')
    parser.add_argument('--plugin', type=Path, required=True)
    parser.add_argument('--region', choices=['com', 'cn'], required=True)
    parser.add_argument('--expected-account', required=True)
    parser.add_argument('--measurement-system', required=True)
    args = parser.parse_args()
    asyncio.run(verify(args))


if __name__ == '__main__':
    main()
