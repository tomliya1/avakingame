# Sessions, Tokens & Tickets

**How a session gets minted, what each credential is for, and how long it lives.**

[LOGIN.md](LOGIN.md) describes the login *flow* — the states, the identity providers, the profile load. This page describes the *credentials*: what goes over the wire, in what order, and which one is to blame when something 401s. Client `2.23.0`. Sources: `LKWD/WebService/WebServices.cs`, `SessionData.cs`, `PerfMetrics.cs`, `PackageHelper.cs`, `Smartfox/SmartFoxConnection.cs`.

---

## 1. Four credentials, one account

Avakin does not have "a session". It has four things with four different lifetimes, and they are minted in a chain:

```
  email + password            ── typed once, ideally never again
        │
        ▼
  login_token (JWE)           ── remember-me. Long-lived, opaque, keychain.
        │                        Replays as {"type":"token"} to mint ↓
        ▼
  session   (UUID)      ┐
  jwt_session (RS256)   ├──── the HTTP session.  TTL 24 h.
  shared_key (ECDH)     ┘     Authorises every REST call.
        │
        ▼
  sfstoken (JWT)              ── a ticket for the realtime server only.
                                 TTL ~30 min.  One per account.
```

| # | Credential | Carried as | TTL | Authorises |
|---|---|---|---|---|
| 1 | `login_token` | login body `{"type":"token","request":{"token": … }}` | long (opaque JWE) | minting a new #2 without a password |
| 2 | session UUID | `X-Avkn-Session` | 24 h | — (identifies the session) |
| 2 | JWT session | `X-Avkn-JWTSession` | **86 400 s exactly** | every REST call |
| 2 | ECDH shared secret | never sent; derived | session | signing `X-Avkn-Journey-Seq` |
| 3 | `sfstoken` | SmartFox zone-login password | **~30 min** | joining rooms; signing SFS frames |

TTLs for #2 and #3 are **measured**, not compiled in — nothing in the client declares them.

> **The rule that saves the most time:** an expired JWT and a malformed Journey-Seq both look like `401`. A `401` on a call that worked five minutes ago is usually the *signature*, not the session. §3 and §7.

---

## 2. Minting the HTTP session

This is what "logging in" actually does on the wire. In the client the chain is `State_Login` → `State_LoginUser` → `LoginHandler`.

```
 client                                                api-sni.avkn.co
   │
   │  1. GET  consent/1/consent/1/check                         │
   │◀─────────── required consent ids ───────────────────────────
   │
   │  2. generate secp256r1 keypair                              │
   │     X-Avkn-Start-Chat: b58(pubkey ‖ serverTime_LE)          │
   │
   │  3. POST auth/1/auth/1/login                                │
   │     { type, request:{…}, consents, sys_info,                │
   │       feature_versions }          ← DefaultJsonNoSession    │
   │─────────────────────────────────────────────────────────────▶
   │                                                             │
   │◀── 200 ─────────────────────────────────────────────────────
   │     headers: x-avkn-session        (UUID)                   │
   │              x-avkn-jwtsession     (RS256 JWT, 24 h)        │
   │              x-avkn-chat-tag       (server ECDH pubkey)     │
   │              x-avkn-server-time                             │
   │              x-avkn-helpshift      (HMAC for support)       │
   │     body:    user_id / souqa_id, flags, login_token         │
   │
   │  4. ECDH(client_priv, server_pub) → shared secret           │
   │     PerfMetrics is now IsReady; all later requests signed    │
   │
   │  5. five parallel profile calls, then the item database      │
```

**Step 3's `type` field selects the identity provider** — `email`, `google`, `ios`, `apple`, `steam`, or `token` for a stored `login_token`. One endpoint, six providers; the credential field changes, nothing else does. Table in [LOGIN.md §2](LOGIN.md#2-identity-providers).

**Step 4 is the part that is easy to miss.** The `X-Avkn-Start-Chat` / `x-avkn-chat-tag` exchange is a plain ECDH handshake (`PerfMetrics.GetTag` / `PerfMetrics.Update`, curve `secp256r1`, base58-encoded). Nothing about it says "auth", and it is not needed for the login call itself — but without the resulting shared secret the client cannot sign anything afterwards, and every subsequent call fails. `PerfMetrics.IsReady` requires all three of: a user id, a received server time, and a completed agreement.

