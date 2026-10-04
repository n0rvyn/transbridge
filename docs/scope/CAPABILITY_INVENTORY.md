# Garmin 权限与能力清单

2026-10-02：用户已同意四类权限。下面的 API 明细是开发核对表，不再逐项索要权限。

| 类别 | 内容 | 已定权限 |
| --- | --- | --- |
| 已发生的事实 | 活动、睡眠、体重、心率、饮食及其它记录 | 只读；禁止新增、导入、修改、删除记录或触发历史重算 |
| 训练计划 | 训练模板、日历排课等计划内容 | 可读写，包括创建、修改、删除、排课和取消排课 |
| 个人设置 | 最大心率、FTHR、区间、目标、默认装备等 | 可读写；不得连带修改历史 |
| 设备操作 | 发送训练等设备动作 | 读取允许；执行动作单独授权，不与排课捆绑 |

**读取统一允许。历史不可改的规则优先于其它权限。** 跨类别或不属于这四类的操作才单独提出；接口尚未验证是技术任务，不是权限待定。运行环境已在命名工具及出站请求两层执行权限规则。真实验证范围见 [../validation/LIVE_VERIFICATION.md](../validation/LIVE_VERIFICATION.md)。

## 本轮与后续范围

用户于 2026-10-02 指定：国区验证和 Connect+ 专属功能移至后续 TODO，不阻塞国际区普通账号交付。明细见 [SCOPE.md](SCOPE.md)。只有已证实需要 Connect+ 的能力才归入延期范围，不以未验证代替订阅归属判断。

## 技术状态

- G26 新增固定路线列表读取，安装版 dev.9 已返回真实空列表；不代表详情或写入已验证。

- `source_only_not_live_verified`：已读到对应源码，尚未通过真实账号验证。
- `contract_unverified`：接口契约仍需研究，不能据此宣布不支持或删掉已批准能力。
- W01–W06、G02 与 G07 已通过国际区真实 MCP 测试；G04 数值写入通过内部适配器验证，清空未解决。其余条目按实际证据保持未验证，详见 ../research/inventory.json。

认证、会话及内部辅助方法属于工程机制，不增加第五类用户数据权限。历史恢复请求需要查清是否改变记录；挑战加入/退出不属于已同意的四类，保留为局部例外，不阻塞其它能力。


## Source coverage


The source audit maps all **163 public methods declared on the Garmin class** in **garminconnect 0.3.17**. The locally installed 0.2.40 class has 129; 34 methods were added. The published release's main module matches the inspected upstream commit byte-for-byte. This bounded audit is not a claim of complete Garmin platform coverage.

See [source provenance](../research/sources.json) and the [complete method index](../research/SOURCE_METHODS.md). Glink's endpoint configuration, regional model, network interface, workout view model and wellness DTOs were also inspected. Glink reads and copies workout templates between regions, and includes activity-upload machinery; the latter must not be inherited by this connector. Its daily `maxHeartRate` DTO fields are observations, not proof of configured max HR access.

