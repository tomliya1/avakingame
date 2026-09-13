# Game Systems

A class-level map of what the client actually simulates. Client `2.23.0`.

---

## 1. Avatar ("Avakin")

The avatar is a **generated** mesh, not a fixed rig. `AvakinApi` (`Lockwood/Avakin/AvakinApi.cs`) owns generation and picks an implementation at runtime:

```
AvakinGeneratorConfig.implementation_version   (or config key avakin_generator_version)
  1 → AvakinGenerator_V1
  2 → AvakinGenerator_V2
  else → warn, default to V1
```

Supporting pieces: `AvakinController` (per-instance), `AvakinSettings`, `AvakinEffectSetting`, `AvakinTextureStreamSystem` (streamed textures), `AvakinExpressionDecompressTask`, `AvakinRuleValidator`, `EquipmentManager`, `AvakinGeneratorPerformanceAnalyzer`.

### `AvakinConfig` — the outfit/body document

`Lockwood/AvakinConfig.cs` wraps an `AvakinConfigJson` and is the unit of "what this avatar looks like":

- Identity: `Id`, `Name`, `Gender` / `IsFemale` / `ShopGender`, `Tags`
- Slots: `TryGetDetails(slot)`, `SetId(slot, id)`, `GetColour(slot)`, `RevertToDefault(slot)`, `RevertToOtherItem(...)`
- Morphs: `GetMorphingValues()` — body shaping
- Animations: `TryGetAnimation(slot)`, `GetAnimations()`
- Outfits: `ApplyOutfit(BaseConfig)`, `ApplyOutfitExclusions(...)` (items that hide other items), `DoesOutfitMatch(OutfitConfig)`
- Serialization: `CreateJsonAvakin(requiredFieldsOnly, hiddenItems)`
- Visibility: `VisibilityState` state machine, `GetReadyForOutfitPhoto()` for portrait capture
- Change tracking: `HasChanged(config)`, `Clone()`, `RequiresCleaning`

Editing UI: `EditableAvakin.cs`, `State_EditAvakin*`, `State_ItemPicker*`. Portraits are taken automatically by `AutoPortraitTaker`.

---

## 2. Economy

### Currencies — `LKWD/Wallet.cs`

`Wallet` extends `ValueTracker<int>`, so every balance is observable.

| Key | Accessor |
|---|---|
| `coins` | `Coins` — soft currency |
| `gems` | `Gems` |
| `crowns` | `Crowns` — premium |
| `bmachine_normal` | `NormalBoostTokens` |
| `bmachine_super` | `SuperBoostTokens` |
| `AgeVerificationVoucher` | `AgeVerificationTokens` |
| `craft_coins`, `craft_coins_pending` | crafting |

Each currency has a data-driven `CurrencyDefinition` (icons at three sizes, localisation key, primary/secondary/icon colours, display string, whether it appears on the award screen), deserialised from remote config. `Balance` is a read-only façade over a `Wallet`.

`ShopItem.Types.eCostType` — `Free, Coins, Gems, Crowns` — maps to wallet keys via `Wallet.GetShopCostTypeValue()`.

### Catalogue — `ShopItem.cs` (3,417 lines, protobuf-generated)

Item taxonomy is tag-based. `eTagType`:

```
LEGACY, FEATURE, BRANDS, TYPE, SUBTYPE, PRIMARYCOLOUR, OTHERCOLOURS,
MATERIAL, PATTERN, STYLE, ROOM, SUBCULTURE, SHOPTYPE, SHOPSUBTYPE
```

Also `eGender { FEMALE, MALE, NONE, ANY }`, `eFurnitureFeature { Surface, Floor, Wall }` (where furniture can be placed), and `Giftable { Enabled, Disabled, LevelLocked, UserNotAllowed, MailDisabled }`.

The catalogue is **not** fetched per request — it is a database file downloaded from the CDN (`asset_db/Database{version}/Life{language}.db2`) and opened locally by `DatabaseLoader`. Only ownership, pricing overrides and recommendations come from the API.

### Purchase paths

| Path | Endpoints |
|---|---|
| In-game item purchase | `shop/1/itemshop/1/purchase` |
| Coin packs (IAP) | `coinpacks/1/coinpack/1/list`, `buy` |
| Steam IAP | `steam/1/steam/1/init_tran`, `generate_refund_token` |
| Subscriptions | `subscriptions/1/subscriptions/1/*` |
| Currency conversion | `ws/1/balanceconverter/1/fulfill` (`State_CurrencyConvert`) |
| Physical merch | `nativeecom/1/nativeecom/1/proxy/` |
| Affiliate shop | `swagse/shop/{search,click,purchase}/v2` |

