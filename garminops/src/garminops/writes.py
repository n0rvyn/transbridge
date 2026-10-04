"""Named plan/settings operations; no public arbitrary request entry point."""
from copy import deepcopy
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from garminconnect import GarminConnectNotFoundError

from .drafts import workout_copy, workout_update, schedule_payload, zone_update, power_zone_update, POWER_FIELDS, calendar_note_payload
from .policy import PolicyDenied, ContractUnverified, write_intent
from .backend import error_metadata, gear_uuid
from .errors import diagnostics
from .goals import GOAL_FIELDS, goal_payload, editable_goal
from .events import EVENT_FIELDS, event_payload, editable_event
from .gear import FIELDS as GEAR_FIELDS, gear_payload, editable_gear


class AccountInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    expected_account: str = Field(description='Garmin account ID from garmin_account_identity, not the browser profile name.')


class CreateWorkout(AccountInput):
    workout: dict[str, Any] = Field(description='Complete Garmin workout definition, including sportType and workoutSegments.')
    name: str
    description: str


class CopyWorkout(AccountInput):
    workout_id: int = Field(gt=0)
    name: str
    description: str


class UpdateWorkout(AccountInput):
    workout_id: int = Field(gt=0)
    changes: dict[str, Any]


class DeleteWorkout(AccountInput):
    workout_id: int = Field(gt=0)


class ScheduleWorkout(DeleteWorkout):
    day: str = Field(description='Calendar date YYYY-MM-DD; does not send to a device.')


class UnscheduleWorkout(AccountInput):
    schedule_id: int = Field(gt=0)


class RescheduleWorkout(UnscheduleWorkout):
    day: str


class UpdateHeartRateZones(AccountInput):
    sport: str
    changes: dict[str, Any] = Field(description='Explicit configuration fields only. Clearing a field with null is unresolved and returns an error without writing.')


class UpdatePowerZones(AccountInput):
    sport: str
    changes: dict[str, Any] = Field(description='Explicit FTP and/or zone1Floor through zone7Floor in watts. Preserves other fields; does not recalculate logged activities.')


class UpdateMeasurementSystem(AccountInput):
    measurement_system: str = Field(pattern=r'^[a-z][a-z0-9_]*$',
        description='Explicit Garmin unit-system key, such as metric or statute_us. Garmin validates supported keys; no default is chosen.')


class CreateGoal(AccountInput):
    goal: dict[str, Any] = Field(description='Complete independent future-goal definition: name, activityType, period, type, startDate, explicit privacy, and four target fields. Only the target matching type is non-null. Never include progress.')


class DeleteGoal(AccountInput):
    goal_id: int = Field(gt=0)


class UpdateGoal(DeleteGoal):
    changes: dict[str, Any]


class CreateCalendarNote(AccountInput):
    name: str
    content: str
    day: str


class DeleteCalendarNote(AccountInput):
    note_id: int = Field(gt=0)


class UpdateCalendarNote(DeleteCalendarNote):
    changes: dict[str, Any] = Field(description='Explicit noteName, content or date changes only.')


class CreateCalendarEvent(AccountInput):
    event: dict[str, Any] = Field(description='Complete future private event definition, including explicit privacy, target, time or null, and location or null. No results, plan associations, course or image attachments.')


class DeleteCalendarEvent(AccountInput):
    event_id: int = Field(gt=0)


class UpdateCalendarEvent(DeleteCalendarEvent):
    changes: dict[str, Any] = Field(description='Explicit event definition changes only; recorded results and associations are never accepted.')


class CreateGear(AccountInput):
    gear: dict[str, Any] = Field(description='Complete unused gear definition with explicit first-use date, explicit usage type/thresholds and associatedActivityTypes null. Never assign existing activities.')


class DeleteGear(AccountInput):
    uuid: str


class SetGearDefaults(DeleteGear):
    activities: list[dict[str, Any]] = Field(description='Complete desired defaults: each item has activityTypeKey, defaultGear true and preferredGear false. Explicit [] clears defaults. Never applies to past activities.')


class SetGearStatus(DeleteGear):
    status: Literal['ACTIVE', 'RETIRED']


class UpdateGear(DeleteGear):
    changes: dict[str, Any]