[Garmin's official program overview](https://developer.garmin.com/gc-developer-program/overview/) describes separate health, activity, training and course capabilities. These official APIs are distinct from the inspected Python library; access to them has not been established here. Courses are retained as a discovery row rather than excluded.


## Engineering checklist

Permission records below derive from the approved categories. Source links prove source presence only, not live compatibility. Full method mappings remain in [../research/SOURCE_METHODS.md](../research/SOURCE_METHODS.md).

### 已发生的事实

| ID | Data / resource | Operation | Permission | Technical evidence | Detail |
| --- | --- | --- | --- | --- | --- |
| R01 | Activity list and totals | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2586); not live verified | List, filter, count; preserve complete pagination. |
| R02 | Activity summary and detailed tracks/charts | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3370); not live verified | Chart and polyline defaults are not a promise of full-resolution data. |
| R03 | Activity laps and splits | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3294); not live verified |  |
| R04 | Activity weather | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3320); not live verified |  |
| R05 | Recorded heart-rate and power time in zones | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3328); not live verified | Historical analysis, separate from current zone settings. |
| R06 | Recorded strength exercise sets | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3391); not live verified |  |
| R07 | Activity-to-gear associations | Read | Allowed: read | Installed dev.27/28 MCP verified for recorded samples | All 55 activity gear associations read; unused gear activities empty page verified. Explicit pagination, no silent clamp; populated pagination unverified. History immutable. |
| R08 | Activity file exports | Read / export | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3260); not live verified | Source offers original, TCX, GPX, KML and CSV formats; per-activity availability untested. |
| R09 | Daily summary and combined body summary | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1146); not live verified |  |
| R10 | Steps, floors and intensity minutes | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1181); not live verified |  |
| R11 | Calories | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2225); not live verified |  |
| R12 | Heart rate and resting heart rate | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1341); not live verified | Daily maxHeartRate is a recorded measurement, not the configured max HR. |
| R13 | Sleep | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2116); not live verified |  |
| R14 | Stress | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2170); not live verified |  |
| R15 | Body Battery and events | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1577); not live verified |  |
| R16 | Respiration and oxygen saturation | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1944); not live verified |  |
| R17 | HRV | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2269); not live verified |  |
| R18 | Daily events and lifestyle logs | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1986); not live verified | These are wellness observations, not editable workout plans. |
| R19 | Weight and body composition | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1383); not live verified |  |
| R20 | Blood pressure | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1644); not live verified |  |
| R21 | Hydration logs | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1936); not live verified |  |
| R22 | Nutrition food logs and meals | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L4383); not live verified | Account entitlements and data availability untested. |
| R23 | Menstrual logs, calendar and reports | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3937); not live verified | The menstrual calendar includes recorded health data, not workout scheduling. |
| R24 | Pregnancy summary | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L4021); not live verified |  |
| R25 | Health Snapshot export | Read / export | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3285); not live verified |  |
| R26 | VO2/max metrics and trends | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1675); not live verified |  |
| R27 | Lactate-threshold measurements | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1741); not live verified | Observed threshold HR/speed/power, not evidence of an editable FTHR setting. |
| R28 | FTP measurements and trends | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3344); not live verified | Separate from configured power zones. |
| R29 | Training readiness, status and load | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2290); not live verified |  |
| R30 | Endurance, hill score, running tolerance and fitness age | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2368); not live verified |  |
| R31 | Race predictions and progress summaries | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2429); not live verified |  |
| R32 | Personal records | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1996); not live verified | Accept/reset/delete record operations would alter recorded achievements; not exposed by inspected class. |
| R33 | Badges and challenges | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2017); not live verified | Earned results remain immutable; joining a challenge would be a separate action. |
| R44 | Device solar observations | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2544); not live verified |  |
| R46 | Gear usage statistics | Read | Allowed: read | Installed dev.28 MCP unused gear statistics verified | Zero totals and UUID verified; preserve not-found errors. Used-gear statistics shapes unverified. |
| R47 | Golf scorecards and shots | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L4404); not live verified |  |
| R48 | Golf club and player statistics | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L4490); not live verified |  |
| R49 | Activity type catalog | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3020); not live verified | Reference taxonomy, not logged activity editing. |
| B01 | Recorded activity | Rename | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2643); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B02 | Recorded activity | Change type | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2651); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B03 | Recorded activity | Edit description | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2671); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B04 | Recorded activity | Create manually | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2684); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B05 | Recorded activity | Upload file | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2730); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B06 | Recorded activity | Import file | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2784); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B07 | Recorded activity | Delete | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2878); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B08 | Recorded strength activity | Replace exercise sets | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3399); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B09 | Recorded activity gear | Attach | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3455); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B10 | Recorded activity gear | Detach | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3486); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B11 | Body composition log | Add | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1404); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B12 | Weight log | Add | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1449); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B13 | Weight log | Delete one | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1541); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B14 | Weight log | Delete day entries | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1555); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B15 | Blood pressure log | Add | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1605); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B16 | Blood pressure log | Delete | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1661); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B17 | Hydration log | Add / adjust | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1855); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B18 | Menstrual daily log | Replace | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L4028); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B19 | Menstrual recorded calendar | Replace dates | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L4122); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B20 | Menstrual history | Initialize with confirmed period | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L4182); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |
| B21 | Menstrual history | Confirm period start | Prohibited: logged data | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L4218); not live verified | Upstream capability listed for completeness, not permission to expose or test it. |

### 训练计划