**Step 5** — `GetUserProfile`, `GetItems`, `GetRewards`, `GetXP`, `GetBalance` in parallel, then `Life<lang>.db2` from the CDN. A database failure aborts login outright. Detail in [LOGIN.md §5](LOGIN.md#5-post-login-profile-load).

### What persists afterwards

| Value | Where the client keeps it |
|---|---|
| `login_token` | OS keychain (`KeychainHandler.SaveTokenData`, key `PlayerPrefKeys.LoginToken`) |
| legacy token, `souqa_id` | PlayerPrefs, mirrored |
| session + JWT | memory only (`SessionData`) — re-minted every launch |
| `GameSessionID` | a fresh GUID per process |

---

## 3. Journey-Seq — why every later call is signed

`LKWDHTTPRequest.Prepare()` stamps **`X-Avkn-Journey-Seq`** onto every outgoing request that does not already carry one. It is built by `PerfMetrics.GetJourneyTag()`:

```
package  = "<souqa_id>.<serverTime>.<PackageHelper.GetDataBundle(serverTime)>"
tag      = b58( encrypt( ascii(package), key = ECDH shared secret ) )
```

So the tag proves three things at once: who you are, that your clock agrees with the server's, and that you hold the shared secret from the login handshake.

### The data bundle — `LKWD/WebService/PackageHelper.cs`

`GetDataBundle(epoch)` is the interesting half, because it is pinned to the exact build:

```csharp
int day  = epoch / 86400;              // Lehmer seed
int dp   = epoch % 86400 / 5400 % 16;  // 90-minute slot → which hash variant

Lehmer prng; prng.Seed(day);
int idx = prng.Next() % 28;
ulong[] data = new ulong[4];
for (int i = 0; i < 4; i++) {
    idx = (idx + prng.Next() + 28 - i) % 28;
    data[i] = LifeClient.sk(idx);      // ← 28 build-specific constants
}
return ComputeHash(dp, data, day);     // 17 variants, selected by dp
```

`LifeClient.sk(0..27)` gathers 28 `uint`s scattered one per class across the assembly (`ActorController.sk()`, `PetkinManager.sk()`, …) and **refuses to run if `BuildData.BuildVersion` does not match the version the table was generated for** — in 2.23.0 it throws *"The secrets embedded in this client … do not match the version number of the build."* The table is regenerated every build.

Three consequences worth internalising:

1. **The tag rotates on a 90-minute UTC boundary** (`5400 s`, 16 slots per day) and on a daily one. An off-by-one slot is a silent, total failure.
2. **The key table is version-locked.** After a client update, a reimplementation carrying the old table signs valid-looking garbage. Observed exactly: same account, same minute, `sfstoken` returned **200** under the 2.023.00 table and **401 `invalid request`** under the 2.022.00 one, while unauthenticated `login` on the same host kept working.
3. **The failure mode is indistinguishable from an expired session** unless you know to look. See §7.

*(The 28 values are client-embedded signing material and stay redacted here, in line with the rest of these notes. They are recoverable from any decompiled `Assembly-CSharp` by following `LifeClient.sk`'s switch to the 28 one-line `sk()` methods it calls — but they are only valid for the exact build they were generated for.)*

---

## 4. The `sfstoken`

**What it is.** A short-lived JWT that is the password for the realtime server, and nothing else.

**How it is minted.**

```
POST auth/1/auth/1/sfstoken          (no body)
     eWebRequestType.DefaultJson | Microservice   → i.e. RequiresSession
     → 200 { "signature": "<JWT>" , … }
```

`WebServices.GetSFSLoginToken()` is one line (`WebServices.cs:4976`). Because the flags include `RequiresSession`, it is a *signed* call — it needs a live HTTP session **and** a correct Journey-Seq. That is why "SmartFox won't connect" is so often really "your REST signing is wrong".

**How it is used.** `SmartFoxConnection.Connect()` requests it, `OnLoginToken` pulls the `signature` field into `m_LoginToken`, then:

```csharp
Services.SmartFoxWrapper.LoginToZone(
    zone: "Life",
    user: Services.User.SouqaID,
    pass: m_LoginToken,                       // ← the sfstoken IS the password
    extra: { mduid, comp, version });
```

and **the same string is reused as HMAC key material** for per-frame signing (§5). So it is simultaneously a bearer ticket and a signing key.

**What it costs you.**

| Property | Value |
|---|---|
| TTL | ~30 minutes (measured) |
| Audience | `smartfox` |
| Concurrency | **one live SmartFox session per account** — minting one and connecting **kicks whatever client is already in a room** |
| Needed for HTTP? | No. Shop, wallet, mail, contests, fashion voting all run on the session JWT alone. |

The practical rule: **do not mint an `sfstoken` unless you are about to open a socket.** Every "the REST login kicked my game" report has turned out to be an unnecessary `sfstoken` mint.

---

## 5. Signing SmartFox frames

Having the ticket is not the end of it. Shortly after connect the server may send an **auth challenge** on the extension channel:

```json
{"b":{"r":-1,"o":{"a":5,"r":"chal","b":7,"o":"X"}},"t":"xt"}
```

`SmartFoxConnection.OnAC` reads `a`, `b` and the op `o`, and — for the only defined op, `eAuthChallengeOp.X` — arms the signer:

```
key   = <sfstoken> + str( sk(a) ^ sk(b) )         # sk() again, same 28-entry table
ack   = "I\0"                                      # unsigned; this arms verification
frame = <msg>\0  then  "H" + lowercase_hex( HMAC_MD5( BE64(seq) ‖ utf8(msg) ) ) + "\0"
seq   = 0 at connect, incremented per *signed* frame only
```

`a` and `b` are re-rolled per connection, so this cannot be precomputed. Two behaviours matter:

- **Acking is a commitment.** Once you send the ack, unsigned frames are dropped **in silence** — no error, no disconnect, just a socket that stops answering. Measured: after acking, a signed frame gets a room list back and an unsigned one gets nothing.
- **Not acking is legal.** A client that never acks is never put into verifying mode. That is a valid way to run if you cannot sign.

---

## 6. Renewal and expiry

**REST.** On an auth failure `WebServices` raises `eResponseAction.ReSignIn`: session tokens are cleared, `LoginHandler.CreateReLoginRequest()` builds a `{"type":"token"}` login from the stored `login_token`, that request is inserted at the **head** of the channel, and anything queued as `Replayable` is replayed behind it. Rate limiting is a separate action (`RateLimited`) with a delayed replay. The user sees nothing.

**SmartFox.** There is no refresh. When the ticket or the connection dies you mint a new `sfstoken` and log into the zone again — which is also what re-kicks any other client on the account.

**What invalidates what**

| Event | `login_token` | session + JWT | `sfstoken` |
|---|---|---|---|
| App restart | survives (keychain) | re-minted | re-minted |
| 24 h elapsed | survives | expired → re-login | long gone |
| Password change | invalidated | invalidated | invalidated |
| New `sfstoken` minted elsewhere | — | — | **your socket is kicked** |
| Client version bump | survives | survives | needs a rebuilt `sk` table to mint at all |

---

## 7. Failure signatures

| Symptom | Actual cause | Do **not** read it as |
|---|---|---|
| `login` 200, but **every** signed call 401 `invalid request` | Journey-Seq wrong — stale `sk` table, wrong 90-min slot, or clock drift | "session evicted", "IP blocked" |
| `sfstoken` 401 while `login` on the same host succeeds | same as above — `sfstoken` is `RequiresSession`, `login` is not | "SmartFox is down" |
| First call after several hours 401s, later calls fine after re-login | JWT genuinely expired | keep retrying with the dead session |
| Login 412 `authentication failed` | wrong credential shape, or a stale password file | "server down" |
| Login 412 on a social provider | **no account exists** for that identity (Apple→age gate, Google→"not created", Steam→back to idle) | "bad password" |
| Login 423 with a `lock` key in the body | banned | rate limit |
| Login 451 | GDPR re-consent required | ban |
| Your game client gets kicked out of a room | you minted an `sfstoken` | "the REST login did it" |
| SFS connects, frames sent, server silent | you acked the challenge and are sending unsigned frames | "wrong room", "bad payload" |

---

## 8. Where this lives in the client

| Concern | Class / file |
|---|---|
| Login chain | `Lockwood/LoginHandler.cs`, `States/Login/State_LoginUser.cs` |
| Request framing, channels, re-auth | `LKWD/WebService/WebServices.cs` |
| Session state | `LKWD/WebService/Session/SessionData.cs` |
| ECDH handshake + Journey-Seq | `LKWD/WebService/PerfMetrics.cs` |
| The data bundle | `LKWD/WebService/PackageHelper.cs` |
| Build-pinned key table | `LifeClient.sk(int)` |
| Header stamping | `LKWD/WebService/LKWDHTTPRequest.cs` |
| SFS ticket, zone login, frame HMAC | `Smartfox/SmartFoxConnection.cs` |
