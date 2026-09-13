# Version Diff — 2.23.0 → 2.24.0

## Evidence and its limits

The rest of this repo documents **2.23.0**, where a full decompiled `Assembly-CSharp` was available. The 2.24.0 build examined here is a **raw IL2CPP install** — no `Managed/` directory, no decompiled source.

So this page is built from two things only:

1. `global-metadata.dat` — the identifier table (null-terminated, diffs cleanly) and the string-literal table (extracted with [`tools/dump_metadata_literals.py`](../tools/dump_metadata_literals.py)).
2. `ScriptingAssemblies.json` — the assembly list.

**This shows names that appeared or disappeared. It does not show changed method bodies.** A rewritten algorithm with a stable signature is invisible here. Treat every "unchanged" claim below as "no name-level evidence of change", not proof.

| | 2.23.0 | 2.24.0 |
|---|---|---|
| Bundle version | `2.023.00` | `2.024.00` |
| Steam buildid | — | `24994344` |
| Unity | `6000.0.68f1` | `6000.0.68f1` |
| `GameAssembly.dll` | 126,438,912 B | 129,044,480 B (+2.6 MB) |
| Metadata version | 31 | 31 |
| Build root | `C:\Users\CallumAbele\Perforce\LifeClient_2_23_0\` | `D:\p4\AvakinLife\LifeClient_2_24_0\` |
| Identifiers | 220,366 | 223,408 (+3,271 / −229) |
| String literals | 66,227 | 66,430 |

---

## Assembly-level changes

| | Assembly | Meaning |
|---|---|---|
| **+** | `ZstdSharp.dll` | Zstandard compression (1 → 1,112 identifiers: effectively new) |
| **+** | `Pushwoosh.Core.Runtime.dll` | Managed Pushwoosh SDK |
| **−** | `HSWidgetLibrary.dll` | Helpshift widget library dropped |

---

## 1. Item-database delivery rebuilt — the largest change

2.23.0 downloaded the whole catalogue every time it changed. 2.24.0 replaces that with a manifest plus **VCDIFF binary deltas**, compressed with zstd and cached locally.

CDN paths tell the story directly:

| Version | Path |
|---|---|
| 2.23.0 | `asset_db/Database{0}/Life{1}.db2` |
| 2.24.0 | `asset_db/{0}/DB4/LifeDB.json` — manifest |
| | `asset_db/{0}/DB4/Life{1}.{2}` — full database |
| | `asset_db/{0}/DB4/patches/{1}/Life{2}.vcdiff` — version→version delta |
| | `asset_db/{0}/DB4/patches/Locale/Life{1}.vcdiff` — locale delta |

New types and members: `LKWD|LifeDBManifest`, `LKWD|Database`, `LKWD.Database|DatabaseCacheInfo`, `LKWD.Tech.Utils|VCDiffDecoder`, `ApplyVcdiff`, `GetVcdiffURL`, `GetVcdiffLangURL`, `GetVcdiffLangAppCacheKey`, `LoadCDNManifest`, `GetManifestUrl`, `DownloadDatabaseFromCDN`, `SaveDatabaseToLocalCache`, `LoadDatabaseFromAppCache`, `ClearDatabaseCache`, `DatabaseCacheDir`, `GetCacheInfoPath`, `SendDatabaseToShop`, plus `VCDiffInvalidHeaderException` and `VCDiffSecondaryCompressionException`.

Removed: `LoadDatabase`, `DatabaseLoadCallback`, `DatabaseDownloaded`.

Recovered log strings spell out the fallback chain:

```
DatabaseLoader: LifeDB.json download failed; will attempt local cache then CDN.
DatabaseLoader: Fetching cached base version from local storage: {0}
DatabaseLoader: Asking for AppCache file {0} from AppCache
DatabaseLoader: Failed to get version patch from AppCache {0} -> {1}
DatabaseLoader: Failed to decompress version patch from AppCache {0} -> {1}
DatabaseLoader Failed to patch language diff from AppCache
```

So: fetch `LifeDB.json` → consult local cache → apply a version delta and/or a locale delta → fall back to a full download on any failure.

> **This supersedes** [ARCHITECTURE.md §4](ARCHITECTURE.md) and the database step in [LOGIN.md §5](LOGIN.md), both of which describe the 2.23.0 wholesale `.db2` download.

---

## 2. "For You" — the one new user-facing feature

No trace of this exists in 2.23.0:

```
ForYouManager            ForYouTargeting          IsForYouItem
ForYouItemPickerCategory ForYouTargetingConfig    ShowForYou
ForYouSidePanel          ForYouItems              CategoryIDForYou
```

A personalised item category, server-targeted (`ForYouTargetingConfig` implies remote config). The item-picker category family grows 17 → 18, `ForYouItemPickerCategory` being the sole addition:

```
AllTag, Brand, Category, Folder, ForYou*, ItemIds, MissingTagType, Multi,
MultiTag, RecentPurchase, Sale, Search, SubCategory, Tag, Type,
UgcAvacraft, WishList
```

It ships with **no new screens** — see §5.

---

## 3. Store, push and support

**IAP store restructured** — `LKWD.IAP|IAPCategory`, `LKWD.IAP|IAPCategoryConfig`, `LKWD.UI|IAPCategoryList`, `CategoryToShow`, `CategoryRootName`, `CategoryConfig`, `UserRetailShopIapStoreInteraction`.

**Pushwoosh promoted, not introduced.** 2.23.0 already had integration code (`InitPushwoosh`, `PushwooshNotificator`, `PushwooshId`, …). 2.24.0 adds the managed SDK assembly itself plus `PushwooshJSON` and `PushwooshSettings`. Local-notification helpers were trimmed: `ClearLocalNotification`, `ClearLocalNotifications`, `GetPushHistory`, `ClearPushHistory` all removed.

**Helpshift reworked** — `HSWidgetLibrary.dll`, `HelpshiftConfig`, `HelpshiftHandlerWidget`, `IsGDPRAvailable`, `GdprSuccessHandler`/`GdprErrorHandler`, `ConversationPrefillText`, `InitialUserMessage` removed. Added: `IHelpshiftUserLoginEventListener`, `USER_SESSION_EXPIRED`, `AGENT_MESSAGE_RECEIVED`, `APP_ATTRIBUTES_*` validation/sync errors, `DATA_MESSAGE_TYPE_APP_REVIEW_REQUEST`, `DATA_MESSAGE_TYPE_SCREENSHOT_REQUEST`.

**Resource handlers unified** — `LKWD.Data.Resources.V1`, `.V1.Handlers`, `.V2`, `.V2.Handlers` collapse into a single `LKWD.Data.Resources.Handlers`.

---

## 4. Content and taxonomy

New item-picker tags: `OccasionsandeventsClubwear`, `OccasionsandeventsNightwear`, `FashiontypesSocksandhosiery`, `PetkinpersonalityCute`, `RoomtypeDiningroom`.

Two are corrections rather than additions — `Dinningroom` → `Diningroom`, `Socks` → `Socksandhosiery`.

Dance selection gained cost awareness: `GetSuggestedDanceByCost`, `higherCostingDances`, `maxItemCosts`, `refreshDanceItemPickerSetSelected`.

---

## 5. What did **not** change

- **REST API surface — 141 endpoints, identical.** Verified by extracting the string-literal table from both builds; no additions, no removals. The full `http(s)://` host list is byte-identical too.
- **UI inventory** — 234 `State_` and 284 `Panel_` types in both. "For You" reuses existing screens.
- **Realtime protocol** — no name-level change to SmartFox zone/extension names, UDP opcodes, or `Envelope` payload cases.

### Caveat on that last point

Absence of name changes is weak evidence for protocol stability. Endpoint *paths* being identical does not mean request payloads, headers or response shapes are identical — those live in method bodies this method cannot see. Confirming protocol parity needs a real 2.24.0 dump (Il2CppDumper + decompiler) or a runtime hook on `WebServices.CreateRequest`.

---

## Reproducing this

```bash
python3 tools/dump_metadata_literals.py <2.23>/global-metadata.dat -o lit23.txt
python3 tools/dump_metadata_literals.py <2.24>/global-metadata.dat -o lit24.txt
comm -13 <(sort -u lit23.txt) <(sort -u lit24.txt)   # added literals

# endpoints in either build
grep -aE '^[a-z][a-zA-Z0-9_-]*/[0-9]+/[a-zA-Z0-9_/{}.?=&-]+$' lit24.txt | sort -u

# identifiers (null-terminated region, so plain strings works)
strings -a -n 4 <metadata> | grep -aE '^[A-Za-z_][A-Za-z0-9_.<>`|-]{2,59}$' | sort -u
```
