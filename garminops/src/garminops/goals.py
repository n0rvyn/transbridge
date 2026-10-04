"""Independent training-goal definitions; never forward recorded progress."""
from copy import deepcopy
from datetime import date
from math import isfinite

from .drafts import schedule_payload
from .policy import ContractUnverified


METRICS = {
    'count_accumulation': 'numberOfActivities',
    'distance_accumulation': 'distanceInMeters',
    'duration_accumulation': 'durationInSeconds',
    'energy_accumulation': 'caloriesInKiloCalories',
}
GOAL_FIELDS = {'name', 'activityType', 'period', 'type', 'startDate', 'privacy', *METRICS.values()}


def goal_payload(value):
    if not isinstance(value, dict) or set(value) != GOAL_FIELDS:
        raise ValueError('Supply only the complete goal definition; progress and history fields are forbidden.')
    for field in ('name', 'activityType', 'privacy'):
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError('Goal name, activity type and explicit privacy must be nonempty strings.')
    if value['type'] not in METRICS or value['period'] not in ('seven_days', 'thirty_days', 'one_month', 'annual'):
        raise ValueError('Unknown goal type or period.')
    schedule_payload(value['startDate'])
    if date.fromisoformat(value['startDate']) <= date.today():
        raise ContractUnverified('Changes to started goals can affect historical progress; only future goal contracts are verified.')
    metric = METRICS[value['type']]
    for field in METRICS.values():
        target = value[field]
        if field != metric:
            if target is not None:
                raise ValueError('Unused target fields must be null.')
        elif (type(target) not in (int, float) or not isfinite(target) or target <= 0
              or (field == 'numberOfActivities' and int(target) != target)):
            raise ValueError('Goal target must be positive and finite; activity counts must be whole numbers.')
    return deepcopy(value)


def editable_goal(row):
    if row.get('active') is not False or row.get('completed') is not False:
        raise ContractUnverified('Started, completed or unclassified goal cannot be changed.')
    progress = row.get('progress')
    fields = {'percent', 'days', *METRICS.values()}
    if not isinstance(progress, dict) or not fields.issubset(progress):
        raise ContractUnverified('Goal progress is incomplete or unclassified.')
    for field in fields:
        value = progress[field]
        if value is None and field in METRICS.values():
            continue
        if type(value) not in (int, float) or value != 0:
            raise ContractUnverified('Goal has recorded or unclassified progress; no write sent.')
    return goal_payload({key: row[key] for key in GOAL_FIELDS})
