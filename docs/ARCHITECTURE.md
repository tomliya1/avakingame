# Client Architecture

Client `2.23.0` (`LifeClient_2_23_0`). Unity, IL2CPP, net6/CoreCLR when loaded under MelonLoader.

---

## 1. Layering

The managed code splits into two generations that coexist:

| Layer | Namespace | Role |
|---|---|---|
| Legacy core | `Lockwood/` | Avatar generation & config, friends, XP, badges, challenges, the SmartFox wrapper, login handler, `Globals` (CDN URL construction) |
| Modern services | `LKWD/` | `WebService` (REST + WebSocket), wallet/IAP, LibChat, groups, contests, daily tasks, UGC, telemetry, configuration |
| Game/flow | root, `States/`, `UI/` | `State_*` flow states, `Panel_*` screens, gameplay behaviours |
| Data model | root | Protobuf-generated messages (`ShopItem`, `AreaData`, `DatabaseMetaData`, …) plus `*_Data` DTOs |

Composition roots:

- **`Lockwood/Hub.cs`** — legacy singleton wiring.
- **`LKWD/SystemsBootstrap.cs`** — modern service registration.
- **`LKWD/Services.cs`** — the service locator. **143** `ServiceReference<T>` properties; this file is the fastest map of what the client can do.

Scene bootstraps: `LKWD/InitialisationSceneBootstrap.cs`, `LKWD/LoginBootstrap.cs`, `LKWD/MainSceneBootstrap.cs`, `LKWD/NewUserBootstrap.cs`.

### A representative slice of `Services`

```
AvakinApi           avatar generation / equipment
LifeClient          SmartFox gameplay client (rooms, actions, interactions)
SmartFoxWrapper     transport-level SFS client
NetworkUDPManager   UDP movement replication
WebServices*        REST + WebSocket (static, not via Services)
Shop / StoreFront   catalogue + purchase
User / UserStats    identity, wallet, entries
Apartment           the loaded area/home instance
TravelManager       moving between areas
InteractionManager  player-to-player interactions
LibChatManager      DMs
GroupManager        group chat
FeedManager         social feed
XPManager           progression
```

---

## 2. Flow control: the state machine

`Services.GameStateManager.Push<T>(args)` drives a stack of states. There are **200** `State_*` classes and **279** `Panel_*` screens.

States are grouped by concern, e.g.:

- Boot/login: `State_Bootup`, `State_InitialiseGame`, `State_Login`, `State_LoginUser`, `State_LoginChoice`, `State_LoginGDPR`, `State_LoginBanned`, `State_LoginMaintenance`
- New user / FTUE: `State_NewUser*` (`LKWD/`), `States/FTUE/State_FTUE*`
- Commerce: `State_Shop*`, `State_Store_Popup`, `State_CurrencyConvert`, `State_Subscription`, `State_EarnCoins`
- Avatar: `State_EditAvakin*`, `State_ItemPicker*`
- World: `State_LoadMainScene`, `State_Travel*`, `State_EditApartment*`

A state typically owns one `Panel_*`, pushes child states, and exits by setting a next-state field.

---

## 3. Configuration

Remote configuration is fetched during login (`auth/1/auth/1/configs`, payload `{configs:true}`) and processed by `LKWD/Configuration.cs` into typed "restricted entries" under `LKWD/ConfigurationClasses/`:

`Servers`, `ChatConfig`, `GroupsConfig`, `Versions`, `CDNLocation`, `SignUp`, `FirebaseConfig`, `LoginBehaviour`, `AvakinGeneratorConfig`, …

Results cache to `configuration_{type}.json` under `LockwoodApplication.SessionDataPath`.

Config drives real behaviour, not just tuning — e.g. `AvakinGeneratorConfig.implementation_version` (or the `avakin_generator_version` key) selects between `AvakinGenerator_V1` and `AvakinGenerator_V2` at runtime (`AvakinApi.Initialize`), and `LoginBehaviour.useSHA` decides whether the client sends a self-integrity hash on login.

---

## 4. Content delivery

`Globals.cs` builds every CDN URL. Roots:

| Constant | Value |
|---|---|
| `CDN_URL_LIVE` | `https://cdn.avakin.com/` |
| `CDN_URL_DEV` | `https://cdn.dev.avakin.com/` |
| UGC (prod / dev) | `https://ugc.prod.avakin.com`, `https://ugc.dev.avakin.com` |
| Media API | `https://media.avakin.life/`, `https://media.dev.avakin.life/` |

Helpers: `ContentDataURL()`, `BaseDataURL()`, `DataURL()`, `ProjectDataURL()`, `HubDataURL()`, `MusicURL()`, `ImageContentURL()`, `ImageThumbnailsURL()`.

A `cdn://` scheme is resolved client-side by `Globals.EvaluateCDNUrl()`: `cdn://content/...` maps to the content root, anything else to the platform asset root.

The item catalogue is a downloaded database: `Globals.ContentDataURL("asset_db/Database{version}/Life{language}.db2")`, loaded by `DatabaseLoader.cs` during login. Login fails hard if it can't open (`"Unable to load DB."`).

> **Changed in 2.24.0.** This wholesale download was replaced by a manifest (`asset_db/{0}/DB4/LifeDB.json`) plus zstd-compressed VCDIFF deltas against a local cache. See [VERSIONS.md §1](VERSIONS.md).

---

## 5. The five network channels

See [NETWORKING.md](NETWORKING.md) for the protocol detail.

```
                    ┌──────────────────────────────┐
                    │        Avakin client         │
                    └──────────────────────────────┘
   REST/HTTPS  ──────┤ LKWD.WebService.WebServices  │──→ api-sni.avkn.co
   WebSocket   ──────┤ WebSocketClient (Envelope)   │──→ friends, DMs, feed
   WebSocket   ──────┤ ChatClient (cmd/* routes)    │──→ group chat
   TCP (SFS)   ──────┤ SmartFoxWrapper / LifeClient │──→ rooms, actions, chat
   UDP         ──────┤ NetworkUDPManager            │──→ movement replication
   TCP (raw)   ──────┤ LKWD.Presence.Client         │──→ presence.avakin.com
```

Channel 1 is further split into **21 logical request channels** (`WebServices.eRequestChannel`: `Primary`, `Avakins`, `Areas`, `Fashion`, `NewsFeed`, `Relations`, `Search`, `UserMail`, `Golem`, `Groups`, `Ugc`, …) so that a stalled subsystem cannot block login traffic.

---

## 6. Notable third-party stack

`BestHTTP` (HTTP/WS + TLS pinning), `Newtonsoft.Json` + `JsonFx` + `SimpleJSON` (three JSON stacks), `Google.Protobuf`, `UniTask` (async), `DOTween`, `Cinemachine`, `AstarPathfindingProject` (navigation), `LiteDB`, `ZString` (allocation-free formatting), `zxing.unity` (QR), Firebase, AppsFlyer, MAX/AppLovin, Tapjoy, Helpshift, Usercentrics (consent), Steamworks.NET.
