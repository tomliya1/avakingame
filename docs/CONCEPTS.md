# Concepts & Vocabulary

**Read this first.** Every other page in `docs/` assumes the words below. Client `2.23.0`.

---

## 1. The shape of the thing, in one paragraph

Avakin Life looks like a game client but behaves much more like a **browser**. The Unity build knows how to render avatars and rooms, how to walk, and how to draw a fixed catalogue of UI widgets. It does **not** know what "Magical Fishing" is, what a strawberry is worth, or what should happen when you press a button in the meadow. All of that lives on the server and is pushed at the client at runtime as *data*: actors to spawn, components to attach to them, UI layouts to build out of JSON, and **callback references** to shout back down when the player does something. That is why a whole seasonal event can ship without a client update — and why a protocol client with no renderer can play most of them. See [MINIGAMES.md](MINIGAMES.md).

## 2. Two servers, one account

| Plane | Host | Carries | Authoritative for |
|---|---|---|---|
| **REST** | `https://api-sni.avkn.co/` | login, profile, wallet, shop, mail, contests, config | your **account** |
| **SmartFox** | `smartfox.avkn.co:9600` / `:9599` (SSL), zone `Life` | rooms, avatars, actions, interactions, chat, **all minigames** | your **presence in a place** |

Three more channels hang off the side — a protobuf WebSocket (friends/DMs/feed), a group-chat WebSocket, and a raw-TCP presence service — but nothing gameplay-critical rides them. Full detail in [NETWORKING.md](NETWORKING.md).

The two planes have **separate credentials with separate lifetimes**, and confusing them is the single most common source of wasted debugging. [SESSIONS.md](SESSIONS.md) is the page that untangles them.

---

## 3. Vocabulary

### Identity and credentials

