# avakingame — How Avakin Life Works

Technical notes on the PC (Steam / CrossOver) client of **Avakin Life**, derived from the decompiled IL2CPP client **`2.23.0`** (build branch `LifeClient_2_23_0`).

It covers how the game boots, how login and session renewal work, the five network channels it speaks, the full REST surface, the realtime room protocol, how the major gameplay systems fit together — and how the server builds entire minigames out of a client that contains none of them.

> **Disclaimer.** Derived from reverse-engineering a commercial game for educational and interoperability research. This repository contains **no game assets, no decompiled sources, no client-embedded secrets and no tooling** — it is documentation. Nothing here is endorsed by or affiliated with Lockwood Publishing.

---

## Start here

New to this? Read in this order:

1. **[CONCEPTS.md](docs/CONCEPTS.md)** — the mental model and the vocabulary. What a souqa id, an `sfstoken`, a NetActor, a ref and a Homebrew bucket actually are. Everything else assumes these words.
2. **[SESSIONS.md](docs/SESSIONS.md)** — the credential chain end to end: how a session gets minted, why every later call is signed, and what each `401` really means.
3. **[MINIGAMES.md](docs/MINIGAMES.md)** — how the server runs a game inside a client that has never heard of it.

## All documents

| Document | What's in it |
|---|---|
| **[CONCEPTS.md](docs/CONCEPTS.md)** | Mental model, glossary, and which page answers which question |
| **[SESSIONS.md](docs/SESSIONS.md)** | Credentials, token lifetimes, request signing, the SmartFox ticket, failure signatures |
| **[MINIGAMES.md](docs/MINIGAMES.md)** | NetActors, Homebrew server-driven UI, refs, and the 35 components / 212 actions the server can drive |
| **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** | Client layering, composition roots, state machine, the five network channels |
| **[LOGIN.md](docs/LOGIN.md)** | Boot sequence, identity providers, token storage, profile load, registration |
| **[NETWORKING.md](docs/NETWORKING.md)** | REST, SmartFox, UDP wire format, chat, presence, friend-graph WebSocket |
| **[ENDPOINTS.md](docs/ENDPOINTS.md)** | All 141 REST endpoints, grouped by service (identical in 2.23.0 and 2.24.0) |
| **[GAME_SYSTEMS.md](docs/GAME_SYSTEMS.md)** | Avatar, economy, inventory, apartments/areas, social, progression, UGC |
| **[HEADLESS.md](docs/HEADLESS.md)** | Which parts of the game are protocol and which are genuinely Unity |
| **[MODS.md](docs/MODS.md)** | The MelonLoader mod projects, and how they hook the client |
| **[VERSIONS.md](docs/VERSIONS.md)** | What changed in **2.24.0** vs 2.23.0 |
| **[tools/](tools/)** | `dump_metadata_literals.py` — recover string literals from IL2CPP metadata |

---

## TL;DR — the shape of the client

Avakin Life is a Unity **IL2CPP** game with a very consistent managed structure:

- **`State_*`** (200 classes) — flow states driven by `Services.GameStateManager.Push<T>()`
- **`Panel_*`** (279 classes) — Unity UI screens
- **`Lockwood/`** — the older core library: avatars, friends, XP, login, SmartFox wrapper
- **`LKWD/`** — the modern services layer: `WebServices`, wallet, IAP, chat, groups, contests
- **`LKWD/Services.cs`** — a service locator exposing **143** singletons (`Services.Shop`, `Services.LifeClient`, …)
- **`Homebrew/`** — 157 classes implementing a server-authored UI framework

Composition roots: `Lockwood/Hub.cs` and `LKWD/SystemsBootstrap.cs`.

### The five network channels

