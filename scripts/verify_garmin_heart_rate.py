"""Opt-in live MCP heart-rate-setting verification with exact value restoration."""
import argparse
import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

FIELDS = {'maxHeartRateUsed', 'restingHeartRateUsed', 'lactateThresholdHeartRateUsed', *(f'zone{i}Floor' for i in range(1, 6))}

def reversible_change(profile, field, delta):
    if field not in FIELDS or isinstance(delta, bool) or not isinstance(delta, int) or delta == 0:
        raise ValueError('Specify one known BPM field and a nonzero integer change.')
    original = profile.get(field)
    if isinstance(original, bool) or not isinstance(original, int) or original <= 0:
        raise ValueError('Test requires an existing positive BPM value that can be restored.')
    from garminops.drafts import zone_update
    changes = {field: original + delta}
    zone_update([profile], profile['sport'], changes)
    return changes


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
            original = (await call('get_heart_rate_zones'))['data']
            profile = next(row for row in original if row['sport'] == args.sport)
            changes = reversible_change(profile, args.field, args.delta)
            base = {'expected_account': args.expected_account, 'sport': args.sport}
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
                changed = await call('update_heart_rate_zones', base | {
                    'changes': changes})
                report['requested_change_verified'] = changed['verified']
            finally:
                restored = await call('update_heart_rate_zones', base | {
                    'changes': {args.field: profile[args.field]}})
                report['restore_verified'] = restored['verified']
            report['all_profiles_restored'] = (await call('get_heart_rate_zones'))['data'] == original
            report['activity_list_unchanged'] = await activities() == history
            print(json.dumps(report))
            if not all(report.values()):
                raise RuntimeError('Post-test state differs; inspect before further changes.')


def main():
    parser = argparse.ArgumentParser(description='Modify then restore one heart-rate-setting field on an explicitly authorized test account through MCP.')
    parser.add_argument('--plugin', type=Path, required=True)
    parser.add_argument('--region', choices=['com', 'cn'], required=True)
    parser.add_argument('--expected-account', required=True)
    parser.add_argument('--sport', required=True)
    parser.add_argument('--field', choices=sorted(FIELDS), required=True)
    parser.add_argument('--delta', type=int, required=True)
    args = parser.parse_args()
    if args.delta == 0:
        parser.error('Specify a nonzero integer change for verification.')
    asyncio.run(verify(args))


if __name__ == '__main__':
    main()