| ID | Data / resource | Operation | Permission | Technical evidence | Detail |
| --- | --- | --- | --- | --- | --- |
| R39 | Workout templates and FIT export | Read / export | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3539); not live verified | Templates are distinct from completed activities. |
| R40 | Scheduled workout calendar | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3847); not live verified | Upstream next-workout helper searches only current/next month and documents incomplete adaptive-plan visibility. |
| R41 | Training plans and adaptive plans | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L4361); not live verified | Plan details do not establish full Coach/adaptive calendar coverage. |
| W01 | Workout template | Create | Allowed: write without history changes | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3569); international MCP verified | Generic JSON plus six typed sport helpers. Creation is separate from calendar scheduling. |
| W02 | Workout template | Update / replace | Allowed: write without history changes | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3589); international MCP verified | Whole-object PUT; preserves ID. Read full object before modifying; verify effects on scheduled references. |
| W03 | Workout template | Delete | Allowed: write without history changes | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3554); international MCP verified | Check impact on scheduled references before any approved use. |
| W04 | Workout calendar entry | Schedule | Allowed: write without history changes | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3913); international MCP verified | POST using template ID and date. |
| W05 | Workout calendar entry | Unschedule | Allowed: write without history changes | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3928); international MCP verified | DELETE using scheduled-instance ID, not template ID. |
| W06 | Workout calendar entry | Reschedule | Allowed: write without history changes | International MCP verified | Creates replacement then removes original; non-atomic, partial outcomes reported. |
| G26 | Courses / routes | Read | Allowed: read | Contract unverified | Garmin official program describes Courses API. No course methods in inspected Garmin class; access route unverified. |
| G27 | Courses / routes | create | Allowed: write without history changes | Contract unverified | Garmin official program describes Courses API. No course methods in inspected Garmin class; access route unverified. |
| G28 | Courses / routes | update | Allowed: write without history changes | Contract unverified | Garmin official program describes Courses API. No course methods in inspected Garmin class; access route unverified. |
| G29 | Courses / routes | delete | Allowed: write without history changes | Contract unverified | Garmin official program describes Courses API. No course methods in inspected Garmin class; access route unverified. |
| G31 | Race/event calendar and notes | Read | Allowed: read | Independent future notes and private events MCP verified | dev.19 notes and dev.21 private independent events passed create/read/rename/move/delete; calendars and activity list restored. Other event variants and training-plan tasks remain unverified. Activity notes remain immutable. |
| G32 | Race/event calendar and notes | create | Allowed: write without history changes | Independent future notes and private events MCP verified | dev.19 notes and dev.21 private independent events passed create/read/rename/move/delete; calendars and activity list restored. Other event variants and training-plan tasks remain unverified. Activity notes remain immutable. |
| G33 | Race/event calendar and notes | update | Allowed: write without history changes | Independent future notes and private events MCP verified | dev.19 notes and dev.21 private independent events passed create/read/rename/move/delete; calendars and activity list restored. Other event variants and training-plan tasks remain unverified. Activity notes remain immutable. |
| G34 | Race/event calendar and notes | delete | Allowed: write without history changes | Independent future notes and private events MCP verified | dev.19 notes and dev.21 private independent events passed create/read/rename/move/delete; calendars and activity list restored. Other event variants and training-plan tasks remain unverified. Activity notes remain immutable. |
| G35 | Training plans / Coach enrollment | Enroll | Allowed: write without history changes | Contract unverified | Plan readers exist; no named enrollment or editing methods in inspected class. |
| G36 | Training plans / Coach enrollment | change | Allowed: write without history changes | Contract unverified | Plan readers exist; no named enrollment or editing methods in inspected class. |
| G37 | Training plans / Coach enrollment | stop | Allowed: write without history changes | Contract unverified | Plan readers exist; no named enrollment or editing methods in inspected class. |

### 个人设置

