"""Calendar event definitions, separate from recorded results and plan enrollments."""
from copy import deepcopy
from datetime import date
from math import isfinite
import re
from zoneinfo import ZoneInfo

from .drafts import resource_id
from .policy import ContractUnverified

EVENT_FIELDS = frozenset(('eventName', 'date', 'eventType', 'eventTimeLocal', 'race',
    'official', 'eventPrivacy', 'courseId', 'courseName', 'location',
    'completionTarget', 'locationStartPoint', 'note', 'url', 'imageUrl'))
NULL_FIELDS = frozenset(('groupId', 'registrationUrl', 'workoutId', 'eventImageUUID',
    'shareableEventUuid', 'eventRef', 'statuses', 'workoutName', 'eventImageURLs',
    'subscribersCount', 'subscribed'))
RESPONSE_FIELDS = (EVENT_FIELDS - {'official', 'imageUrl'}) | NULL_FIELDS | {
    'id', 'eventCustomization', 'provider', 'eventOrganizer'}
CUSTOMIZATION_FIELDS = {'customGoal', 'isPrimaryEvent', 'associatedWithActivityId',
    'isTrainingEvent', 'isGoalMet', 'trainingPlanId', 'trainingPlanType', 'enrollmentTime'}


def event_payload(value):
    if not isinstance(value, dict) or set(value) not in (EVENT_FIELDS, EVENT_FIELDS | {'id'}):
        raise ContractUnverified('Only the explicit event definition fields are supported; never send results or associations.')
    p = deepcopy(value)
    if 'id' in p:
        resource_id(p['id'])
    if not isinstance(p['date'], str) or date.fromisoformat(p['date']).isoformat() != p['date'] or date.fromisoformat(p['date']) <= date.today():
        raise ContractUnverified('Past or current-day event changes require a separately verified history-preserving contract.')
    if not isinstance(p['eventName'], str) or not p['eventName'].strip() or len(p['eventName']) > 254:
        raise ValueError('Garmin requires an event name of 1 to 254 characters.')
    if not isinstance(p['eventType'], str) or not re.fullmatch('[a-z][a-z0-9_]*', p['eventType']):
        raise ValueError('Use a Garmin event-type key.')
    if type(p['race']) is not bool or p['official'] is not False or p['eventPrivacy'] != {'label': 'PRIVATE'}:
        raise ContractUnverified('Public, shared and official event contracts are not verified.')
    if p['courseId'] is not None or p['courseName'] != '' or p['imageUrl'] != '':
        raise ContractUnverified('Course and image attachment contracts are not verified.')
    for key in ('location', 'note', 'url'):
        if not isinstance(p[key], str):
            raise ValueError(f'{key} must be text.')
    target = p['completionTarget']
    if (not isinstance(target, dict) or set(target) != {'value', 'unit', 'unitType'}
            or type(target['value']) not in (int, float) or not isfinite(target['value']) or target['value'] <= 0):
        raise ValueError('An event needs a positive finite completion target.')
    if not ((target['unitType'] == 'distance' and target['unit'] in ('meter', 'kilometer', 'mile', 'yard'))
            or (target['unitType'] == 'time' and target['unit'] == 'second')):
        raise ValueError('Completion target unit and unitType do not agree.')
    local = p['eventTimeLocal']
    if local is not None:
        if (not isinstance(local, dict) or set(local) != {'startTimeHhMm', 'timeZoneId'}
                or not isinstance(local['startTimeHhMm'], str)
                or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', local['startTimeHhMm'])
                or not isinstance(local['timeZoneId'], str)):
            raise ValueError('Start time requires HH:MM and an explicit time-zone ID.')
        ZoneInfo(local['timeZoneId'])
    point = p['locationStartPoint']
    if point is not None:
        if (not isinstance(point, dict) or set(point) != {'lat', 'lon'}
                or any(type(point[k]) not in (int, float) or not isfinite(point[k]) for k in point)
                or not -90 <= point['lat'] <= 90 or not -180 <= point['lon'] <= 180):
            raise ValueError('Location requires finite latitude and longitude.')
    return p


def editable_event(row):
    if not isinstance(row, dict) or set(row) != RESPONSE_FIELDS:
        raise ContractUnverified('Event response contains missing or unverified fields.')
    resource_id(row['id'])
    if any(row[k] is not None for k in NULL_FIELDS) or row['eventOrganizer'] is not True:
        raise ContractUnverified('Only independent events owned by this account have a verified write contract.')
    if row['eventPrivacy'] != {'label': 'PRIVATE', 'isShareable': False, 'isDiscoverable': False}:
        raise ContractUnverified('Shared or discoverable event writes are not verified.')
    c = row['eventCustomization']
    if (not isinstance(c, dict) or set(c) != CUSTOMIZATION_FIELDS
            or any(c[k] is not None for k in ('customGoal', 'associatedWithActivityId', 'isGoalMet', 'trainingPlanId', 'trainingPlanType'))
            or c['isPrimaryEvent'] is not False or c['isTrainingEvent'] is not False
            or not isinstance(c['enrollmentTime'], str)):
        raise ContractUnverified('Event has recorded results, plan associations, customizations or incomplete state.')
    p = {k: deepcopy(row[k]) for k in EVENT_FIELDS - {'official', 'imageUrl'}}
    p.update(official=False, imageUrl='', eventPrivacy={'label': 'PRIVATE'})
    # The real server normalizes these empty definition strings to null.
    for k in ('courseName', 'url'):
        if p[k] is None:
            p[k] = ''
    return event_payload(p | {'id': row['id']})
