from copy import deepcopy
import pytest
from pydantic import ValidationError
from garminops.backend import Backend, make_api, UpstreamResponseError

GID = '00000000-0000-4000-8000-000000000001'


def test_gear_page_preserves_rows_and_explicit_pagination(monkeypatch):
    api=make_api('com');calls=[]
    rows=[dict(uuid=GID,numActivitiesLinked=2,unknown={'keep':None})]
    def read(path,**kwargs):
        calls.append((path,kwargs));return deepcopy(rows)
    monkeypatch.setattr(api,'connectapi',read)
    assert api.get_gear_items(40,20,'RETIRED')==rows
    assert calls==[('/gear-service/gear/v2/list',{'params':{'start':40,'limit':20,'gearStatuses':'RETIRED'}})]


@pytest.mark.parametrize('value',[None,{},[{}],[{'uuid':'../activity/1'}]])
def test_gear_page_rejects_malformed_response(monkeypatch,value):
    api=make_api('com');monkeypatch.setattr(api,'connectapi',lambda *a,**k:value)
    with pytest.raises(UpstreamResponseError):api.get_gear_items(0,20,'ACTIVE')


@pytest.mark.parametrize('args',[{'start':-1,'limit':20},{'start':0,'limit':0},
    {'start':True,'limit':20},{'start':0,'limit':'20'},{}])
def test_gear_pagination_validated_before_session(args):
    with pytest.raises(ValidationError):Backend('com').read('get_gear_items',args | {'status':'ACTIVE'})


def test_gear_detail_keeps_usage_and_collections(monkeypatch):
    api=make_api('com');calls=[]
    row=dict(uuid=GID,gearType='SHOES',status='ACTIVE',usageType='NONE',
        numActivitiesLinked=3,distanceUsedMeters=5.5,images=[],collections=[{'unknown':None}])
    def read(path):calls.append(path);return deepcopy(row)
    monkeypatch.setattr(api,'connectapi',read)
    assert api.get_gear_item(GID)==row
    assert calls==['/gear-service/gear/v2/'+GID]
    row['uuid']='00000000-0000-4000-8000-000000000002'
    with pytest.raises(UpstreamResponseError):api.get_gear_item(GID)


@pytest.mark.parametrize('value',[1,True,'../activity/1','not-a-uuid','00000000000040008000000000000001'])
def test_gear_uuid_rejected_before_session(value):
    with pytest.raises(ValidationError):Backend('com').read('get_gear_item',{'uuid':value})


def test_usage_type_catalog_preserved_including_new_types(monkeypatch):
    api=make_api('com');calls=[]
    def read(path):calls.append(path);return ['NONE','DISTANCE','DURATION','DATE','NEW_TYPE']
    monkeypatch.setattr(api,'connectapi',read)
    assert api.get_gear_usage_types()[-1]=='NEW_TYPE'
    assert calls==['/gear-service/gear/v2/usagetypes']


@pytest.mark.parametrize('value',[None,{},[1]])
def test_invalid_usage_catalog_rejected(monkeypatch,value):
    api=make_api('com');monkeypatch.setattr(api,'connectapi',lambda path:value)
    with pytest.raises(UpstreamResponseError):api.get_gear_usage_types()

from threading import RLock
from types import SimpleNamespace
from garminconnect import GarminConnectNotFoundError
from garminops.gear import editable_gear
from garminops.policy import ContractUnverified,PolicyDenied,check_request,write_intent
from garminops.writes import execute,WriteFailure


def definition():
    return dict(uuid=None,gearType='SHOES',brand='TEST',model=None,name='Synthetic',
        firstUseDate='2026-01-01',usageType='NONE',maxUsageDistanceMeters=0,
        maxUsageDurationSeconds=0,maxUsageDate=None,associatedActivityTypes=None,notes='Test')


def response(p):
    row=deepcopy(p);row['uuid']=GID
    for k in ('model','maxUsageDate','associatedActivityTypes'):
        if row[k] is None: row.pop(k)
    if row['maxUsageDistanceMeters']==0:row.pop('maxUsageDistanceMeters')
    row.update(userProfilePk=1,status='ACTIVE',numActivitiesLinked=0,durationUsedSeconds=0,
        distanceUsedMeters=0.0,daysUsed=0,processing=False,createdDate='2026-01-01T00:00:00.0',images=[],collections=[])
    return row


