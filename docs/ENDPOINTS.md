# REST Endpoint Index

Every REST service path in the client. **141 unique paths**, verified identical in `2.23.0` and `2.24.0`.

Extracted from the IL2CPP string-literal table with [`tools/dump_metadata_literals.py`](../tools/dump_metadata_literals.py); cross-checked against decompiled `2.23.0` source, which independently yielded 139 of the 141 (the two it missed carry query strings).

## How a URL is built

`LKWD/WebService/WebRequest.cs → Dispatch()`:

```
if (api looks like an absolute URL)      → use it verbatim
else if (request has Microservice flag)  → base = APIEndpoint with trailing "api/" stripped
else                                     → base = APIEndpoint  (legacy Python API)
uri = base + api
```

With production `APIEndpoint = https://api-sni.avkn.co/api/`:

| Flag | Resulting URL |
|---|---|
| `Microservice` | `https://api-sni.avkn.co/` + `auth/1/auth/1/login` |
| legacy | `https://api-sni.avkn.co/api/` + `<path>` |

Almost everything modern sets `Microservice`. The doubled-looking shape `auth/1/auth/1/login` is literal — it is `<service>/<ver>/<resource>/<ver>/<action>`.

Method defaults to `POST` (`CreateRequest(..., eHTTPMethod lMethod = eHTTPMethod.POST)`); `GET`/`PUT`/`DELETE`/`PATCH`/`HEAD` are available and used by the REST-ish services (`relations`, `gateway`, `nativeecom`).

`{0}`/`{1}` below are runtime-formatted segments.

---

## auth — identity, session, remote config (13)

| Path | Purpose |
|---|---|
| `auth/1/auth/1/login` | The single login call; `type` field selects provider |
| `auth/1/auth/1/register` | Complete registration |
| `auth/1/auth/1/preregister` | Allocate a pre-session before signup |
| `auth/1/auth/1/start_registration` | Begin registration flow |
| `auth/1/auth/1/validate-email` | Email validation |
| `auth/1/auth/1/touch` | Keep session warm |
| `auth/1/auth/1/current` | Current account info |
| `auth/1/auth/1/configs` | Remote configuration bundle |
| `auth/1/auth/1/sfstoken` | Short-lived SmartFox zone-login token |
| `auth/1/auth/1/geoip` | Geo lookup |
| `auth/1/auth/1/dataportal` | GDPR data portal |
| `auth/1/entry/1/restricted/get` | Project restricted entries |
| `auth/1/helpshift/1/qrcode` | Helpshift support QR |

## ws — the "world service" workhorse (34)

**Areas / homes:** `ws/1/area/1/get`, `list`, `save`, `rate`
**Currency & progression:** `ws/1/balance/1/get`, `ws/1/xp/1/get`, `ws/1/stat/1/get`, `ws/1/balanceconverter/1/fulfill`
**Identity:** `ws/1/username/1/check`, `resolve`, `evloser`, `ws/1/profile/1/set`, `ws/1/lastseen/1/get`
**Pets:** `ws/1/avapet/1/get`, `save`, `touch`
**Build machine (crafting):** `ws/1/bmachine/2/list`, `build`, `buy`, `boost`, `cancel`, `complete`
**Push:** `ws/1/push/1/register`, `unregister`, `preferences/get`, `preferences/set`
**Misc:** `ws/1/events/1/list`, `ws/1/likes/1/set`, `ws/1/adshint/1/hint`, `ws/1/popup/1/list`, `ws/1/popup/1/feedback`, `ws/1/forgottenpassword/1/request`, `ws/1/userentry/1/user/get`, `ws/1/userentry/1/user/set`

## games — contests, minigames, mystery box (16)

**Contests** (`games/1/contest/1/…`): `list-contests`, `enter-contest`, `check-prerequisites`, `contestants`, `contest-entries`, `contest-leaderboard`, `contest-result`, `result-overview`, `submit-votes`, `votes-progress`, `starpower`, `starpower-leaderboard`, `imageoftheday`
**Mystery box:** `games/1/mbox/16/odds`, and `games/1/mbox/16/play?currency={0}`
**Spin wheel:** `games/1/sw/1/get`, `games/1/sw/1/claim`

## rewards (10)

`rewards/1/userreward/1/list`, `award`, `receive` · `rewards/1/rewards/1/details`, `xprewards` · `rewards/1/dailybonus/1/list/{0}`, `claim/{0}` · `rewards/1/gamerewards/1/redeem`, `rate-limiter` · `rewards/1/userchallenge/1/completed`

