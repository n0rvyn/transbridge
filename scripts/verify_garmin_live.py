"""Explicitly requested live plan verification; never run by the offline suite."""
import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class VerificationFailure(RuntimeError):
    pass


def returned_ids(payload, key):
    """Recover successful create IDs even when the following read-back failed."""
    candidates = [payload.get('data')]
    candidates.extend(row.get('response') for row in payload.get('completed_requests', []))
    result = set()
    for item in candidates:
        value = item.get(key) if isinstance(item, dict) else None
        if key == 'uuid' and isinstance(value, str):
            try:
                if str(UUID(value)) == value:
                    result.add(value)
            except ValueError:
                pass
        elif key != 'uuid' and type(value) is int and value > 0:
            result.add(value)
    return result


async def verify(args):
    plugin = args.plugin.resolve()
    config = json.loads((plugin/'mcp.json').read_text())['mcpServers']['garmin']
    params = StdioServerParameters(command=config['command'],
        args=[a.replace('${PLUGIN_ROOT}', str(plugin)) for a in config['args']] +
             ['--region', args.region], cwd=str(plugin))
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            async def call(name, arguments=None, capture=None):
                response = await client.call_tool('garmin_'+name, arguments or {})
                payload = response.structuredContent or {}
                if capture:
                    pending, key = capture
                    pending.update(returned_ids(payload, key))
                if response.isError:
                    raise VerificationFailure(name+': '+str(payload.get('error', 'tool error')))
                return payload

            await client.initialize()
            identity = await call('account_identity')
            if identity.get('account_id') != args.expected_account:
                raise VerificationFailure('Account mismatch; no resource operations sent.')
            base = {'expected_account': args.expected_account}
            async def rows(method):
                result = []
                while True:
                    page = (await call(method, {'start': len(result), 'limit': 100}))['data']
                    if not page:
                        return result
                    result.extend(page)

            async def templates():
                listed = await rows('get_workouts')
                return {wid: (await call('get_workout_by_id', {'workout_id': wid}))['data']
                        for wid in {item['workoutId'] for item in listed}}

            before = await templates()
            activities = await rows('get_activities')
            pending_workouts, pending_schedules = set(), set()
            report = {'region': args.region, 'identity_verified': True}
            cleanup_errors = []
            try:
                # A known real template supplies the full upstream format.
                if args.source_workout not in before:
                    raise VerificationFailure('Source workout absent; no test writes sent.')
                created = await call('copy_workout', base | {
                    'workout_id': args.source_workout,
                    'name': 'OPENCON_TEST_'+uuid4().hex,
                    'description': 'Temporary explicit connector verification'},
                    (pending_workouts, 'workoutId'))
                wid = created['data']['workoutId']
                await call('update_workout', base | {'workout_id': wid, 'changes': {
                    'description': 'Updated temporary connector verification',
                    'workoutSegments': created['data']['workoutSegments']}})
                scheduled = await call('schedule_workout', base | {
                    'workout_id': wid, 'day': args.day}, (pending_schedules, 'workoutScheduleId'))
                old_sid = scheduled['data']['workoutScheduleId']
                detail = await call('get_scheduled_workout_by_id', {'scheduled_workout_id':old_sid})
                report['scheduled_detail_read_verified'] = detail['data'] == scheduled['data']
                if not report['scheduled_detail_read_verified']:
                    raise VerificationFailure('Named scheduled-workout detail differs from created schedule.')
                moved = await call('reschedule_workout', base | {
                    'schedule_id': old_sid, 'day': args.move_to},
                    (pending_schedules, 'workoutScheduleId'))
                pending_schedules.discard(old_sid)
                sid = moved['data']['workoutScheduleId']
                await call('unschedule_workout', base | {'schedule_id': sid})
                pending_schedules.discard(sid)
                await call('delete_workout', base | {'workout_id': wid})
                pending_workouts.discard(wid)
                report['plan_roundtrip_verified'] = True
            finally:
                # Cleanup IDs come only from this run's successful create responses.
                for sid in sorted(pending_schedules):
                    try:
                        calendar = (await call('get_scheduled_workouts', {
                            'year': date.fromisoformat(args.day).year,
                            'month': date.fromisoformat(args.day).month}))['data']['calendarItems']
                        other = date.fromisoformat(args.move_to)
                        if (other.year, other.month) != (date.fromisoformat(args.day).year, date.fromisoformat(args.day).month):
                            calendar += (await call('get_scheduled_workouts', {'year': other.year, 'month': other.month}))['data']['calendarItems']
                        if any(item.get('id') == sid for item in calendar):
                            await call('unschedule_workout', base | {'schedule_id': sid})
                    except Exception:
                        cleanup_errors.append({'schedule_id': sid})
                for wid in sorted(pending_workouts):
                    try:
                        probe = await client.call_tool('garmin_get_workout_by_id', {'workout_id': wid})
                        if probe.isError:
                            if (probe.structuredContent or {}).get('error') != 'GarminConnectNotFoundError':
                                raise VerificationFailure('Template state unresolved')
                        else:
                            await call('delete_workout', base | {'workout_id': wid})
                    except Exception:
                        cleanup_errors.append({'workout_id': wid})
                if cleanup_errors:
                    print(json.dumps({'cleanup_unresolved': cleanup_errors}), file=sys.stderr)
            report['original_templates_unchanged'] = await templates() == before
            report['activity_list_unchanged'] = await rows('get_activities') == activities
            report['cleanup_verified'] = not cleanup_errors
            if not all(value for key, value in report.items() if key != 'region'):
                raise VerificationFailure('Post-test state differs; inspect before further changes.')
            print(json.dumps(report))


def main():
    parser = argparse.ArgumentParser(description='Create, edit, schedule and delete a temporary test workout through MCP. Use only an authorized test account.')
    parser.add_argument('--plugin', type=Path, required=True)
    parser.add_argument('--region', choices=['com', 'cn'], required=True)
    parser.add_argument('--expected-account', required=True)
    parser.add_argument('--source-workout', type=int, required=True)
    parser.add_argument('--day', type=date.fromisoformat, required=True)
    parser.add_argument('--move-to', type=date.fromisoformat, required=True)
    args = parser.parse_args()
    if args.day == args.move_to:
        parser.error('Use different dates to verify rescheduling.')
    args.day, args.move_to = args.day.isoformat(), args.move_to.isoformat()
    try:
        asyncio.run(verify(args))
    except Exception as exc:
        # Avoid upstream account data and authentication details in diagnostic output.
        print('Live verification failed: '+(str(exc) if isinstance(exc, VerificationFailure) else type(exc).__name__), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
