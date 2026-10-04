# Garmin web contract research

Observed 2026-10-02. Engineering evidence only; this document does not expand
permissions or establish a working write contract.

## Public application sources

The authenticated Garmin page identified the public application release as
`5.29.0.15`. Public scripts were downloaded without cookies or account credentials.

| Source | SHA-256 |
| --- | --- |
| [Bootstrap](https://connect.garmin.com/web-react/static/js/index__bundle__5.29.0.15.js) | `13918c6cb61a6c6fe9e5b4d4598deeffac5565541ee1497b43830be3c4205c83` |
| [Shared application chunk](https://connect.garmin.com/web-react/static/js/16110.901362e2.chunk__5.29.0.15.js) | `a3abc878d49cfbe13d46a273b955508801a1072d55f1b4a4e2222b1c0819e115` |

Local research copies are temporary and excluded from the release.
Their machine-specific location is not public provenance. URLs are versioned and can expire.

## Observed handlers in the shared chunk

- Heart-rate zone reading uses GET `/biometric-service/heartRateZones/`.
- Power-zone reading includes a branch using GET
  `/biometric-service/powerZones/sports/all?generateDefaults=false`.
  The parameter's actual server-side effects have not been tested.
- User-setting updates use PUT
  `/userprofile-service/userprofile/user-settings/` with a `userData` wrapper
  around the supplied fields. Other handlers send distinct settings subsets.
  This is not permission to forward an arbitrary profile or logged values.
- Effective goal reading uses GET `/goal-service/goal/user/effective/{date}`.
  Updating a goal uses PUT
  `/goal-service/goal/user/effective/{type}/{date}` with a goal payload.
  Date semantics and effects on prior daily goals require real verification
  before exposing a setter; a dated goal is not a timeless preference.
- The application also contains biometric observation writers. They remain
  prohibited and must never be inherited simply because they share a service.

## Threshold clearing: accepted known issue KI-001, investigation stopped

User decision on 2026-10-02: no further tests, probes or restoration attempts
for this issue unless explicitly reopened. Numeric zero remains distinct from
the original null. The observations below are historical evidence, not an
instruction to continue investigating. See ../scope/SCOPE.md.


The bootstrap, shared chunk and observed settings dependencies were inspected.
They did not establish a way to restore `lactateThresholdHeartRateUsed` to null.
This bounded inspection does not prove that no such endpoint exists elsewhere.
No guessed sentinel, deletion, reset or additional threshold write was attempted.
The earlier residual numeric zero is still not a restored null value.

The next write-contract investigation can use the observed official handlers,
but must validate real input shapes, exact resource effects and restoration before
shipping a new write. Source evidence alone is not an end-to-end test.

## Goal resource distinction verified

The shared chunk also uses POST `/goal-service/goal/goal`, and PUT/DELETE
`/goal-service/goal/goal/{id}` for independent training goals. These routes
are distinct from dated effective goals and the `/goal/user/{id}` route.
The official running-goal creation form shows a name, activity type, goal type
(hours, distance, calories or activities), target, duration and start date.
The form was inspected without saving.

Live response observations and roundtrip evidence remain in ignored local research logs. Source evidence alone does not validate a write contract.


## Independent calendar notes

The shared 5.29.0.15 chunk has POST /calendar-service/note with noteName, content, date, id:null; PUT /calendar-service/note/{id} with the same fields and the resource ID; GET and DELETE use that same ID route. Training-plan notes use a different service. The note response contract includes id, noteName, content and date; calendar representation uses itemType=note, matching id/date and null trainingPlanId. Prototype execution and cleanup records remain in ignored local research logs. This does not establish contracts for other event or note resources.

## Calendar event editor: source contract, not live write verification

Retrieved the official [event editor module](https://connect.garmin.com/web-react/static/js/50719.cbc4808c.chunk__5.29.0.15.js)
without credentials on 2026-10-02. SHA-256:
`b10cbd41e395b8f376317f2730640c7041f2cf8d530ce464913ed711c63b5975`.
The create-page module 135100 in chunk 35100 imports editor module 150719;
the editor imports event request handlers from module 570088. This establishes
the actual form-to-handler relationship rather than borrowing the discovery
event conversion helper's payload.

- Basic fields: date, eventName, eventType, eventTimeLocal. When no start time
  is entered, eventTimeLocal is null; otherwise it contains startTimeHhMm and
  timeZoneId. The form checks a nonblank name with at most 254 characters.
- Options getData returns race, official and eventPrivacy with a label of
  PRIVATE, PUBLIC_SHAREABLE or PUBLIC_SHAREABLE_DISCOVERABLE. The initial
  state also contains privacy booleans, but the submitted options object
  does not simply forward that initial state.
- Distance/location fields include courseId, courseName, location,
  locationStartPoint and completionTarget. A distance target has value, unit,
  unitType=distance; a duration target has value, unit=second, unitType=time.
  An unselected course ID of -1 becomes null. Triathlon adds separate leg
  targets and triathlonType; it is not interchangeable with a single target.
- Additional fields include note, url, imageUrl and optional imageFile.
  Image upload uses a separate call. The editor merges the four sections;
  when editing it additionally spreads the original response before the
  changed fields. A connector must inspect that response for linked plans
  and recorded results before deciding which definitions can be written.
- The editor calls handler W2 for creation, qM followed by wA for editing;
  optional image removal/upload adds further calls. Coach/adaptive origins
  take a separate path. These extra effects must be understood before
  treating every editor save as a simple private calendar update.

The inspected browser form was cancelled without saving. No event was created,
updated or deleted in this research step. Real response samples, exact update
side effects and the installed MCP roundtrip are still required.


## Private event prototype: live evidence

Per-account prototype dates, changes and cleanup records remain in ignored local research logs.

The real response includes eventCustomization with customGoal, isPrimaryEvent,
associatedWithActivityId, isTrainingEvent, isGoalMet, trainingPlanId,
trainingPlanType and enrollmentTime. Private responses contain an explicit
privacy label and false sharing/discovery flags. Empty url, courseName and
imageUrl inputs are normalized or omitted in the response; direct payload
versus response equality is not a valid verification strategy for those fields.

The qM handler writes the event definition and can additionally modify official
status. The wA handler exclusively requests/removes official status; it is not
an ordinary event rename requirement. Public/group/Coach-linked event contracts and the installed MCP write path require separate verification.

## Dated floors goal investigation (2026-10-02)

Official floors module 53937.07b93e17, release 5.29.0.15, SHA-256
`3913826c60bae8de335f75613f54f54836d0e38c918873c09b863ac8987e638c`:
https://connect.garmin.com/web-react/static/js/53937.07b93e17.chunk__5.29.0.15.js

The editor receives today's date, independently of the chart's selected date.
Its save action submits goalType=FLOORS_CLIMBED and goalValue to the shared
handler, which maps the type to floors-climbed in the dated effective-goal PUT
route. The form was inspected without saving.

The dated effective-goal write contract remains unresolved; no runtime goal setter was added. Individual request results and settings read-backs remain in ignored local research logs.

## Gear v2: definitions versus historical associations

Official editor and dependency, release 5.29.0.15:

- https://connect.garmin.com/web-react/static/js/34445.c8a69643.chunk__5.29.0.15.js
  SHA-256 `449ea00c04a6e74f56d732bc4f545ac739fe160cd3686d5634bd76c74c5c19fe`.
- https://connect.garmin.com/web-react/static/js/27701.fbd31d67.chunk__5.29.0.15.js
  SHA-256 `ca6182b818ec4417a8a81cb6246f218dccac081d5a6631cc07fb2d3f8b9d0457`.

The new-gear form contains
gear type, brand/model, nickname, first-use date, usage tracking and thresholds,
default activities and notes. The unsaved form was cancelled.

Source handlers use GET /gear-service/gear/v2/list with start/limit/status,
GET /gear-service/gear/v2/{uuid}, POST /gear-service/gear/v2, and PUT/DELETE
/gear-service/gear/v2/{uuid}. The definition includes uuid, gearType, brand,
model, name, firstUseDate, usageType, three maxUsage fields,
associatedActivityTypes and notes. No create/update payload has been validated
against a live response yet.

Crucially, the editor's addToExistingActivities flag begins false. When it is
true and selected activity types are present, the save flow makes an additional
POST to /gear-service/gear/v2/{uuid}/activity-type-association. Collections have
a corresponding association route. Separate PUT/DELETE requests to
/gear-service/activity/v2/{activityId}/associated-gear directly alter recorded
activity associations. These historical writers remain prohibited and now have
explicit outbound-denial regression coverage. Do not copy the editor's optional
historical-assignment flow when adding gear definition/default settings support.



## 本地研究日志

逐版本装备验证、真实账号设置与请求回读、测试资源清理记录保存在忽略的 `logs/research/WEB_CONTRACT_RESEARCH.md`。这些本机证据不随插件分发。公开协议说明不是完整业务兼容性声明。