OPERATIONS = {
    'set_gear_defaults': (SetGearDefaults, 'Set or clear future activity defaults on unused active independent gear; verify detail and default mappings, preserve other gear. Conflicting defaults and preferred gear remain unverified. Never assigns existing activities.'),
    'set_gear_status': (SetGearStatus, 'Retire or reactivate unused independent gear; verify status, retirement date, definition and inventory. Never changes logged usage.'),
    'create_gear': (CreateGear, 'Create unused independent gear without default activity assignments; verify definition and inventory.'),
    'update_gear': (UpdateGear, 'Update unused independent gear after checking recorded usage and associations; preserve unrelated fields.'),
    'delete_gear': (DeleteGear, 'Delete unused independent gear only; reject linked activities and verify absence.'),
    'create_calendar_event': (CreateCalendarEvent, 'Create an independent future private calendar event; verify its details and calendar entry.'),
    'update_calendar_event': (UpdateCalendarEvent, 'Update an independent future private event with no activity or training-plan association; verify details and calendar.'),
    'delete_calendar_event': (DeleteCalendarEvent, 'Delete an independent future private event with no recorded results or plan association; verify absence.'),
    'create_calendar_note': (CreateCalendarNote, 'Create an independent future planning note and verify its calendar entry. Never changes activity notes.'),
    'update_calendar_note': (UpdateCalendarNote, 'Update or move an independent future planning note; verify its contents and calendar entry.'),
    'delete_calendar_note': (DeleteCalendarNote, 'Delete an independent future planning note and verify absence by ID and calendar.'),
    'create_goal': (CreateGoal, 'Create an independent future training goal with explicit privacy; verify saved definition. Does not write daily goal history.'),
    'update_goal': (UpdateGoal, 'Update an unstarted future goal with no recorded progress. Preserve other definition fields and verify read-back.'),
    'delete_goal': (DeleteGoal, 'Delete an unstarted future goal with no recorded progress; verify complete active/future/past goal lists.'),
    'update_measurement_system': (UpdateMeasurementSystem, 'Update display measurement units only and verify the full profile. Never sends weight, historical measurements or other settings.'),
    'create_workout': (CreateWorkout, 'Create a workout template. Read back before reporting success.'),
    'copy_workout': (CopyWorkout, 'Copy a workout template into a new independent template.'),
    'update_workout': (UpdateWorkout, 'Update selected fields of a workout template while retaining unrelated fields.'),
    'delete_workout': (DeleteWorkout, 'Delete a workout template and verify its absence. Never delete recorded activities.'),
    'schedule_workout': (ScheduleWorkout, 'Schedule a workout on the Garmin calendar; no device delivery.'),
    'unschedule_workout': (UnscheduleWorkout, 'Remove an uncompleted scheduled workout from the calendar.'),
    'reschedule_workout': (RescheduleWorkout, 'Move an uncompleted schedule by creating the replacement then removing the original. Reports partial outcomes; never blindly retry.'),
    'update_power_zones': (UpdatePowerZones, 'Update current FTP or power-zone floors and verify the requested profile. Garmin also changes cross-country-ski power settings when cycling FTP changes; returns those linked field changes explicitly. Other unexpected profile changes fail verification. Zero is literal zero, not null.'),
    'update_heart_rate_zones': (UpdateHeartRateZones, 'Update current heart-rate configuration for an existing sport. Does not edit historical measurements. Null clearing remains unresolved.'),
}


class WriteFailure(Exception):
    def __init__(self, outcome: dict):
        self.outcome = outcome
        super().__init__(outcome['error'])


def identity(backend) -> dict:
    # The SDK loads the Garmin social identity when restoring the session.
    backend.read('get_full_name', {})
    return {'account_id': backend._api.display_name, 'name': backend._api.full_name,
            'region': f'garmin.{backend.region}'}


def execute(backend, name: str, arguments: dict) -> dict:
    if name not in OPERATIONS:
        raise PolicyDenied('Unknown write operation.')
    args = OPERATIONS[name][0].model_validate(arguments)
    with backend._lock:
        account = identity(backend)
        if not account['account_id'] or args.expected_account != account['account_id']:
            raise PolicyDenied('Garmin account does not match the requested account.')
        op = PlanWriter(backend)
        try:
            data = getattr(op, name)(args)
            return {'verified': True, 'data': data, 'account': account,
                    'completed_requests': op.completed}
        except Exception as exc:
            if not op.started:
                raise
            metadata = error_metadata(exc)
            raise WriteFailure({**metadata, **diagnostics(exc, stage=op.stage, operation=name, status=metadata.get('http_status')), 'retriable': False, 'retry_requires_state_check': True, 'verified': False,
                'operation': name, 'completed_requests': op.completed,
                'last_request': op.last_request,
                'outcome': 'A request was sent. The last request or its verification failed; inspect current state before retrying.',
                'account': account}) from exc