## ext — external/social integrations (9)

`ext/1/friendcodes/1/get`, `resolve`, `branch-read` · `ext/1/samenetwork/1/status`, `remove` · `ext/1/playerreporting/1/report`, `check` · `ext/1/sharedid/1/get` · `ext/1/ads/1/rate_limits/2`

## shop / commerce (11)

`shop/1/itemshop/1/purchase`, `shop/1/itemshop/1/recommend`, `shop/1/discounts/1/list`, `shop/1/bundleshop/1/list` · `coinpacks/1/coinpack/1/list`, `buy` · `items/1/useritem/1/list` · `lightningsale/1/lightningsale/1/get` · `steam/1/steam/1/init_tran`, `generate_refund_token` · `swagse/shop/search/v2`, `click/v2`, `purchase/v2` *(absolute-URL affiliate shop)*

## subscriptions (5)

`subscriptions/1/subscriptions/1/get`, `list_packs`, `process_receipt`, `reprocess`, `acknowledge_claims`

## glm — "Golem" content/config service (5)

`glm/1/ping/1`, `glm/1/config/get/2`, `glm/1/ftue_version/post/1`, `glm/1/ftue_registration_version/post/1`, `glm/1/ugc_templates/1`

## dailytasks (4)

`dailytasks/1/dailytasks/1/list`, `update`, `claim`, `cancel`

## gateway — clans/groups (4)

`gateway/1/gateway/1/clan-service`, `…/invitations`, `…/invitations/pending/{0}`, `gateway/1/gateway/1/dominii`

## nativeecom — physical merchandise (4)

`nativeecom/1/nativeecom/1/proxy/`, `link_account`, `link_account_status`, `unlink_account/`
Behind the proxy: `api-proxy/service/affil/product/v2/items`

## profile (3)

`profile/1/profile/1/get`, `data`, `marketing`

## objects — generic key/value blobs (3)

`objects/1/objects/1/put`, `get`, `del/2`

## consent / age verification (6)

`consent/1/consent/1/current`, `check`, `list/current` · `ageverification/1/ageverification/1/start_flow`, `estimate`, `verification_status`

## Everything else (12)

| Path | Purpose |
|---|---|
| `entry/1/entry/1/global` · `global/lite` | Global entries |
| `entry/1/entry/1/ping?request_id=` | Latency probe |
| `relations/1/relations/1/{0}` | Friend/block relations (REST verbs) |
| `search/1/search/1/search` | Player/content search |
| `messagefilter/1/messagefilter/1/check` | Profanity/message filter |
| `filter/1/rules/1/list` | Filter rule set |
| `usermail/{0}/usermail/2/{1}` | In-game mail |
| `imageapi/v1/requestupload/` | Image upload ticket |
| `userjourney/1/userjourney/1/submit` | Journey telemetry |
| `logreceiver/1/clientlogs/1/manifest` | Client log upload manifest |
| `warehouse-receiver/1/warehouse/1/` | Analytics warehouse |
| `discordbot/1/discordbot/1/generate_code` | Discord link code |
| `planetplay/1/planetplay/1/link` · `link/status` | PlanetPlay partner link |
| `modio/1/modio/1` | mod.io integration |

---

## Appendix — raw sorted list

All 141, straight from the string-literal table.

