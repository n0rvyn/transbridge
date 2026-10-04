"""Verified unused gear definitions; never historical activity assignments."""
from copy import deepcopy
from datetime import date
from math import isfinite
import re
from .backend import gear_uuid
from .policy import ContractUnverified

FIELDS = {'uuid','gearType','brand','model','name','firstUseDate','usageType',
          'maxUsageDistanceMeters','maxUsageDurationSeconds','maxUsageDate','associatedActivityTypes','notes'}
REQUIRED_RESPONSE = {'uuid','userProfilePk','gearType','status','brand','usageType',
    'maxUsageDurationSeconds','firstUseDate','numActivitiesLinked','durationUsedSeconds',
    'distanceUsedMeters','daysUsed','processing','createdDate','images','collections'}
OPTIONAL_RESPONSE = {'name','model','notes','maxUsageDistanceMeters','maxUsageDate','associatedActivityTypes','retireDate'}


def default_activities(value):
    if not isinstance(value, list):
        raise ValueError('Default activities must be an explicit list; [] clears them.')
    seen = set()
    for row in value:
        if not isinstance(row, dict) or set(row) != {'activityTypeKey', 'defaultGear', 'preferredGear'}:
            raise ValueError('Each default needs activityTypeKey, defaultGear and preferredGear only.')
        key = row['activityTypeKey']
        if not isinstance(key, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', key) or key in seen:
            raise ValueError('Activity type keys must be valid and unique.')
        if row['defaultGear'] is not True or row['preferredGear'] is not False:
            raise ContractUnverified('Only defaultGear true and preferredGear false have a verified contract.')
        seen.add(key)
    return deepcopy(value)


def gear_payload(value, *, allow_defaults=False):
    if not isinstance(value,dict) or set(value)!=FIELDS:
        raise ContractUnverified('Only the complete gear definition is supported; no usage records or associations.')
    p=deepcopy(value)
    if p['uuid'] is not None:gear_uuid(p['uuid'])
    if p['gearType'] not in ('SHOES','BIKE','BIKE_COMPONENT','BOOTS','SKIS','SNOWBOARD','RACKET',
            'SKATES','PADDLEBOARD','SURFBOARD','WAKEBOARD','BOAT','WHEELCHAIR','OTHER'):
        raise ContractUnverified('This gear type has no verified definition contract.')
    if not isinstance(p['brand'],str) or not p['brand'].strip():raise ValueError('Gear brand is required.')
    for k in ('model','name','notes'):
        if p[k] is not None and not isinstance(p[k],str):raise ValueError(f'{k} must be text or null.')
    if not isinstance(p['firstUseDate'],str) or date.fromisoformat(p['firstUseDate']).isoformat()!=p['firstUseDate'] or date.fromisoformat(p['firstUseDate'])>date.today():
        raise ValueError('First-use date must be an explicit ISO date no later than today.')
    if p['associatedActivityTypes'] is not None:
        if not allow_defaults:
            raise ContractUnverified('Use the named default-setting operation for default activity assignments.')
        default_activities(p['associatedActivityTypes'])
    if p['usageType'] not in ('NONE','DISTANCE','DURATION','DATE'):
        raise ValueError('Unknown gear usage-tracking type.')
    for k in ('maxUsageDistanceMeters','maxUsageDurationSeconds'):
        if type(p[k]) not in (int,float) or not isfinite(p[k]) or p[k]<0:
            raise ValueError('Usage thresholds must be finite nonnegative numbers.')
    if p['usageType']!='DISTANCE' and p['maxUsageDistanceMeters']!=0:
        raise ValueError('Inactive distance threshold must explicitly be zero.')
    if p['usageType']!='DURATION' and p['maxUsageDurationSeconds']!=0:
        raise ValueError('Inactive duration threshold must explicitly be zero.')
    if p['usageType']=='DATE':
        day=p['maxUsageDate']
        if not isinstance(day,str) or date.fromisoformat(day).isoformat()!=day:
            raise ValueError('Date threshold requires an explicit ISO date.')
    elif p['maxUsageDate'] is not None:
        raise ValueError('Inactive date threshold must explicitly be null.')
    return p


def editable_gear(row, *, allow_retired=False, allow_defaults=False):
    if not isinstance(row,dict) or not REQUIRED_RESPONSE<=set(row) or set(row)-REQUIRED_RESPONSE-OPTIONAL_RESPONSE:
        raise ContractUnverified('Gear detail has missing or unverified state.')
    gear_uuid(row['uuid'])
    allowed_statuses = ('ACTIVE', 'RETIRED') if allow_retired else ('ACTIVE',)
    if row['status'] not in allowed_statuses or row['processing'] is not False or row['images']!=[] or row['collections']!=[]:
        raise ContractUnverified('Only active, fully processed, independent gear has a verified write contract.')
    if row['status']=='RETIRED':
        day=row.get('retireDate')
        if not isinstance(day,str) or date.fromisoformat(day).isoformat()!=day:
            raise ContractUnverified('Retired gear has an unknown retirement date.')
    elif row.get('retireDate') is not None:
        raise ContractUnverified('Active gear unexpectedly retains a retirement date.')
    for k in ('numActivitiesLinked','durationUsedSeconds','distanceUsedMeters','daysUsed'):
        if type(row[k]) not in (int,float) or row[k]!=0:
            raise ContractUnverified('Gear has recorded usage or an unknown association count.')
    p={k:deepcopy(row.get(k)) for k in FIELDS}
    # The live NONE response omits the zero distance threshold and null fields.
    if 'maxUsageDistanceMeters' not in row:p['maxUsageDistanceMeters']=0
    return gear_payload(p, allow_defaults=allow_defaults)