class GearAPI:
    display_name='test'
    full_name='Test'
    def __init__(self):
        self.client=self;self.rows={};self.calls=[];self.ignore_delete=False;self.hide_list=False
    def get_gear_item(self,uuid):
        if uuid not in self.rows:raise GarminConnectNotFoundError('API Error 404')
        return deepcopy(self.rows[uuid])
    def get_gear_items(self,start,limit,status):
        return [] if self.hide_list else deepcopy([r for r in self.rows.values() if r['status']==status][start:start+limit])
    def get_gear_default_choices(self,gear_type):
        rows={}
        for uuid,row in self.rows.items():
            if row['gearType']!=gear_type:continue
            for entry in row.get('associatedActivityTypes') or []:
                rows.setdefault(entry['activityTypeKey'],[]).append(uuid)
        return [{'activityTypeKey':k,'defaultGearUUIDs':v} for k,v in rows.items()]
    def request(self,method,domain,path,**kwargs):
        p=kwargs.get('json');check_request(method,path,named_read=False,payload=p)
        self.calls.append((method,path,deepcopy(p)))
        if '/status/' in path:
            from datetime import date
            status=path.rsplit('/',1)[1];self.rows[GID]['status']=status
            if status=='RETIRED':self.rows[GID]['retireDate']=date.today().isoformat()
            else:self.rows[GID].pop('retireDate',None)
        elif method in ('POST','PUT'):self.rows[GID]=response(p)
        elif not self.ignore_delete:del self.rows[GID]
        data=deepcopy(self.rows.get(GID))
        return SimpleNamespace(content=b'{}',json=lambda:data)


def backend():return SimpleNamespace(_api=GearAPI(),_lock=RLock(),region='com',read=lambda *a:'Test')
def create(b):return execute(b,'create_gear',dict(expected_account='test',gear=definition()))


def test_unused_gear_roundtrip_preserves_other_items():
    b=backend();other='00000000-0000-4000-8000-000000000002'
    b._api.rows[other]=response(definition())|{'uuid':other}
    original=deepcopy(b._api.rows[other])
    assert create(b)['verified']
    assert execute(b,'update_gear',dict(expected_account='test',uuid=GID,changes={'name':'Changed'}))['verified']
    assert execute(b,'delete_gear',dict(expected_account='test',uuid=GID))['verified']
    assert b._api.rows=={other:original}
    assert all('numActivitiesLinked' not in (p or {}) for _,_,p in b._api.calls)


@pytest.mark.parametrize('operation',['update_gear','delete_gear'])
@pytest.mark.parametrize('changes',[{'numActivitiesLinked':1},{'durationUsedSeconds':1},
    {'distanceUsedMeters':1},{'daysUsed':1},{'processing':True},{'collections':[{}]},
    {'images':[{}]},{'unknown':None},{'associatedActivityTypes':[{'activityTypeKey':'running'}]},
    {'status':'RETIRED'},{'numActivitiesLinked':None},{'numActivitiesLinked':False}])
def test_used_or_ambiguous_gear_never_written(operation,changes):
    b=backend();b._api.rows[GID]=response(definition())|changes
    args=dict(expected_account='test',uuid=GID)
    if operation=='update_gear':args['changes']={'name':'Changed'}
    with pytest.raises(ContractUnverified):execute(b,operation,args)
    assert not b._api.calls


def test_missing_association_count_is_not_zero():
    row=response(definition());del row['numActivitiesLinked']
    with pytest.raises(ContractUnverified):editable_gear(row)


def test_gear_wrong_account_never_reads_resource():
    b=backend();b._api.get_gear_item=lambda _:pytest.fail('Unauthorized read')
    with pytest.raises(PolicyDenied):execute(b,'delete_gear',dict(expected_account='other',uuid=GID))


def test_create_gear_missing_inventory_keeps_uuid_and_does_not_retry():
    b=backend();b._api.hide_list=True
    with pytest.raises(WriteFailure) as exc:create(b)
    assert exc.value.outcome['completed_requests'][0]['response']['uuid']==GID
    assert len(b._api.calls)==1


def test_gear_ignored_delete_is_failure():
    b=backend();create(b);b._api.ignore_delete=True
    with pytest.raises(WriteFailure):execute(b,'delete_gear',dict(expected_account='test',uuid=GID))


def test_gear_uuid_mismatch_and_historical_payload_rejected_at_boundary():
    with pytest.raises(PolicyDenied):
        with write_intent('PUT','/gear-service/gear/v2/'+GID,definition()):pytest.fail('Wrong UUID accepted')
    with pytest.raises(ContractUnverified):
        with write_intent('POST','/gear-service/gear/v2',definition()|{'numActivitiesLinked':0}):pytest.fail('Usage accepted')


@pytest.mark.parametrize('usage,fields', [('DISTANCE',{'maxUsageDistanceMeters':1000}),
    ('DURATION',{'maxUsageDurationSeconds':3600}),('DATE',{'maxUsageDate':'2099-01-01'}),('NONE',{})])