```
ageverification/1/ageverification/1/estimate
ageverification/1/ageverification/1/start_flow
ageverification/1/ageverification/1/verification_status
auth/1/auth/1/configs
auth/1/auth/1/current
auth/1/auth/1/dataportal
auth/1/auth/1/geoip
auth/1/auth/1/login
auth/1/auth/1/preregister
auth/1/auth/1/register
auth/1/auth/1/sfstoken
auth/1/auth/1/start_registration
auth/1/auth/1/touch
auth/1/auth/1/validate-email
auth/1/entry/1/restricted/get
auth/1/helpshift/1/qrcode
coinpacks/1/coinpack/1/buy
coinpacks/1/coinpack/1/list
consent/1/consent/1/check
consent/1/consent/1/current
consent/1/consent/1/list/current
dailytasks/1/dailytasks/1/cancel
dailytasks/1/dailytasks/1/claim
dailytasks/1/dailytasks/1/list
dailytasks/1/dailytasks/1/update
discordbot/1/discordbot/1/generate_code
entry/1/entry/1/global
entry/1/entry/1/global/lite
entry/1/entry/1/ping?request_id=
ext/1/ads/1/rate_limits/2
ext/1/friendcodes/1/branch-read
ext/1/friendcodes/1/get
ext/1/friendcodes/1/resolve
ext/1/playerreporting/1/check
ext/1/playerreporting/1/report
ext/1/samenetwork/1/remove
ext/1/samenetwork/1/status
ext/1/sharedid/1/get
filter/1/rules/1/list
games/1/contest/1/check-prerequisites
games/1/contest/1/contest-entries
games/1/contest/1/contest-leaderboard
games/1/contest/1/contest-result
games/1/contest/1/contestants
games/1/contest/1/enter-contest
games/1/contest/1/imageoftheday
games/1/contest/1/list-contests
games/1/contest/1/result-overview
games/1/contest/1/starpower
games/1/contest/1/starpower-leaderboard
games/1/contest/1/submit-votes
games/1/contest/1/votes-progress
games/1/mbox/16/odds
games/1/mbox/16/play?currency={0}
games/1/sw/1/claim
games/1/sw/1/get
gateway/1/gateway/1/clan-service
gateway/1/gateway/1/clan-service/invitations
gateway/1/gateway/1/clan-service/invitations/pending/{0}
gateway/1/gateway/1/dominii
glm/1/config/get/2
glm/1/ftue_registration_version/post/1
glm/1/ftue_version/post/1
glm/1/ping/1
glm/1/ugc_templates/1
items/1/useritem/1/list
lightningsale/1/lightningsale/1/get
logreceiver/1/clientlogs/1/manifest
messagefilter/1/messagefilter/1/check
modio/1/modio/1
nativeecom/1/nativeecom/1/link_account
nativeecom/1/nativeecom/1/link_account_status
nativeecom/1/nativeecom/1/proxy/
nativeecom/1/nativeecom/1/unlink_account/
objects/1/objects/1/del/2
objects/1/objects/1/get
objects/1/objects/1/put
planetplay/1/planetplay/1/link
planetplay/1/planetplay/1/link/status
profile/1/profile/1/data
profile/1/profile/1/get
profile/1/profile/1/marketing
relations/1/relations/1/{0}
rewards/1/dailybonus/1/claim/{0}
rewards/1/dailybonus/1/list/{0}
rewards/1/gamerewards/1/rate-limiter
rewards/1/gamerewards/1/redeem
rewards/1/rewards/1/details
rewards/1/rewards/1/xprewards
rewards/1/userchallenge/1/completed
rewards/1/userreward/1/award
rewards/1/userreward/1/list
rewards/1/userreward/1/receive
search/1/search/1/search
shop/1/bundleshop/1/list
shop/1/discounts/1/list
shop/1/itemshop/1/purchase
shop/1/itemshop/1/recommend
steam/1/steam/1/generate_refund_token
steam/1/steam/1/init_tran
subscriptions/1/subscriptions/1/acknowledge_claims
subscriptions/1/subscriptions/1/get
subscriptions/1/subscriptions/1/list_packs
subscriptions/1/subscriptions/1/process_receipt
subscriptions/1/subscriptions/1/reprocess
userjourney/1/userjourney/1/submit
warehouse-receiver/1/warehouse/1/
ws/1/adshint/1/hint
ws/1/area/1/get
ws/1/area/1/list
ws/1/area/1/rate
ws/1/area/1/save
ws/1/avapet/1/get
ws/1/avapet/1/save
ws/1/avapet/1/touch
ws/1/balance/1/get
ws/1/balanceconverter/1/fulfill
ws/1/bmachine/2/boost
ws/1/bmachine/2/build
ws/1/bmachine/2/buy
ws/1/bmachine/2/cancel
ws/1/bmachine/2/complete
ws/1/bmachine/2/list
ws/1/events/1/list
ws/1/forgottenpassword/1/request
ws/1/lastseen/1/get
ws/1/likes/1/set
ws/1/popup/1/feedback
ws/1/popup/1/list
ws/1/profile/1/set
ws/1/push/1/preferences/get
ws/1/push/1/preferences/set
ws/1/push/1/register
ws/1/push/1/unregister
ws/1/stat/1/get
ws/1/userentry/1/user/get
ws/1/userentry/1/user/set
ws/1/username/1/check
ws/1/username/1/evloser
ws/1/username/1/resolve
ws/1/xp/1/get
```