def contains_requested_content(actual, expected):
    """Allow server-added fields, but preserve every requested value and step."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and contains_requested_content(actual[key], value)
            for key, value in expected.items() if key != 'stepId')
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            contains_requested_content(a, e) for a, e in zip(actual, expected))
    return actual == expected


class PlanWriter:
    def __init__(self, backend):
        self.backend = backend
        self.api = backend._api
        self.started = False
        self.completed = []
        self.last_request = None
        self.stage = "preflight"

    def request(self, method, path, payload=None):
        self.stage = 'request'
        self.last_request = {'method': method, 'path': path}
        with write_intent(method, path, payload):
            self.started = True
            kwargs = {} if payload is None else {'json': payload}
            response = self.api.client.request(method, 'connectapi', path, **kwargs)
        data = response.json() if response.content else None
        self.stage = 'verification'
        self.completed.append(self.last_request | {'response': data})
        return data

    def template(self, workout_id):
        value = self.api.get_workout_by_id(workout_id)
        if value.get('workoutId') != workout_id:
            raise ValueError('Returned template ID differs.')
        return value

    def gear_inventory(self):
        rows = []
        for status in ('ACTIVE', 'RETIRED'):
            start = 0
            while True:
                page = self.api.get_gear_items(start=start, limit=20, status=status)
                if not page:
                    break
                ids = [gear_uuid(r['uuid']) for r in rows + page]
                if len(ids) != len(set(ids)):
                    raise ValueError('Gear pagination returned duplicate identities; inventory is ambiguous.')
                rows.extend(page)
                start += len(page)
        return {r['uuid']: r for r in rows}

    def gear(self, uuid, *, allow_retired=False, allow_defaults=False):
        uuid = gear_uuid(uuid)
        row = self.api.get_gear_item(uuid)
        if row.get('uuid') != uuid:
            raise ValueError('Gear UUID differs.')
        editable_gear(row, allow_retired=allow_retired, allow_defaults=allow_defaults)
        return row

    def create_gear(self, args):
        payload = gear_payload(args.gear)
        if payload['uuid'] is not None:
            raise ValueError('New gear must not specify an existing UUID.')
        before = self.gear_inventory()
        saved = self.request('POST', '/gear-service/gear/v2', payload)
        if not isinstance(saved, dict):
            raise ValueError('Created gear returned no object; inspect before retrying.')
        uuid = gear_uuid(saved.get('uuid'))
        confirmed = self.gear(uuid)
        if editable_gear(confirmed) != payload | {'uuid': uuid}:
            raise ValueError('Created gear differs from requested definition.')
        after = self.gear_inventory()
        if uuid not in after or uuid in before or {k:v for k,v in after.items() if k!=uuid} != before:
            raise ValueError('Gear inventory did not preserve existing items.')
        return confirmed

    def update_gear(self, args):
        if not args.changes or set(args.changes) - (GEAR_FIELDS - {'uuid'}):
            raise ValueError('Only gear definition fields can change.')
        original = self.gear(args.uuid)
        before = self.gear_inventory()
        payload = gear_payload(editable_gear(original) | args.changes)
        self.request('PUT', f'/gear-service/gear/v2/{args.uuid}', payload)
        confirmed = self.gear(args.uuid)
        if editable_gear(confirmed) != payload:
            raise ValueError('Updated gear differs from requested definition.')
        for k in set(original) - set(args.changes):
            if original[k] != confirmed.get(k):
                raise ValueError('Gear update changed unrelated fields.')
        after = self.gear_inventory()
        if args.uuid not in after or {k:v for k,v in after.items() if k!=args.uuid} != {k:v for k,v in before.items() if k!=args.uuid}:
            raise ValueError('Gear update changed other inventory items.')
        return confirmed

    def gear_default_map(self, gear_type):
        rows = self.api.get_gear_default_choices(gear_type)
        result = {}
        for row in rows:
            key, ids = row['activityTypeKey'], row['defaultGearUUIDs']
            if key in result or len(ids) != len(set(ids)):
                raise ContractUnverified('Default gear mappings contain duplicate identities.')
            result[key] = set(ids)
        return result

    def set_gear_defaults(self, args):
        from .gear import default_activities
        activities = default_activities(args.activities)
        original = self.gear(args.uuid, allow_defaults=True)
        before = self.gear_inventory()
        defaults = self.gear_default_map(original['gearType'])
        selected = {r['activityTypeKey'] for r in activities}
        if any(defaults.get(key, set()) - {args.uuid} for key in selected):
            raise ContractUnverified('Another gear item already owns a requested default; replacement effects remain unverified.')
        payload = editable_gear(original, allow_defaults=True) | {'associatedActivityTypes': activities or None}
        payload = gear_payload(payload, allow_defaults=True)
        if original.get('associatedActivityTypes') != (activities or None):
            self.request('PUT', f'/gear-service/gear/v2/{args.uuid}', payload)
        confirmed = self.gear(args.uuid, allow_defaults=True)
        if editable_gear(confirmed, allow_defaults=True) != payload:
            raise ValueError('Default gear definition was not saved as requested.')
        for key in (set(original) | set(confirmed)) - {'associatedActivityTypes'}:
            if original.get(key) != confirmed.get(key):
                raise ValueError('Default update changed unrelated gear fields.')
        expected = {key: ids - {args.uuid} for key, ids in defaults.items()}
        for key in selected:
            expected.setdefault(key, set()).add(args.uuid)
        expected = {key: ids for key, ids in expected.items() if ids}
        actual = self.gear_default_map(original['gearType'])
        if actual != expected:
            raise ValueError('Default gear mapping does not match the requested change.')
        after = self.gear_inventory()
        if args.uuid not in after or {k:v for k,v in before.items() if k!=args.uuid} != {k:v for k,v in after.items() if k!=args.uuid}:
            raise ValueError('Default update changed other gear inventory items.')
        return confirmed

    def set_gear_status(self, args):
        original = self.gear(args.uuid, allow_retired=True)
        before = self.gear_inventory()
        if original['status'] != args.status:
            self.request('PUT', f'/gear-service/gear/v2/{args.uuid}/status/{args.status}')
        confirmed = self.gear(args.uuid, allow_retired=True)
        if confirmed['status'] != args.status:
            raise ValueError('Gear status was not saved.')
        if args.status == 'RETIRED' and original['status'] != 'RETIRED' and confirmed.get('retireDate') != date.today().isoformat():
            raise ValueError('Unexpected gear retirement date.')
        for k in (set(original) | set(confirmed)) - {'status', 'retireDate'}:
            if original.get(k) != confirmed.get(k):
                raise ValueError('Status update changed unrelated gear fields.')
        after = self.gear_inventory()
        if (args.uuid not in after or after[args.uuid].get('status') != args.status
                or {k:v for k,v in after.items() if k!=args.uuid} != {k:v for k,v in before.items() if k!=args.uuid}):
            raise ValueError('Gear inventory failed status verification.')
        return confirmed

    def delete_gear(self, args):
        self.gear(args.uuid)
        before = self.gear_inventory()
        self.request('DELETE', f'/gear-service/gear/v2/{args.uuid}')
        try:
            self.api.get_gear_item(args.uuid)
        except GarminConnectNotFoundError:
            after = self.gear_inventory()
            if args.uuid in after or after != {k:v for k,v in before.items() if k!=args.uuid}:
                raise ValueError('Gear deletion changed other items or failed to remove the target.')
            return {'uuid': args.uuid, 'absent': True}
        raise ValueError('Deleted gear remains retrievable.')

    def event(self, event_id):
        row = self.api.get_calendar_event(event_id)
        if row.get('id') != event_id:
            raise ValueError('Event ID differs.')
        editable_event(row)
        return row

    def verify_event_calendar(self, row, present):
        matches = [item for item in self.calendar(row['date'])
                   if item.get('id') == row['id'] and item.get('itemType') == 'event']
        if present and (len(matches) != 1 or matches[0].get('date') != row['date']
                or matches[0].get('title') != row['eventName']):
            raise ValueError('Event calendar entry is absent, ambiguous or differs.')
        if not present and matches:
            raise ValueError('Event remains on its original calendar date.')

    def create_calendar_event(self, args):
        payload = event_payload(args.event)
        if 'id' in payload:
            raise ValueError('Creation must not specify an existing event ID.')
        saved = self.request('POST', '/calendar-service/event', payload)
        if not isinstance(saved, dict) or type(saved.get('id')) is not int or saved['id'] <= 0:
            raise ValueError('Created event returned no valid ID; inspect before retrying.')
        confirmed = self.event(saved['id'])
        if editable_event(confirmed) != payload | {'id': saved['id']}:
            raise ValueError('Event creation did not preserve the requested definition.')
        self.verify_event_calendar(confirmed, True)
        return confirmed

    def update_calendar_event(self, args):
        if not args.changes or set(args.changes) - EVENT_FIELDS:
            raise ValueError('Only explicit event definition fields can change.')
        original = self.event(args.event_id)
        payload = event_payload(editable_event(original) | args.changes)
        self.request('PUT', f'/calendar-service/event/{args.event_id}', payload)
        confirmed = self.event(args.event_id)
        if editable_event(confirmed) != payload:
            raise ValueError('Updated event failed definition verification.')
        untouched = set(original) - set(args.changes)
        if any(original[k] != confirmed[k] for k in untouched):
            raise ValueError('Event update changed unrelated fields.')
        self.verify_event_calendar(confirmed, True)
        if original['date'] != confirmed['date']:
            self.verify_event_calendar(original, False)
        return confirmed

    def delete_calendar_event(self, args):
        original = self.event(args.event_id)
        self.request('DELETE', f'/calendar-service/event/{args.event_id}')
        try:
            self.api.get_calendar_event(args.event_id)
        except GarminConnectNotFoundError:
            self.verify_event_calendar(original, False)
            return {'event_id': args.event_id, 'absent': True}
        raise ValueError('Deleted event is still retrievable.')

    def note(self, note_id):
        row = self.api.get_calendar_note(note_id)
        # Unknown fields could represent a different kind of note. Do not discard
        # them while issuing a replacement write under an unverified contract.
        if row.get('id') != note_id:
            raise ValueError('Calendar note ID differs.')
        return calendar_note_payload(row)

    def verify_note_calendar(self, row, present):
        matches = [item for item in self.calendar(row['date'])
                   if item.get('id') == row['id'] and item.get('itemType') == 'note']
        if present and (len(matches) != 1 or matches[0].get('date') != row['date']):
            raise ValueError('Planning note is absent or ambiguous in the calendar.')
        if not present and matches:
            raise ValueError('Planning note remains in the calendar.')

    def create_calendar_note(self, args):
        payload = calendar_note_payload(dict(id=None, noteName=args.name, content=args.content, date=args.day))
        saved = self.request('POST', '/calendar-service/note', payload)
        if not isinstance(saved, dict) or type(saved.get('id')) is not int or saved['id'] <= 0:
            raise ValueError('Created note returned no valid ID; inspect before retrying.')
        confirmed = self.note(saved['id'])
        if confirmed != payload | {'id': saved['id']}:
            raise ValueError('Created note failed read-back verification.')
        self.verify_note_calendar(confirmed, True)
        return confirmed

    def update_calendar_note(self, args):
        if not args.changes or set(args.changes) - {'noteName', 'content', 'date'}:
            raise ValueError('Only noteName, content and date can change.')
        original = self.note(args.note_id)
        payload = calendar_note_payload(original | args.changes)
        self.request('PUT', f'/calendar-service/note/{args.note_id}', payload)
        confirmed = self.note(args.note_id)
        if confirmed != payload:
            raise ValueError('Updated note failed read-back verification.')
        self.verify_note_calendar(confirmed, True)
        if original['date'] != confirmed['date']:
            old = [item for item in self.calendar(original['date'])
                   if item.get('id') == args.note_id and item.get('itemType') == 'note'
                   and item.get('date') == original['date']]
            if old:
                raise ValueError('Moved note remains on its original date.')
        return confirmed

    def delete_calendar_note(self, args):
        original = self.note(args.note_id)
        self.request('DELETE', f'/calendar-service/note/{args.note_id}')
        try:
            self.api.get_calendar_note(args.note_id)
        except GarminConnectNotFoundError:
            self.verify_note_calendar(original, False)
            return {'note_id': args.note_id, 'absent': True}
        raise ValueError('Deleted note is still retrievable.')

    def goals(self):
        rows = [row for status in ('active', 'future', 'past')
                for row in self.api.get_goals(status=status)]
        if any(not isinstance(row, dict) or type(row.get('id')) is not int for row in rows):
            raise ValueError('Goal list contains malformed identities.')
        if len({row['id'] for row in rows}) != len(rows):
            raise ValueError('Goal list contains duplicate identities; verification is ambiguous.')
        return {row['id']: row for row in rows}

    def create_goal(self, args):
        payload = goal_payload(args.goal)
        before = self.goals()
        created = self.request('POST', '/goal-service/goal/goal', payload)
        if not isinstance(created, dict) or type(created.get('id')) is not int or created['id'] <= 0:
            raise ValueError('Created goal returned no valid ID; inspect before retrying.')
        after = self.goals()
        confirmed = after.get(created['id'])
        if (created['id'] in before or confirmed is None or editable_goal(confirmed) != payload
                or {k:v for k,v in after.items() if k != created['id']} != before):
            raise ValueError('Goal creation or unrelated goals failed read-back verification.')
        return confirmed

    def update_goal(self, args):
        if not args.changes or set(args.changes) - GOAL_FIELDS:
            raise ValueError('Only goal definition fields can change; recorded progress is immutable.')
        before = self.goals()
        original = editable_goal(before[args.goal_id])
        payload = goal_payload(original | args.changes)
        self.request('PUT', f'/goal-service/goal/goal/{args.goal_id}', payload)
        after = self.goals()
        confirmed = after.get(args.goal_id)
        if (confirmed is None or editable_goal(confirmed) != payload
                or {k:v for k,v in after.items() if k != args.goal_id} !=
                   {k:v for k,v in before.items() if k != args.goal_id}):
            raise ValueError('Goal update or unrelated goals failed read-back verification.')
        return confirmed

    def delete_goal(self, args):
        before = self.goals()
        editable_goal(before[args.goal_id])
        self.request('DELETE', f'/goal-service/goal/goal/{args.goal_id}')
        after = self.goals()
        if after != {k:v for k,v in before.items() if k != args.goal_id}:
            raise ValueError('Deleted goal remains present or other goals changed.')
        return {'goal_id': args.goal_id, 'absent': True}

    def calendar(self, day):
        d = date.fromisoformat(day)
        return self.api.get_scheduled_workouts(d.year, d.month)['calendarItems']

    def schedule(self, schedule_id):
        value = self.api.get_scheduled_workout_by_id(schedule_id)
        if value.get('workoutScheduleId') != schedule_id:
            raise ValueError('Returned schedule ID differs.')
        if 'associatedActivityId' not in value or value['associatedActivityId'] is not None:
            raise PolicyDenied('A completed or unclassified schedule cannot be changed.')
        if value.get('associatedActivityDateTime') is not None:
            raise PolicyDenied('Schedule is associated with logged data.')
        if value.get('protected') is not False:
            raise ContractUnverified('Protected schedule contract is unverified.')
        return value

    def create_workout(self, args):
        payload = workout_copy(args.workout, args.name, args.description)
        created = self.request('POST', '/workout-service/workout', payload)
        confirmed = self.template(created['workoutId'])
        if not contains_requested_content(confirmed, {key: payload[key] for key in
                ('workoutName', 'description', 'sportType', 'workoutSegments')}):
            raise ValueError('Created template failed read-back verification.')
        return confirmed

    def copy_workout(self, args):
        return self.create_workout(CreateWorkout(expected_account=args.expected_account,
            workout=self.template(args.workout_id), name=args.name, description=args.description))

    def update_workout(self, args):
        payload = workout_update(self.template(args.workout_id), args.changes)
        self.request('PUT', f'/workout-service/workout/{args.workout_id}', payload)
        confirmed = self.template(args.workout_id)
        if not contains_requested_content(confirmed, args.changes):
            raise ValueError('Updated template failed read-back verification.')
        return confirmed

    def delete_workout(self, args):
        self.template(args.workout_id)
        self.request('DELETE', f'/workout-service/workout/{args.workout_id}')
        try:
            self.api.get_workout_by_id(args.workout_id)
        except GarminConnectNotFoundError:
            return {'workout_id': args.workout_id, 'absent': True}
        raise ValueError('Deleted template is still retrievable by ID.')

    def schedule_workout(self, args):
        payload = schedule_payload(args.day)
        self.template(args.workout_id)
        created = self.request('POST', f'/workout-service/schedule/{args.workout_id}', payload)
        confirmed = self.schedule(created['workoutScheduleId'])
        if confirmed.get('calendarDate') != args.day or confirmed.get('workout', {}).get('workoutId') != args.workout_id:
            raise ValueError('Schedule failed read-back verification.')
        if not any(x.get('id') == created['workoutScheduleId'] and x.get('workoutId') == args.workout_id
                   and x.get('date') == args.day for x in self.calendar(args.day)):
            raise ValueError('Scheduled workout is absent from calendar.')
        return confirmed

    def unschedule_workout(self, args):
        original = self.schedule(args.schedule_id)
        self.request('DELETE', f'/workout-service/schedule/{args.schedule_id}')
        if any(x.get('id') == args.schedule_id and x.get('workoutId') == original['workout']['workoutId']
               for x in self.calendar(original['calendarDate'])):
            raise ValueError('Removed schedule remains in calendar.')
        return {'schedule_id': args.schedule_id, 'absent': True}

    def reschedule_workout(self, args):
        schedule_payload(args.day)
        original = self.schedule(args.schedule_id)
        if original['calendarDate'] == args.day:
            return original
        replacement = self.schedule_workout(ScheduleWorkout(expected_account=args.expected_account,
            workout_id=original['workout']['workoutId'], day=args.day))
        self.unschedule_workout(UnscheduleWorkout(expected_account=args.expected_account, schedule_id=args.schedule_id))
        return replacement

    def update_measurement_system(self, args):
        before = self.api.get_user_profile()
        if not isinstance(before, dict) or not isinstance(before.get('userData'), dict):
            raise ValueError('Expected the current user settings object.')
        expected = deepcopy(before)
        expected['userData']['measurementSystem'] = args.measurement_system
        self.request('PUT', '/userprofile-service/userprofile/user-settings',
                     {'userData': {'measurementSystem': args.measurement_system}})
        confirmed = self.api.get_user_profile()
        if confirmed != expected:
            raise ValueError('Unit setting read-back or unrelated profile fields differ.')
        return confirmed

    def update_heart_rate_zones(self, args):
        if any(v is None for v in args.changes.values()):
            raise ContractUnverified('Garmin ignores null; clearing settings is unresolved. No write sent.')
        before = self.api.get_heart_rate_zones()
        payload = zone_update(before, args.sport, args.changes)
        self.request('PUT', '/biometric-service/heartRateZones', payload)
        confirmed = self.api.get_heart_rate_zones()
        expected = [dict(p, **args.changes) if p['sport'] == args.sport else p for p in before]
        # changeState is transport bookkeeping, not a saved user setting.
        normalize = lambda rows: {p['sport']: {k:v for k,v in p.items() if k != 'changeState'} for p in rows}
        if normalize(confirmed) != normalize(expected):
            raise ValueError('Settings read-back differs from the intended change.')
        return confirmed


    def update_power_zones(self, args):
        before = self.api.get_power_zones()
        payload = power_zone_update(before, args.sport, args.changes)
        self.request('PUT', '/biometric-service/powerZones', payload)
        confirmed = self.api.get_power_zones()
        expected = [dict(profile, **args.changes) if profile['sport'] == args.sport else profile
                    for profile in before]
        by_sport = {profile['sport']: profile for profile in confirmed}
        if len(by_sport) != len(confirmed) or len(confirmed) != len(expected) or set(by_sport) != {profile['sport'] for profile in expected}:
            raise ValueError('Power profile identities changed.')
        linked = []
        for profile in expected:
            actual = by_sport[profile['sport']]
            if actual == profile:
                continue
            fields = {key for key in set(actual) | set(profile)
                      if key not in actual or key not in profile or actual[key] != profile[key]}
            if (args.sport == 'CYCLING' and 'functionalThresholdPower' in args.changes
                    and args.changes['functionalThresholdPower'] != next(p for p in before if p['sport'] == 'CYCLING')['functionalThresholdPower']
                    and profile['sport'] == 'CROSS_COUNTRY_SKIING' and fields <= POWER_FIELDS):
                linked.append({'sport': profile['sport'], 'changes': {
                    key: {'before': profile.get(key), 'after': actual.get(key)} for key in sorted(fields)}})
            else:
                raise ValueError('Power settings read-back differs from the intended change.')
        return {'profiles': confirmed, 'linked_profile_changes': linked,
                'verification_scope': 'Requested profile verified; observed skiing linkage reported separately.'}