def test_gear_usage_threshold_updates_preserve_recorded_fields(usage,fields):
    b=backend();create(b)
    result=execute(b,'update_gear',dict(expected_account='test',uuid=GID,
        changes={'usageType':usage}|fields))
    assert result['verified'] and result['data']['usageType']==usage
    assert result['data']['distanceUsedMeters']==0


def test_unused_gear_retire_reactivate_and_idempotent_status():
    b=backend();create(b)
    retired=execute(b,'set_gear_status',dict(expected_account='test',uuid=GID,status='RETIRED'))
    assert retired['data']['status']=='RETIRED' and retired['data']['retireDate']
    count=len(b._api.calls)
    assert execute(b,'set_gear_status',dict(expected_account='test',uuid=GID,status='RETIRED'))['verified']
    assert len(b._api.calls)==count
    active=execute(b,'set_gear_status',dict(expected_account='test',uuid=GID,status='ACTIVE'))
    assert active['data']['status']=='ACTIVE' and 'retireDate' not in active['data']


def test_used_gear_cannot_retire():
    b=backend();b._api.rows[GID]=response(definition())|{'numActivitiesLinked':1}
    with pytest.raises(ContractUnverified):
        execute(b,'set_gear_status',dict(expected_account='test',uuid=GID,status='RETIRED'))
    assert not b._api.calls


def test_status_update_checks_side_effects():
    b=backend();create(b);request=b._api.request
    def changed(*a,**k):
        result=request(*a,**k);b._api.rows[GID]['brand']='Unexpected';return result
    b._api.request=changed
    with pytest.raises(WriteFailure):
        execute(b,'set_gear_status',dict(expected_account='test',uuid=GID,status='RETIRED'))


@pytest.mark.parametrize('changes',[{'maxUsageDistanceMeters':-1},{'maxUsageDistanceMeters':float('nan')},
    {'maxUsageDurationSeconds':True},{'usageType':'DATE','maxUsageDate':None},
    {'usageType':'NONE','maxUsageDistanceMeters':100}])
def test_invalid_thresholds_never_sent(changes):
    from garminops.gear import gear_payload
    with pytest.raises(ValueError):gear_payload(definition()|changes)


def test_inventory_includes_both_statuses_and_paginates_each():
    from garminops.writes import PlanWriter
    b=backend()
    from uuid import UUID
    for i in range(1,44):
        gid=str(UUID(int=i)); b._api.rows[gid]=response(definition())|{'uuid':gid,'status':'ACTIVE' if i<=21 else 'RETIRED'}
    assert PlanWriter(b).gear_inventory()==b._api.rows


@pytest.mark.parametrize('status',[None,'ALL','ACTIVE,RETIRED',True])
def test_invalid_gear_status_rejected_before_session(status):
    with pytest.raises(ValidationError):
        Backend('com').read('get_gear_items',{'start':0,'limit':20,'status':status})


def test_default_choices_preserve_real_structure_and_unknown_fields(monkeypatch):
    api=make_api('com'); calls=[]
    rows=[{'activityTypeKey':'running','defaultGearUUIDs':[GID],'extra':None}]
    def read(path, **kwargs): calls.append((path,kwargs)); return deepcopy(rows)
    monkeypatch.setattr(api,'connectapi',read)
    assert api.get_gear_default_choices('SHOES')==rows
    assert calls==[('/gear-service/gear/v2/default-gear-choices',{'params':{'gearTypes':'SHOES'}})]
    rows.clear()
    assert api.get_gear_default_choices('BIKE')==[]


@pytest.mark.parametrize('row',[None,{},[{}],[{'activityTypeKey':'running','defaultGearUUIDs':None}],
    [{'activityTypeKey':'running','defaultGearUUIDs':['bad']}],
    [{'activityTypeKey':'running','defaultGearUUIDs':[None]}]])
def test_default_choices_reject_unknown_shapes(monkeypatch,row):
    api=make_api('com');monkeypatch.setattr(api,'connectapi',lambda *a,**kw:row)
    with pytest.raises(UpstreamResponseError):api.get_gear_default_choices('SHOES')


@pytest.mark.parametrize('gear_type',['', 'SHOES&activityId=1', '../activity', 1])
def test_default_choice_arguments_checked_before_login(gear_type):
    with pytest.raises(ValidationError):
        Backend('com').read('get_gear_default_choices',{'gear_type':gear_type})


DEFAULT_RUNNING=[{'activityTypeKey':'running','defaultGear':True,'preferredGear':False}]