| Term | What it actually is |
|---|---|
| **Souqa ID** | The canonical numeric user id (e.g. `758325`). Named after a legacy backend. Sent as `X-Avkn-UserID`; resolved from whichever of `user_id` / `souqa_id` / `id` the profile response provides (`SessionData.ProcessProfileUserId`). Every ref, every room user, every ownership check keys off it. |
| **LKWD token** / **login token** | The long-lived *remember-me* credential. A JWE, stored in the OS keychain, replayed as `{"type":"token"}` to get a new session without a password. Survives restarts; this is what "stay signed in" means. |
| **Session token** | A UUID handed back in the `x-avkn-session` response header. Identifies the session server-side. |
| **JWT session** | An RS256 JWT in `x-avkn-jwtsession`, **24 h** TTL. This is what actually authorises REST calls. |
| **`sfstoken`** | A **short-lived (~30 min) ticket for the realtime server only**, minted by `POST auth/1/auth/1/sfstoken` and returned in the `signature` field. It is the password for SmartFox zone login, *and* the key material for per-frame HMAC signing. It is **not** interchangeable with the JWT session. Minting one **kicks any live game client on the same account**. → [SESSIONS.md §4](SESSIONS.md#4-the-sfstoken) |
| **Journey-Seq** | `X-Avkn-Journey-Seq`, a per-request anti-tamper tag derived from an ECDH secret, the server clock and a build-pinned key table. Present on essentially every REST call after login; a wrong one returns `401 invalid request` even though the session is perfectly alive. → [SESSIONS.md §3](SESSIONS.md#3-journey-seq--why-every-later-call-is-signed) |
| **Client token** | `WebServices.GenerateClientToken(id)` — a bespoke MD5-chain derivation over the API secret and server date. Obfuscation, not cryptography. → [LOGIN.md §4](LOGIN.md#4-tokens-and-session-storage) |

### Places

| Term | What it actually is |
|---|---|
| **Scene** | The Unity level: geometry, lighting, nav mesh. `scenePath` identifies one. |
| **Area** | A *place*: an id, an owner, a title, a furniture layout, entry nodes. Public hubs and player apartments are both Areas. Model: `Area.cs`. |
| **Apartment** | The *loaded instance* of an Area in this client, with its own load state machine. Model: `Apartment.cs`. |
| **Instance** / **room index** (`ri`) | A popular Area runs as many parallel copies. `me`/`rl` lists them, `me`/`rr {id, ri}` joins a chosen one, `me`/`rrr` a random one. Note that `me`/`rl`'s `uc` is an **area-wide** user count, not per-instance occupancy — the only reliable occupancy oracle is joining and counting `joinOK.users`. |
| **Node** | A scene attachment point (a seat, a fishing spot). Ownership is arbitrated by the server over the `ne` extension. Contention for nodes is the usual throughput limit on a farming loop. |

### The realtime object model

| Term | What it actually is |
|---|---|
| **Extension** | A named server-side handler on the SmartFox connection. `me` (rooms), `ae` (actions), `ne` (nodes), `se` (state), `inter` (interactions), `chat`, `data`, `men` (moderation). You address one with `SendXt(ext, cmd, payload, "json")`. |
| **NetActor** | A server-owned object in the room. Not a Unity prefab — an id plus a bag of **components**, created by `create_actors`, mutated by `data_actors`, removed by `destroy_actors`. NPCs, collectables, trigger volumes, score HUDs and UI proxies are all NetActors. |
| **Component** | A typed behaviour bolted onto a NetActor, identified by a string (`homebrew_ui_proxy`, `volume_trigger`, `avatar_proxy`, …) via `[NetActorComponent("…")]`. 35 exist. Each exposes a set of named **actions**. |
| **Action** (`LifeAction`) | One server→client instruction, routed to a component's `[NetActionProcessor("…")]` method. Wire shape `{a: "<name>", p: {…}, ref, id, t}`. ~200 exist — full table in [MINIGAMES.md §7](MINIGAMES.md#7-component--action-reference). |
| **Ref** | A server-minted callback address, e.g. `remote://1181155972#n=2006000176_758325_T1787313400010_closeRef`. The server hands you a ref, you notify it back to say "the player pressed the thing". Refs are **per session and per instance** — they can only be read off the wire, never hardcoded. |
| **Notify** | Calling back on a ref. `LifeClient.NotifyRemote(ref, payload)` sends a `nop` LifeAction over `ae`/`pa` and **attaches the avatar's current position** (`NotifyRemoteNoPos` is the variant that does not). |
| **uVar** | A SmartFox user variable. Event progress, quotas and balances are published here — `sv.CottageCore_26_balance`, `sv.max_FlagMaxTokens`, and so on. Reading them is how you tell a rate limit from a bug. |

### Server-driven UI

| Term | What it actually is |
|---|---|
| **Homebrew** | Lockwood's in-house **server-authored UI framework**: the server sends a JSON layout tree, the client instantiates it out of a fixed element library, and every button carries a little response program. 157 classes under `Homebrew/`. Most modern minigame UI is Homebrew. |
| **Panel ref** | `"<bucket_name>#<panel_id>"` — how a Homebrew panel is addressed (`Homebrew.Core.Utils.CreatePanelRef`). |
| **Data bucket** | The key/value store a Homebrew panel binds against. The server `merge`s data into it; bound elements re-render. The panel's visible state *is* the accumulated merges. |
| **Response** | A comma-separated mini-language on a Homebrew element — `set(…)`, `payload(…)`, `if(…)`, `close`, `notify`, … — run client-side when the element fires. Only `notify` reaches the server. 39 verbs; see [MINIGAMES.md §5](MINIGAMES.md#5-homebrew-in-depth). |
| **GLM / Golem** | The server-side scripting service that drives all of the above. You see it as the `glm/…` REST prefix, the `Golem` request channel, the `glm/lkwd/layout/…` CDN paths that hold Homebrew layouts, and `glm`-marked actor ids. |

### Client internals

| Term | What it actually is |
|---|---|
| **`Services`** | The service locator, `LKWD/Services.cs` — 143 singletons. The fastest map of what the client can do. |
| **`State_*` / `Panel_*`** | 200 flow states pushed on a stack by `GameStateManager`, and 279 Unity UI screens. Native UI, as opposed to Homebrew's server-built UI. |
| **Restricted entry** | A per-user or per-project feature gate delivered as config (`LKWD/RestrictedEntries.cs`). "Is the Steam login button visible", "is this event open to you". |
| **Feature versions** | `FeatureVersions.GetDictionary()`, sent on login. Tells the server which client subsystems (including `homebrew`) this build speaks, so it can send a compatible layout. |

---

## 4. Which page answers which question

| You want to know… | Go to |
|---|---|
| What is an `sfstoken`? How does a session get minted? Why is this call 401ing? | [SESSIONS.md](SESSIONS.md) |
| How does the login *flow* work — states, providers, profile load, registration? | [LOGIN.md](LOGIN.md) |
| How do minigames work? What is Homebrew? What can the server push at me? | [MINIGAMES.md](MINIGAMES.md) |
| What are the wire formats and channels? | [NETWORKING.md](NETWORKING.md) |
| Which REST endpoint does X? | [ENDPOINTS.md](ENDPOINTS.md) |
| How is the client itself put together? | [ARCHITECTURE.md](ARCHITECTURE.md) |
| How do avatars / economy / areas / social work? | [GAME_SYSTEMS.md](GAME_SYSTEMS.md) |
| What is reachable without the Unity client at all? | [HEADLESS.md](HEADLESS.md) |
| What changed in 2.24.0? | [VERSIONS.md](VERSIONS.md) |