| ID | Data / resource | Operation | Permission | Technical evidence | Detail |
| --- | --- | --- | --- | --- | --- |
| R34 | Goals | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3025); not live verified | Reading includes goals by status; writes require separate decisions. |
| R35 | Profile and general settings | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L1138); not live verified | Field-level review required; this is not approval for all profile fields. |
| R36 | Configured heart-rate zones | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3352); not live verified | Verify per-sport/device field structure before interpreting max HR, resting HR, or FTHR. |
| R37 | Configured power zones | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3357); not live verified |  |
| R38 | Nutrition settings | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L4397); not live verified | Separate from food logs. |
| R43 | Device settings and alarms | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2527); not live verified | No named setters in inspected class. |
| R45 | Gear definitions and defaults | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3078); not live verified | Separate from associations on logged activities. |
| W08 | Gear definition | Create | Allowed: write without history changes | Unused independent gear verified via installed dev.23 MCP | Create/read/rename/delete passed; original inventory and activity list unchanged. Defaults, usage tracking, retired or associated gear remain unverified. |
| W09 | Gear defaults | Set default | Allowed: write without history changes | Installed dev.27 MCP verified for unused independent gear | Set/read/clear passed; all 55 historical gear associations unchanged; original defaults/inventory restored. Conflicts, preferred and used gear unverified. |
| W10 | Gear defaults | Remove default | Allowed: write without history changes | Installed dev.27 MCP verified for unused independent gear | Set/read/clear passed; all 55 historical gear associations unchanged; original defaults/inventory restored. Conflicts, preferred and used gear unverified. |
| W11 | Menstrual tracking configuration | Update settings | Allowed: write without history changes | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L4255); not live verified | Merges supplied settings with stored settings and PUTs profile subset; logging operations remain prohibited. |
| G01 | Configured maximum HR | Read field | Allowed: read | Contract unverified | Do not confuse daily maxHeartRate with profile or sport-specific max HR. Zone/profile readers exist; exact setting write is unverified. |
| G02 | Configured maximum HR | update field | Allowed: write without history changes | International MCP verified | Do not confuse daily maxHeartRate with profile or sport-specific max HR. Zone/profile readers exist; exact setting write is unverified. |
| G03 | Configured FTHR / LTHR | Read field | Allowed: read | Contract unverified | User example. Historical lactate-threshold methods are not a setting setter; establish account/device/sport scope. |
| G04 | Configured FTHR / LTHR | update field | Allowed: write without history changes | Contract unverified | User example. Historical lactate-threshold methods are not a setting setter; establish account/device/sport scope. |
| G05 | Configured resting HR | Read field | Allowed: read | Contract unverified | Different from daily measured resting HR. |
| G06 | Configured resting HR | update field | Allowed: write without history changes | Contract unverified | Different from daily measured resting HR. |
| G07 | Heart-rate zones | Update boundaries | Allowed: write without history changes | Contract unverified | Read method exists; no named write method in inspected class. |
| G08 | Heart-rate zone calculation | Change basis | Allowed: write without history changes | Contract unverified | Separate decision from boundary values, max HR and FTHR. |
| G09 | Heart-rate automatic detection | Enable | Allowed: write without history changes | Contract unverified | Candidate setting; exact API and side effects unverified. |
| G10 | Heart-rate automatic detection | disable | Allowed: write without history changes | Contract unverified | Candidate setting; exact API and side effects unverified. |
| G11 | Configured FTP | Read field | Allowed: read | International MCP verified | Current configuration, distinct from historical FTP. Cycling FTP also changes cross-country-ski settings; reported explicitly. |
| G12 | Configured FTP | update field | Allowed: write without history changes | International MCP verified | Current configuration, distinct from historical FTP. Cycling FTP also changes cross-country-ski settings; reported explicitly. |
| G13 | Power zones | Update boundaries | Allowed: write without history changes | International MCP verified | Named connector power setter verified; exact original profiles restored. |
| G14 | Power zones | basis | Allowed: write without history changes | Contract unverified | Read methods exist; no named write method in inspected class. |
| G15 | Profile fields and preferences | Update individual fields | Allowed: write without history changes | Contract unverified | Choose exact fields separately: identity, units and training-profile values are not one blanket permission. |
| G16 | Device settings and alarms | Create | Allowed: write without history changes | Contract unverified | Stored settings and alarm configuration fall under personal settings. A command to execute on a device is a separate device action. Verify the exact target and effects. |
| G17 | Device settings and alarms | update | Allowed: write without history changes | Contract unverified | Stored settings and alarm configuration fall under personal settings. A command to execute on a device is a separate device action. Verify the exact target and effects. |
| G18 | Device settings and alarms | delete | Allowed: write without history changes | Contract unverified | Stored settings and alarm configuration fall under personal settings. A command to execute on a device is a separate device action. Verify the exact target and effects. |
| G19 | Goals | Create | Allowed: write without history changes | Future independent goals verified | Installed dev.17 MCP create/rename/delete passed on an authorized test account; original goal and activity lists unchanged. Started goals and date-effective daily goal writes remain unverified. |
| G20 | Goals | update | Allowed: write without history changes | Future independent goals verified | Installed dev.17 MCP create/rename/delete passed on an authorized test account; original goal and activity lists unchanged. Started goals and date-effective daily goal writes remain unverified. |
| G21 | Goals | delete | Allowed: write without history changes | Future independent goals verified | Installed dev.17 MCP create/rename/delete passed on an authorized test account; original goal and activity lists unchanged. Started goals and date-effective daily goal writes remain unverified. |
| G22 | Nutrition settings | Update individual settings | Allowed: write without history changes | Contract unverified | Separate from recorded food/meal changes, which remain prohibited. |
| G23 | Gear definitions | Update | Allowed: write without history changes | Unused independent gear verified via installed dev.25 MCP | Create/read/rename, usage thresholds, retire/reactivate and delete passed; full ACTIVE/RETIRED inventory and activity list unchanged. Used gear, defaults, images and collections remain unverified. |
| G24 | Gear definitions | retire | Allowed: write without history changes | Unused independent gear verified via installed dev.25 MCP | Create/read/rename, usage thresholds, retire/reactivate and delete passed; full ACTIVE/RETIRED inventory and activity list unchanged. Used gear, defaults, images and collections remain unverified. |
| G25 | Gear definitions | delete | Allowed: write without history changes | Unused independent gear verified via installed dev.25 MCP | Create/read/rename, usage thresholds, retire/reactivate and delete passed; full ACTIVE/RETIRED inventory and activity list unchanged. Used gear, defaults, images and collections remain unverified. |
| G40 | Social connections and privacy | Read | Allowed: read | Contract unverified | Discovery candidate, not confirmed support. Sharing recorded activity metadata would violate the historical-write rule. |
| G41 | Social connections and privacy | change settings | Allowed: write without history changes | Contract unverified | Privacy preferences fall under personal settings only if history is unchanged. Friend/follow/invite/message actions are not included in this row or authorized by the four-category policy. |