def set_defaults(b, activities):
    return execute(b,'set_gear_defaults',dict(expected_account='test',uuid=GID,activities=activities))


def test_set_clear_defaults_preserve_gear_and_are_idempotent():
    b=backend();create(b);original=deepcopy(b._api.rows[GID])
    assert set_defaults(b,DEFAULT_RUNNING)['data']['associatedActivityTypes']==DEFAULT_RUNNING
    count=len(b._api.calls)
    assert set_defaults(b,DEFAULT_RUNNING)['verified'] and len(b._api.calls)==count
    assert set_defaults(b,[])['verified'] and b._api.rows[GID]==original


def test_conflicting_default_never_displaces_other_gear():
    b=backend();create(b)
    other='00000000-0000-4000-8000-000000000002'
    b._api.rows[other]=response(definition())|{'uuid':other,'associatedActivityTypes':DEFAULT_RUNNING}
    count=len(b._api.calls)
    with pytest.raises(ContractUnverified):set_defaults(b,DEFAULT_RUNNING)
    assert len(b._api.calls)==count


@pytest.mark.parametrize('activities',[[{}],DEFAULT_RUNNING*2,
    [{'activityTypeKey':'running','defaultGear':True,'preferredGear':True}],
    [{'activityTypeKey':'running','defaultGear':1,'preferredGear':False}],
    [{'activityTypeKey':'../activity','defaultGear':True,'preferredGear':False}],
    [DEFAULT_RUNNING[0]|{'activityId':123}]])
def test_invalid_defaults_never_sent(activities):
    b=backend();create(b);count=len(b._api.calls)
    with pytest.raises((ContractUnverified,ValueError)):set_defaults(b,activities)
    assert len(b._api.calls)==count


def test_used_gear_defaults_never_written():
    b=backend();b._api.rows[GID]=response(definition())|{'numActivitiesLinked':1}
    with pytest.raises(ContractUnverified):set_defaults(b,DEFAULT_RUNNING)
    assert not b._api.calls


def test_default_mapping_must_match_readback():
    b=backend();create(b);b._api.get_gear_default_choices=lambda _:[]
    with pytest.raises(WriteFailure):set_defaults(b,DEFAULT_RUNNING)


def test_default_write_detects_unrelated_field_change():
    b=backend();create(b);request=b._api.request
    def changed(*args,**kwargs):
        response=request(*args,**kwargs);b._api.rows[GID]['notes']='unexpected';return response
    b._api.request=changed
    with pytest.raises(WriteFailure):set_defaults(b,DEFAULT_RUNNING)


def test_gear_activity_pagination_does_not_silently_clamp(monkeypatch):
    api=make_api('com');calls=[];rows=[{'activityId':1,'unknown':None}]
    def read(path,**kwargs):calls.append((path,kwargs));return rows
    monkeypatch.setattr(api,'connectapi',read)
    assert api.get_gear_activities(GID,20,1001)==rows
    assert calls==[('/activitylist-service/activities/'+GID+'/gear',{'params':{'start':20,'limit':1001}})]


@pytest.mark.parametrize('args',[{'gearUUID':GID,'limit':20},{'gearUUID':GID,'start':-1,'limit':20},
    {'gearUUID':GID,'start':0,'limit':True},{'gearUUID':'../activity','start':0,'limit':20}])
def test_gear_activity_arguments_checked_before_login(args):
    with pytest.raises(ValidationError):Backend('com').read('get_gear_activities',args)


def test_stats_preserve_undashed_uuid_and_unknown_fields(monkeypatch):
    api=make_api('com');row={'uuid':GID.replace('-',''),'totalDistance':0.0,'totalActivities':0,'unknown':[]}
    monkeypatch.setattr(api,'connectapi',lambda path:row)
    assert api.get_gear_stats(GID)==row


@pytest.mark.parametrize('method',['get_gear_activities','get_gear_stats'])
def test_missing_gear_never_looks_like_zero_usage(monkeypatch,method):
    api=make_api('com')
    def read(*args,**kwargs):raise GarminConnectNotFoundError('API Error 404')
    monkeypatch.setattr(api,'connectapi',read)
    with pytest.raises(GarminConnectNotFoundError):
        getattr(api,method)(GID,**({'start':0,'limit':20} if method=='get_gear_activities' else {}))


@pytest.mark.parametrize('row',[None,{}, {'uuid':'bad'}, {'uuid':'00000000-0000-4000-8000-000000000002'}])
def test_stats_reject_mismatched_identity(monkeypatch,row):
    api=make_api('com');monkeypatch.setattr(api,'connectapi',lambda path:row)
    with pytest.raises(UpstreamResponseError):api.get_gear_stats(GID)
