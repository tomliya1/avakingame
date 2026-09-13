# Login & Authentication

Client `2.23.0` (`LifeClient_2_23_0`). Primary sources: `Lockwood/LoginHandler.cs`, `LKWD/WebService/WebServices.cs`, `State_Login*.cs`.

---

## 1. Boot sequence

1. **`LKWD/InitialisationSceneBootstrap.cs`** — entry point; pushes `State_Bootup`.
2. **`State_Bootup`** — sets `WebServices.Session.ClientVersion`, pushes `State_InitialiseGame`.
3. **`State_InitialiseGame`** (extends `State_BaseBootup`) — language selection, age-verification check, remote config + config-DB download. Can divert to `State_Maintenance` or `State_BootupError`.
4. Scene transition to **`"LoginNew"`**; `LKWD/LoginBootstrap.cs` pushes `State_Login`.
5. **`State_Login`** runs the login state machine, entering at `Maintenance`.

### `State_Login.LoginData.eLoginState`

```
Idle, AutoLogin, Login, NewUser, NewUserAgeGate, Consent,
Permission, Maintenance, Banned, GDPR, Loaded
```

- **Maintenance** — `State_LoginMaintenance` gates on `WebServices.LoginAvailability` / `RegisterAvailability`. The availability payload (`WebServices.AvailabilityData`) carries `Message`, `BlockUntil`, `ServerTime`, `TimeInMaintenance`, `AppliedJitter`, `ImageURL`, `MaintenanceID` and a `MaintenanceType` of `Login` or `Register` — the jitter staggers reconnects after an outage.
- **Idle** → `State_LoginStart` / `State_LoginWelcome` → `State_LoginChoice` (provider picker; per-platform gating in `LoginChoiceConfig.cs`).
- **AutoLogin / Login** → `State_LoginUser`.
- **NewUser** → `State_NewUser*`, scene `"SignupNew"`, preregistration via `auth/1/auth/1/preregister`.
- **Loaded** → `Services.SceneLoader.TransitionScene("Main")`.

Loading milestones logged by `State_Login.SetLoadingPercentage()`:

```
82  auto login
84  Attempt Login
92  Load Project Restricted Entries
94  Wait For Profile Data
96  Wait For Database Load
97  Load Additional Profile Data
98  Profile List
99  Profile Loaded
100 Account Recover Completed / Failed To Login
```

---

## 2. Identity providers

`LoginHandler.eLoginType` → the `type` field on the wire:

| `eLoginType` | wire `type` | Credential field | Mechanism |
|---|---|---|---|
| `Standard` | `email` | `email_address` + `raw_password` | Email/password |
| `SignInGoogle` | `google` | `access_code` | Play Games auth code |
| `SignInIOS` | `ios` | `access_token` | Game Center |
| `SignInApple` | `apple` | `access_token` | Sign in with Apple |
| `SignInSteam` | `steam` | `session_ticket` | Steamworks session ticket |
| `ValidateToken` | `token` | `token` | Stored LKWD token |
| `LegacyToken` | `token` | `old_token` | Migration from the old token format |
| `CommandLine` | — | — | Config override (`auto_login.user/pass`, `auto_login.token`) |
| `NewUser` | — | — | Registration flow |

Note `WebServices.EncryptPassword()` is **an identity function** — it returns the password unchanged. The password is protected by TLS only; there is no client-side hashing before transport.

---

## 3. The login request

One endpoint handles every provider: **`POST auth/1/auth/1/login`** with `DefaultJsonNoSession | Microservice`, so the effective URL is `https://api-sni.avkn.co/auth/1/auth/1/login`.

```jsonc
{
  "type": "token | email | google | ios | apple | steam",
  "request": { /* the credential field for that type */ },
  "consents": { "<consent-id>": true },   // when GDPR consents are pending
  "sys_info": { ... },                    // DeviceIdentifier.SystemInfoPayload
  "feature_versions": { ... }             // FeatureVersions.GetDictionary()
}
```

Built by `GetAuthPayload()` + `GetAuthRequestElement()`; `AddSystemInfoData()` appends `sys_info` and `feature_versions`.

Login-only headers (`AddLoginOnlyHeaders`): `X-Avkn-TZOffset`, `X-Avkn-Device` (`SystemInfo.deviceModel`), `X-Avkn-Start-Chat`, plus `X-Avkn-Sha` — a self-integrity hash from `LockwoodPackageIntegrity.GetSelfSHA()`, sent **only when remote config `LoginBehaviour.useSHA` is `"TRUE"`**. `X-Avkn-Deeplink` is added when the session started from a deep link.

### Failure semantics — `State_LoginUser.HandleFailedResponse()`

| Status | Handling |
|---|---|
| **423** | Locked. If body `error` contains `"account locked"` **and** a `lock` key is present → `Banned` state. Otherwise falls through, and pending GDPR extra-data is cleared. |
| **451** | → `GDPR` state (re-consent required) |
| **412** | Account does not exist for this social identity. Apple on iOS → `NewUserAgeGate`; Google → clears auth, `GoogleAccountNotFound = true`, "account not created" popup; Steam → back to `Idle`. |

---