| # | Channel | Transport | Purpose |
|---|---|---|---|
| 1 | REST API | HTTPS via BestHTTP → `https://api-sni.avkn.co/` | Auth, profile, economy, config — everything non-realtime (**141 endpoints**) |
| 2 | SmartFoxServer 1.x | TCP **9600**, SSL **9599**, zone `"Life"` | Rooms, authority, in-room chat, actions, interactions, **all minigames** |
| 3 | AvakinUdpLib | UDP, host:port handed out over SmartFox | High-frequency avatar movement replication (HMAC-SHA256 signed) |
| 4 | Pipeline WebSocket | Protobuf `Envelope` | Friends graph, DMs (LibChat), feed, presence, social events |
| 5 | Presence service | Raw TCP `presence.avakin.com:8080` | Online status and joinable friend rooms (JSON frames ending `0x1A`) |

Plus a separate group-chat WebSocket (`ChatClient`, protobuf `cmd/*` routes) and CDN downloads.

---

## How the game behaves, end to end

1. **Boot** — `InitialisationSceneBootstrap` → `State_Bootup` → `State_InitialiseGame`: pick language, check age verification, pull remote config, check the availability/maintenance service.
2. **Login** — scene `LoginNew`, `State_Login` runs a small state machine (maintenance → idle → auto-login → login). Auth is one `POST auth/1/auth/1/login` whose `type` field selects the identity provider (token / email / google / ios / apple / steam). An ECDH handshake alongside it produces the secret that signs every later request.
3. **Profile load** — five REST calls fire in parallel (profile, items, rewards, XP, balance), then the item database (`Life<lang>.db2`) is downloaded from the CDN and opened locally, then entries/restricted-entries/recommendations/sales.
4. **Main scene** — `Services.SceneLoader.TransitionScene("Main")`. The client mints a short-lived ticket from `auth/1/auth/1/sfstoken`, logs into SmartFox zone `"Life"` with it, and joins a room.
5. **In a room** — the `me`/`se`/`ae`/`ne`/`inter`/`chat`/`data` extensions carry room membership, avatar state, queued animations, node ownership, social interactions and chat. Movement offloads to UDP where the scene supports it.
6. **Gameplay content** — arrives as **NetActors**: server-owned objects carrying typed components, driven by ~212 named actions, drawing UI the server authored itself. See [MINIGAMES.md](docs/MINIGAMES.md).
7. **Out of room** — the Pipeline WebSocket keeps the friends graph, DMs and feed live; the presence service reports which friends are online and joinable.

---

## Reading this alongside a decompile

The decompiled sources are **not** included (proprietary, and ~28 MB for `Assembly-CSharp` alone). Every claim in these docs cites the class and file it came from, so you can follow along in your own dump. Paths are written relative to a decompiled tree root, e.g. `Assembly-CSharp/LKWD/WebService/WebServices.cs`.

Two things make that easy. Every `LogService` call retains its original build path, so grepping a string from `Player.log` lands you on the exact source file. And `LKWD/Services.cs` is the fastest index of what the client can do at all.

Version pinning matters: the deep-dive docs describe **client 2.23.0**, API version **15**. A name-level diff against **2.24.0** is in [VERSIONS.md](docs/VERSIONS.md) — the REST surface is unchanged, but the item-database delivery was rebuilt around manifests and VCDIFF deltas, which supersedes the database sections of ARCHITECTURE.md and LOGIN.md.

---

## On embedded secrets

The client ships several hardcoded credentials — a REST API signing secret, a SmartFox application key, a token-derivation salt, and a 28-entry key table regenerated every build. Their **existence, location and role** are documented ([SESSIONS.md §3](docs/SESSIONS.md#3-journey-seq--why-every-later-call-is-signed), [LOGIN.md §4](docs/LOGIN.md#4-tokens-and-session-storage), [NETWORKING.md §1](docs/NETWORKING.md#1-rest-api)); the **values are redacted throughout and no signing material is committed here**.

## License

[CC BY 4.0](LICENSE). "Avakin Life" and "Lockwood" are trademarks of Lockwood Publishing Ltd, used here nominatively.