Services: `Shop`, `StoreFront`, `WishListManager`, `FavouritesManager`, `IAPSubscription`, `NativeECom`.

---

## 3. Progression

**XP / levels** — `LKWD/XpTracker.cs`. Multiple independent XP tracks keyed by string; each has a `LevelTable` of `LevelData { Level, XpRequired }` delivered as config. `UpdateXp()`, `GetXp(key)`, `GetLevel(key)`, and per-key listeners for XP and level changes. Fetched at login via `ws/1/xp/1/get`; rewards via `rewards/1/rewards/1/xprewards`.

**Daily tasks** — `dailytasks/1/dailytasks/1/{list,update,claim,cancel}`, `TaskManager`, `State_DailyTaskRewards`.
**Daily bonus** — `rewards/1/dailybonus/1/list/{0}`, `claim/{0}`.
**Challenges** — `Lockwood/Challenge.cs`, `ChallengeManager`, `ChallengeTier`, `ChallengeFriend`, `ChallengeReward`; completion via `rewards/1/userchallenge/1/completed`.
**Badges** — `Lockwood/BadgesManager.cs`, `BadgeClaimData`.
**Reward wheel / spin** — `RewardWheelManager`, `games/1/sw/1/get|claim`.
**Mystery box** — `games/1/mbox/16/odds`, `play?currency={0}` (published odds).
**Build machine (crafting)** — `ws/1/bmachine/2/{list,build,buy,boost,cancel,complete}`, `BuildMachineManager`, boosted with `bmachine_normal` / `bmachine_super` tokens.

---

## 4. Areas, apartments and travel

An **Area** is a place; an **Apartment** is the loaded instance of one.

### `Area.cs`

`areaId`, `ownerId`, `title`, `rating`, `userCount`, `visits`, `age`, `lastUpdated`, `furnitureList`, plus `headerDict` / `layoutDict` (header metadata vs furniture layout, saved separately) and `EntryNodes`.

`EntryNodeData` — spawn points: `roomId`, `weight` (spawn weighting), `pos`, `scl`, `rot`, optional `camPos`.

### `Apartment.cs`

Load state machine:

```
UnInitialized → LoadingApartment → ProcessingApartment
→ LoadingApartmentSettings → LoadingApartmentAdditional
→ LoadingFurniture → Idle → Unloading
```

Exposes `AreaId`, `SouqaId` (owner), `RoomIndex`, `IsPublicScene`, `HasWaterZone`, welcome message, zone data (`GetZoneData` / `SetZoneData` / `ClearZoneData`), paintable surfaces, per-tag item counts, LOD management and lighting reload. Events: `OnSFSEntryFailure`, `OnFinishedLoading`, `OnSceneUnloadedEvent`.

### Persistence

`ws/1/area/1/save` — `WebServices.AreaSave()` distinguishes **create**, **header-only** and **layout-only** saves. Reads: `ws/1/area/1/get`, `list`, and `AreaFriendList(userIDs)`.

Ratings are a separate service: `ws/1/area/1/rate` — `SetRating(instanceID, rating)`, `GetOwnRating`, `GetRating(params int[])`, `ClearRatings` (`ApartmentRatingService`, `ApartmentRating`, `ApartmentReward`).

Travel: `TravelManager`, `TravelHistory`, `State_Travel*`, `AreaGating`, `AreaLoader.ValidateAreas()` at login. Joining is a SmartFox operation (`me`/`rr`,`rf`,`ri`,`rrr`) — see [NETWORKING.md](NETWORKING.md) §2.

---

## 5. Realtime behaviour in a room

**Nodes** (`ne` extension, `NodeManager`, `NetActorNodeMap`, `RewardNodeManager`) — scene attachment points such as seats. A client requests a node (`na`), optionally releasing others, and the server arbitrates ownership.

**Actions** (`ae` extension, `ActionController`, `ActionSequence`, `ActionSequencePlayer`, `ActionRuleSet`, `AnimationSyncAction`) — queued, parallel and stop-all animation posting, for both the player and scene actors. Synchronised actions use an explicit **master/slave** split (`msa` vs `ssa`) plus broadcast (`bsd`).

**Interactions** (`inter` extension, `InteractionManager`, `InteractionSyncManager`, `ContextInteractionManager`, `InteractionHighlightSystem`) — offer/accept player-to-player interactions. Flow: `inGD` fetch definitions → `inCr` create offer → `inRp` respond → `inRv` revoke. Callbacks carry `eInteractionCallbackResult`, `eInteractionResponse`, `eInteractionResponseReason`.

**Movement** (`MovementSystem/Movement.cs`, `NetworkUDPManager`) — UDP where the scene supports it, SmartFox TCP otherwise.

