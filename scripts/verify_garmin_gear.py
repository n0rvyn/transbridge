"""Opt-in MCP roundtrip for one synthetic unused gear item on an authorized account."""
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
                    pending.update(returned_ids(payload, 'uuid'))
                if result.isError:
                    print(json.dumps({'failed_operation':name, 'error':payload.get('error'), 'http_status':payload.get('http_status'), 'last_request':payload.get('last_request'), 'completed_count':len(payload.get('completed_requests', []))}), flush=True)
                    raise RuntimeError(name+' failed; inspect returned resource IDs before repeating.')
                return payload
            identity = await call('account_identity')
            if identity['account_id'] != args.expected_account:
                raise RuntimeError('Account mismatch; no resource operations sent.')
            base = {'expected_account': args.expected_account}
            async def inventory():
                rows = []
                for status in ('ACTIVE', 'RETIRED'):
                    start = 0
                    while True:
                        page = (await call('get_gear_items', {'start':start, 'limit':20, 'status':status}))['data']
                        if not page:
                            break
                        rows.extend(page)
                        start += len(page)
                return rows
            async def activities():
                rows = []
                while True:
                    page = (await call('get_activities', {'start':len(rows), 'limit':100}))['data']
                    if not page:
                        return rows
                    rows.extend(page)
            before = await inventory(); history = await activities()
            async def defaults():
                return (await call('get_gear_default_choices', {'gear_type':'SHOES'}))['data']
            async def associations():
                rows = {}
                for activity in history:
                    aid = activity['activityId']
                    rows[aid] = (await call('get_activity_gear', {'activity_id':aid}))['data']
                return rows
            original_defaults = await defaults() if args.verify_defaults else None
            original_associations = await associations() if args.verify_defaults else None
            if args.verify_defaults and original_defaults:
                raise RuntimeError('Test requires no pre-existing shoe defaults; no writes sent.')
            name = 'OPENCON_TEST_'+uuid4().hex
            report = {}
            try:
                definition = dict(uuid=None,gearType='SHOES',brand='OPENCON_TEST',model=None,name=name,
                    firstUseDate=args.first_use_date,usageType='NONE',maxUsageDistanceMeters=0,
                    maxUsageDurationSeconds=0,maxUsageDate=None,associatedActivityTypes=None,notes='Synthetic unused gear.')
                created = await call('create_gear', base | {'gear':definition}, capture=True)
                report['create_verified'] = created['verified']
                gid = created['data']['uuid']
                read = await call('get_gear_item', {'uuid':gid})
                report['read_verified'] = read['data'] == created['data']
                linked=await call('get_gear_activities',{'gearUUID':gid,'start':0,'limit':20})
                report['gear_activities_read_verified']=linked['data']==[]
                stats=await call('get_gear_stats',{'gearUUID':gid})
                report['gear_stats_read_verified']=(stats['data']['totalActivities']==0 and stats['data']['totalDistance']==0)
                updated = await call('update_gear', base | {'uuid':gid, 'changes':{'name':name+'_EDITED'}})
                report['update_verified'] = updated['verified']
                if args.threshold_date:
                    for usage,fields in [('DISTANCE',{'maxUsageDistanceMeters':1000}),
                            ('DURATION',{'maxUsageDurationSeconds':3600}),
                            ('DATE',{'maxUsageDate':args.threshold_date}),('NONE',{})]:
                        changes={'usageType':usage,'maxUsageDistanceMeters':0,
                                 'maxUsageDurationSeconds':0,'maxUsageDate':None}|fields
                        result=await call('update_gear',base|{'uuid':gid,'changes':changes})
                        report[usage+'_verified']=result['verified']
                for status in ('RETIRED','ACTIVE'):
                    result=await call('set_gear_status',base|{'uuid':gid,'status':status})
                    report[status+'_verified']=result['verified']
                if args.verify_defaults:
                    selected=[{'activityTypeKey':'running','defaultGear':True,'preferredGear':False}]
                    saved=await call('set_gear_defaults',base|{'uuid':gid,'activities':selected})
                    report['set_defaults_verified']=saved['verified']
                    choices=await defaults()
                    report['default_mapping_read_verified']=choices==[{'activityTypeKey':'running','defaultGearUUIDs':[gid]}]
                    cleared=await call('set_gear_defaults',base|{'uuid':gid,'activities':[]})
                    report['clear_defaults_verified']=cleared['verified']
            finally:
                errors = []
                for gid in sorted(pending):
                    try:
                        current = await call('get_gear_item', {'uuid':gid})
                        if current['data'].get('associatedActivityTypes'):
                            await call('set_gear_defaults',base|{'uuid':gid,'activities':[]})
                        if current['data']['status']=='RETIRED':
                            await call('set_gear_status', base|{'uuid':gid,'status':'ACTIVE'})
                        deleted = await call('delete_gear', base | {'uuid':gid})
                        report['delete_verified'] = deleted['verified']
                    except Exception:
                        errors.append(gid)
                report['original_gear_list_restored'] = await inventory() == before
                report['activity_list_unchanged'] = await activities() == history
                if args.verify_defaults:
                    report['original_defaults_restored']=await defaults()==original_defaults
                    report['historical_gear_associations_unchanged']=await associations()==original_associations
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
    parser.add_argument('--first-use-date', required=True)
    parser.add_argument('--threshold-date', help='Also verify all usage tracking types with this explicit date threshold.')
    parser.add_argument('--verify-defaults', action='store_true', help='Verify set/read/clear defaults and compare every historical activity gear association.')
    asyncio.run(verify(parser.parse_args()))