### 设备操作

| ID | Data / resource | Operation | Permission | Technical evidence | Detail |
| --- | --- | --- | --- | --- | --- |
| R42 | Device list, primary and last-used device | Read | Allowed: read | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L2520); not live verified |  |
| W07 | Workout delivery | Send to device | Separate authorization: device action | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3802); not live verified | Source defaults to last-used device and first listed workout if IDs omitted; device action authorization must identify its intended targets. Server acceptance does not prove watch receipt. |
| G30 | Courses / routes | send | Separate authorization: device action | Contract unverified | Garmin official program describes Courses API. No course methods in inspected Garmin class; access route unverified. |

### 工程机制 / 分类例外

| ID | Data / resource | Operation | Permission | Technical evidence | Detail |
| --- | --- | --- | --- | --- | --- |
| G38 | Challenges | Join | Exception: challenge participation is outside the four agreed categories | Contract unverified | Read methods exist; no named action methods in inspected class. |
| G39 | Challenges | leave | Exception: challenge participation is outside the four agreed categories | Contract unverified | Read methods exist; no named action methods in inspected class. |
| O01 | Authentication | Login / MFA continuation | Internal mechanism; not a data permission decision | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L846); not live verified | Authentication infrastructure, not a Garmin data-write grant. |
| O02 | Session | Logout / clear cached tokens | Internal mechanism; not a data permission decision | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L4325); not live verified | Local session effects; confirmation behavior and storage location undecided. |
| O03 | Archived data restoration | Request reload | Technical check: establish no history mutation | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L3529); not live verified | POST requests old data restoration. Not automatically classified as read-only merely because its purpose is reading; verify effects. |
| O04 | Generic API and download access | Arbitrary requests | Internal only; cannot bypass category permissions | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L832); not live verified | AI proposal: keep internal only. Arbitrary GraphQL documents or method/path dispatch can bypass named-operation restrictions. |
| O05 | Typed model namespace | Wrap supported methods | Internal mechanism; not a data permission decision | [Source](https://github.com/cyberjunky/python-garminconnect/blob/218e72ca5459e014435fc2d94fd18bd601fa0c14/garminconnect/__init__.py#L808); not live verified | Internal helper, not an additional Garmin data category. |

## Findings that affect later design


1. Max HR/FTHR writes are not established. Source exposes heart-rate zone reads and historical threshold reads, but no dedicated setting setters. Real read samples and a verified write contract are required before building these operations.
2. Current source uses a native client; upstream documents an authentication migration from the older garth-backed series. Do not copy the local 0.2.40 authentication path into a new runtime without a deliberate dependency decision.
3. Template update replaces the object. Calendar schedule and unschedule use different resource IDs. A move cannot be claimed atomic from two separate operations.
4. The upstream next-workout helper checks only two months and explicitly warns that some adaptive/Coach sessions are absent. That convenience method is not evidence of full calendar coverage.
5. Upstream has page-size limits, a 2,000-request pagination guard and chart/polyline defaults. These must not silently become connector scope or completeness claims.
6. Configuration changes require field-level side-effect checks so settings writes do not rewrite observations. A broad profile endpoint is not a safe blanket permission.
7. The four-category permission policy is approved. Research now resolves technical contracts; only cross-category exceptions and device actions need separate authorization.

## Verification before runtime work

See [SCOPE.md](SCOPE.md). For each selected operation record account/region, sanitized real input/output structure, exact request and side effects, read-back results, and device verification where relevant. Do not use real logged-data mutations as tests.