**Chat and reactions** (`chat` extension) — history (`ch`), groups (`chg`), reactions (`chat_mod`).

---

## 6. Social

| System | Where |
|---|---|
| Friends graph | `Lockwood/FriendsManager.cs`, `Friend.cs`; Pipeline WebSocket (`FriendList`, `Friend`, `FriendState`, `Relation`, `SocialGraph`); REST `relations/1/relations/1/{0}` |
| Presence | `LKWD/Presence/Client.cs` — see [NETWORKING.md](NETWORKING.md) §5 |
| Feed | `Lockwood/FeedManager.cs`, `FeedItem`, `FeedComments`; Pipeline `Feed*` models; 14-day cache expiry |
| Groups | `LKWD/Groups/` — `GroupManager`, `GroupData`, `GroupMember`, `GroupInvite`, `GroupDeeplink`, moderation via `GroupChatAdmin` |
| Clans | `gateway/1/gateway/1/clan-service*` |
| DMs | `LKWD/LibChat/` |
| Mail | `usermail/{0}/usermail/2/{1}`, `LKWD/Usermail/` |
| Friend codes | `ext/1/friendcodes/1/get|resolve|branch-read` |
| Reporting | `ext/1/playerreporting/1/report|check`, `LKWD/UserReporting/` |
| Same-network detection | `ext/1/samenetwork/1/status|remove` (alt-account / shared-device signal) |
| Search | `search/1/search/1/search` |

---

## 7. Competition

**Contests** — `LKWD/Contests/`: `Contest`, `ContestEntry`, `ContestGroup`, `ContestPrerequisite`, `ContestPrizeData`, `ContestReward`, `Leaderboard`, `eContestLevel`, `eContestTypes`. 13 REST actions under `games/1/contest/1/` covering entry, contestant listing, voting (`submit-votes`, `votes-progress`), leaderboards, "star power" and results.

**Fashion** — `FashionManager`, `FashionLeaderboardService`.

---

## 8. UGC (user-generated content)

`Ugc/` — `UgcAvatar`, `UgcItemController`, `UgcOutfitController`, `UgcTemplateController`, `UgcItemStorage`, `Marketplace/`, `Thumbnail/`, `Dynamic/`.

Templates come from Golem (`glm/1/ugc_templates/1`); assets live on the UGC CDN (`ugc.prod.avakin.com`); uploads are ticketed through `imageapi/v1/requestupload/`. Marketplace UI is driven by `UgcMarketplaceController`.

---

## 9. Pets

`ws/1/avapet/1/{get,save,touch}`, `PetkinApi`, plus a dedicated `Petkins` request channel.

---

## 10. Monetisation & compliance surrounds

**Ads** — `Adverts/`, `AdvertManager`, `AdvertRateLimit` (`ext/1/ads/1/rate_limits/2`), `ws/1/adshint/1/hint`; mediation via MAX/AppLovin, Tapjoy, Fyber, Ayet, Audiomob, Gadsme, OfferWallEdge. `EarnCoinsManager` / `State_EarnCoins` converts ad views and account-linking into currency.

**Consent & privacy** — `consent/1/consent/1/*`, `ConsentHandler`, `GDPRDataHandler`, Usercentrics (`UsercentricsHelper`), data portal `auth/1/auth/1/dataportal`.

**Age verification** — `ageverification/1/ageverification/1/{start_flow,estimate,verification_status}`, Yoti integration, face capture (`AgeVerificationFaceCapture`), `AgeVerification*Section` UI, `eAgeRestrictionTier { Everyone, Adult }`, consumed with `AgeVerificationVoucher` tokens.

**Moderation** — `messagefilter/1/messagefilter/1/check`, `filter/1/rules/1/list`, profanity filtering in `Lockwood/`, SmartFox `men` extension, `RequestKickUser` (`me`/`rk`).

**Telemetry** — `LKWD/Metrics/`, `MetricsManager.Create<T>().Send()`, `TelemetrySystem.Timeline`, `userjourney/1/userjourney/1/submit`, `warehouse-receiver/1/warehouse/1/`, Firebase, AppsFlyer, plus client log upload (`logreceiver/1/clientlogs/1/manifest`).

---

## 11. Access control primitives

Two related config-driven mechanisms gate features:

- **Restricted entries** (`LKWD/RestrictedEntries.cs`, `auth/1/entry/1/restricted/get`, `ws/1/userentry/1/user/get|set`) — per-project and per-user feature gates. `LoginChoiceConfig` uses one to decide whether the Steam login button appears.
- **Global entries** (`entry/1/entry/1/global`, `global/lite`) — global switches.

`AreaGating` applies the same idea to places.