## 4. Tokens and session storage

### Long-lived login token

On success, `State_LoginUser.HandleSuccessResponse()` → `LoginHandler.SetLKWDToken()` → `SaveLKWDTokenData()` → `KeychainHandler.SaveTokenData()` (OS keychain; `FSG.iOSKeychain.Keychain` on Apple platforms) under `PlayerPrefKeys.LoginToken`:

```json
{ "data_version": 1, "tokens": { }, "logged_in_username": "guest", "linked_methods": false }
```

`"guest"` is the default username key (`LoginHandler.GuestKey`) for accounts that never linked an identity. The legacy token and `souqa_id` are also mirrored into PlayerPrefs under `PlayerPrefKeys.Login`.

Auto-login order (`HandleAutoLogin`): config overrides → keychain LKWD token (`ValidateToken`) → legacy token → Android backup-permission path.

### Per-session tokens — `LKWD/WebService/Session/SessionData.cs`

- `SessionToken` and `JWTSessionToken` are captured from response headers `x-avkn-session` / `x-avkn-jwtsession` (`WebServices.ExtractSessionToken`, `ProcessHTTPHeader`), and also read from `session_token` in JSON bodies.
- `SouqaID` — the canonical user id, resolved by `ProcessProfileUserId()` from whichever of `user_id`, `souqa_id` or `id` the profile response provides.
- `GameSessionID` — a fresh GUID per process.
- `HelpshiftHMAC` — from the `x-avkn-helpshift` response header.
- Flags `IsDebug`, `Developer` (profile `flags.admin`), `DevServer` come from the profile body.
- `PreSessionData` covers the pre-registration handshake (`PreId`, `PreSession`, `NewAccount`).

### Client token derivation — `LKWD/WebService/SessionToken.cs`

`WebServices.GenerateClientToken(id)` derives a token from `(APIVersion, socialNetworkID, APISecret, ServerTime)`. The algorithm is bespoke:

1. The id is UTF-8 normalised (for `APIVersion >= 10`) and "mangled" by inserting a salt character every 3rd byte.
2. A date string is composed as `DD "76" YYYY "99" MM "86"`.
3. Both are converted to digit strings and repeated to 100 chars; several offsets and rotation counts are derived from trailing digit groups of the id.
4. 50 characters each are sliced from the id digits, an embedded 80-char **salt**, the date string and the **`APISecret`**, then interleaved through a 60-char substitution alphabet.
5. The result is MD5-hashed `2 + (n mod 3)` times, each round appending the previous hex digest.

It is obfuscation rather than cryptography — the salt and secret are both static and present in the binary. *(Values redacted here; see the note in the README.)*

### Renewal

On auth failure `WebServices` raises `eResponseAction.ReSignIn`: session tokens are cleared, `LoginHandler.CreateReLoginRequest()` builds a `type:"token"` login from the stored `LoggedInLKWDToken`, it is inserted at the head of the request channel, and queued `Replayable` requests are replayed behind it. Rate limiting is handled separately (`eResponseAction.RateLimited`) with a delayed replay.

---

## 5. Post-login profile load

`LoginHandler.GetProfileData()` — five requests in parallel via `FutureMonitor.WaitFor`:

| Call | Endpoint |
|---|---|
| `GetUserProfile` | `profile/1/profile/1/get` |
| `GetItems` | `items/1/useritem/1/list` |
| `GetRewards` | `rewards/1/userreward/1/list` |
| `GetXP` | `ws/1/xp/1/get` |
| `GetBalance` | `ws/1/balance/1/get` |

Then, in order: balance merged into user data → `FetchDebugKeys` → **item database load** (`DatabaseLoader.Load`, `Life<lang>.db2` from the CDN — a failure here aborts login with *"Unable to load DB."*) → `DisableSubscriptionItems` → shop new-item flags → `AreaLoader.ValidateAreas` → filter rules → finally a second parallel batch: recommended items, sales data, user entries and user restricted entries.

> **Changed in 2.24.0.** The database step is no longer a full download — it resolves a manifest and applies VCDIFF deltas over a cached copy. See [VERSIONS.md §1](VERSIONS.md).

State then moves to `Loaded` and the client transitions to scene `"Main"`, where it connects to SmartFox zone `"Life"` (see [NETWORKING.md](NETWORKING.md) §2).

---

## 6. Registration

| Endpoint | Role |
|---|---|
| `auth/1/auth/1/preregister` | Allocate a pre-session |
| `auth/1/auth/1/start_registration` | Begin the flow |
| `auth/1/auth/1/register` | Commit the account |
| `auth/1/auth/1/validate-email` | Email validation |
| `glm/1/ftue_registration_version/post/1` | FTUE version (Golem channel; sends `X-Avkn-Presession`) |

The register payload (`GetAuthRegisterPayload`) carries a `username` **signature** rather than a raw name, accepted `consents`, a `config` object holding `outfit` / `avakinbody` / `old` (previous signature), optional `extra_items`, an optional `link` block to attach a login identity to the new account, and the `pre_session` string.

Registration adds `X-Avkn-Locale` (`AddRegisterOnlyHeaders`) on top of the login headers.
