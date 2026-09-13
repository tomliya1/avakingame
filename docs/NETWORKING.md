# Networking Reference

Sources: `Assembly-CSharp`, `SmartFoxClient`, `AvakinUdpLib`, `ChatClient`, `BestHTTP`. Client `2.23.0`.

---

## 1. REST API

### Environments — `LKWD/WebService/Environment/Environment.cs`

| Environment | Base URL |
|---|---|
| Production | `https://api-sni.avkn.co/api/` |
| Staging | `https://staging-sni.api.avkn.co/api/` |
| Development | `https://dev-sni.api.avkn.co/api/` |

All three share `APIVersion = 15`, `ProjectName = "avakinlife"`, `ItemCostVersion = 1`, a null `APIKey` (set later at runtime by `SetAPIKey`), and one hardcoded **`APISecret`** — a ~100-char string used as key material for client-token derivation. *(Value present in the binary; intentionally not reproduced here.)*

`Environment.CreateEnvironment(...)` allows a fully custom environment, which is how debug builds retarget the client.

### Request pipeline

`WebServices.CreateRequest(api, payload, type, method)` → `WebRequest` → queued on one of 21 `eRequestChannel`s → `Dispatch()`.

`eWebRequestType` is a flags enum that decides framing:

| Flag | Value | Effect |
|---|---|---|
| `SessionData` | `0x01` | Payload patched with session fields |
| `RequiresSession` | `0x02` | Blocks until a session exists |
| `Replayable` | `0x04` | Re-queued after re-auth |
| `RawJSONContent` | `0x10` | `Content-Type: application/json; charset=utf-8` |
| `ProtoBufContent` | `0x20` | `Content-Type: application/protobuf` |
| `Microservice` | `0x40` | Strip `api/` from the base URL |
| `NonCritical` | `0x80` | Failures don't surface to the user |
| `SSLPinned` | `0x100` | Force HTTPS; pinned via `BestHTTP.Addons.TLSSecurity` |
| `ShortTimeout` | `0x200` | |
| `URLFormContent` | `0x400` | `application/x-www-form-urlencoded` |

Common composites: `DefaultJson = 0x116`, `DefaultJsonNoSession = 0x114`, `DefaultProto = 0x166`, `FormURLEncoded = 0x544`.

### Headers on every request — `WebRequest.SetupHeaders()`

```
X-Avkn-Session          session token
X-Avkn-JWTSession       JWT session token
X-Avkn-UserID           Souqa ID (the canonical user id)
X-Avkn-ApiVersion       15
X-Avkn-ClientOS         HostPlatform.GetOS()
X-Avkn-ClientPlatform   HostPlatform.GetPlatform()
X-Avkn-ClientVersion    e.g. 2.23.0
X-Avkn-ClientVersionCode  "{2}{023}{00}"  → 202300
X-Avkn-ApiKey           when set
X-Avkn-AdvertisingID    advertising id
X-Avkn-GameSessionID    GUID, new per process
X-Avkn-VendorID         installation id
X-Avkn-Locale           user locale
x-avkn-route            optional routing override
```

Login adds `X-Avkn-TZOffset`, `X-Avkn-Device`, `X-Avkn-Start-Chat`, optionally `X-Avkn-Sha` and `X-Avkn-Deeplink`.

Response headers consumed: `x-avkn-session`, `x-avkn-jwtsession`, `x-avkn-helpshift`, `x-avkn-error`.

### Response handling

`WebServices.eResponseAction` — `None, ReSignIn(1), Replay(2), ConnectionLost(4), RateLimited(8), Finalize(16)`. `ValidateHTTPStatusCode` and `ProcessResponseStatus` map HTTP/body status onto these, driving re-auth, replay and back-off.

**Full endpoint list: [ENDPOINTS.md](ENDPOINTS.md) — 141 paths.**

### Other hosts

| Host | Purpose |
|---|---|
| `https://availability.avkn.co/{0}/check` (dev: `availability-service-dev.avkn.co`) | Maintenance / availability gate |
| `https://cdn.avakin.com/`, `https://cdn.dev.avakin.com/` | Primary CDN |
| `https://cdn.avkn.co/`, `http://avakin-2191.kxcdn.com/` | Legacy CDN roots |
| `https://ugc.prod.avakin.com`, `https://ugc.dev.avakin.com` | UGC storage |
| `https://media.avakin.life/`, `https://media.dev.avakin.life/` | Image content & thumbnails API |
| `https://status.avakin.com` | Status page |
| `presence.avakin.com:8080` | Presence (raw TCP) |
| `avakinlife://`, `avakin.com/deeplink/deeplink.php?path=` | Deep links |

---

## 2. SmartFoxServer — realtime rooms

**Protocol:** SmartFoxServer **1.x** (the C# port reports `majVersion=1, minVersion=6, subVersion=0`). Raw TCP with an XML/JSON string protocol, server-side extensions addressed via `SendXtMessage`, room variables and buddy lists. BlueBox HTTP tunnelling is available as a fallback (`SmartFoxClientAPI/Http/HttpConnection.cs`).

**Ports** — `Smartfox/SmartFoxConnection.cs`:

```
DEFAULT_SFS_PORT     = 9600   (plaintext)
DEFAULT_SSL_SFS_PORT = 9599   (SSL)
```

> The SmartFox library's own field default is `port = 9339`, but the game always overrides it — `State_LoadMainScene.cs` constructs `LifeServer { m_Port = 9600, m_SSLPort = 9599, m_Zone = "Life" }`. Per-area values arrive from `ws/1/area/1/get` (`LifeGamePlayData`, keys `server`, `port`, `SSLPort`, `bluebox`, `zone`, `timeout`) or from an `SFSAddr` string parsed by `SmartFoxConnection.SFSDecomposeURI()`.

**Zone:** `"Life"` (`LifeGlobals.LIFE_ZONE_NAME`).

**Login:** REST `auth/1/auth/1/sfstoken` → `SmartFoxWrapper.LoginToZone("Life", souqaID, loginToken, extraProperties)`. `LifeGlobals` also carries `SFS_APP_SECRET_KEY` and `SFS_FORCE_LOGIN_APP_SECRET_KEY` *(values redacted here)*.

**Joining:** `JoinByAreaIdData`, `JoinByAreaTagData`, `JoinByFriendIdData`, `JoinByInviteData`, `JoinRandomSceneData`.

### Extensions — `LifeGlobals`

| Const | Name | Meaning |
|---|---|---|
| `MASTER_EXTENSION_NAME` | `me` | Master/room-management |
| `CHAT_EXTENSION_NAME` | `chat` | Room chat |
| `DATA_EXTENSION_NAME` | `data` | Arbitrary keyed data |
| `INTERACTION_EXTENSION_NAME` | `inter` | Player-to-player interactions |
| `NODE_EXTENSION_NAME` | `ne` | Scene node ownership |
| `ACTION_EXTENSION_NAME` | `ae` | Animation/action sequencing |
| `STATE_EXTENSION_NAME` | `se` | Avatar/user state |
| `MOD_EXTENSION_NAME` | `men` | Moderation |

### Command reference

Derived by mapping each `SendXt(ext, cmd, …)` call to its enclosing method in `LifeClient.cs` and `Smartfox/SmartFoxConnection.cs`. All are sent with `"json"` framing.

**`me` — master / rooms**

| Cmd | Method | Meaning |
|---|---|---|
| `rsi` | `RequestSceneInfo` | Scene info |
| `rl` | `RequestSceneList` / `RequestSceneDetails` | List / detail scenes |
| `rr` | `JoinByAreaID` / `JoinByAreaTag` | Join room by area id or tag |
| `rf` | `JoinByFriendID` | Join a friend |
| `ri` | `JoinByInvite` | Join via invite |
| `rrr` | `JoinRandom` | Join a random scene |
| `srs` | `RequestSceneRoomSwitch` | Switch room index |
| `rk` | `RequestKickUser` | Kick a user |
| `bv` / `ub` | on login | Buddy-list bootstrap |
| `pld` | `SendPlatformData` / `SendChatLanguagePlatformData` | Platform + chat language |
| `paad` / `gaad` | `PutAreaAuxDataField` / `GetAreaAuxDataField` | Area auxiliary data |
| `set_leave_intention` | — | Signal intent to leave |
| `""` + `{m:1}` | — | Heartbeat |

**`ae` — actions**

| Cmd | Method |
|---|---|
| `ad` | `RequestAllActionData` |
| `acs` | `RequestAllActorData` |
| `pa` | `PostQueueAction` / `PostStopAllAction` / `PostParallelAction` |
| `paca` | `PostParallelActorAction` / `PostQueueActorAction` / `PostStopAllActorAction` |
| `msd` | `RequestAllMasterSyncActionData` |
| `msa` | `PostMasterSyncAction` |
| `ssa` | `PostSlaveSyncAction` |
| `bsd` | `PostBroadcastSyncAction` |

The `msa`/`ssa` split is the authority model: one client is master for a synchronised action, others are slaves.

**`ne` — nodes** (scene attachment points, e.g. a chair)

| Cmd | Method |
|---|---|
| `na` | `RequestNode` — acquire, optionally releasing all others |
| `nr` | `ReleaseNodes` |
| `nd` | `RequestNodeData` |

**`inter` — interactions**

| Cmd | Method |
|---|---|
| `inGD` | `RequestInteractionDefs` — get definitions |
| `inCr` | `CreateInteraction` — offer |
| `inRp` | `RespondToInteraction` — accept/decline |
| `inRv` | `RevokeInteraction` |

**`se` — state:** `ua` (`SendUserData`, `SendProfileData`), `ud` (`RequestStateData`)
**`chat`:** `ch` (`RequestChatHistory`), `chg` (`CreateNodeChatGroup`), `chat_mod` (`SendReaction`, `SendReactionButton`)
**`data`:** `sd` (`SendData`)
**`bot`:** `log` (`SendDebugInformation`)
**any:** `fjwt` (`FreshenJWTObject`) — refresh a JWT held by a server extension

---

## 3. UDP movement replication — `AvakinUdpLib`

Used for high-frequency avatar movement. Host and port are handed to the client over SmartFox (`SmartFoxWrapper.OnUdpHostUpdate`; an empty value logs *"Received empty UDP host from SmartFox server"*). Enabled per scene (`SetSceneDataSupportsUDP`); otherwise movement falls back to SmartFox TCP. Game side: `NetworkUDPManager.cs`, consumed by `MovementSystem/Movement.cs`.

**Authentication:** each packet is signed with **HMAC-SHA256** using a per-user shared key taken from the SmartFox room user object (`CurrentRoom.GetUser(id).GetUdpSharedKey()`, UTF-8 bytes).

### Wire format — `Protocol/Utils/PacketSerializer.cs`

Header is **48 bytes**, big-endian, followed by the payload.

| Offset | Size | Field |
|---|---|---|
| `0` | 1 | `bit7` = isRequest, `bits 0-3` = opcode |
| `1` | 4 | `messageId` (uint32 BE) |
| `5` | 4 | `userId` (uint32 BE) |
| `9` | 1 | `rsv4 << 4` |
| `10` | 4 | `roomId` (uint32 BE) |
| `14` | 32 | HMAC-SHA256 signature |
| `46` | 2 | `payloadLength` (uint16 BE) |
| `48` | n | payload |

The signature covers a compacted buffer of **header[0..14] ‖ payloadLength(2) ‖ payload** — i.e. the signature field itself is excluded. Verification is a byte-by-byte compare that throws `CryptographicException` on the first mismatch.

### Opcodes

```
0 Ping   1 Pong   2 ControlCommand
3 GameCommand   4 GameStateCommand   5 BatchReplicatedState
```

### Replicated / batched variant

`BatchReplicatedState` payloads pack many inner packets. Those use a **14-byte header with no signature**, immediately followed by a 2-byte length and the payload (`DeserializeReplicated`, `DeserializeBatch`) — the outer packet's HMAC authenticates the whole batch, so inner frames are unsigned.

---

## 4. Chat

Three distinct systems.

**1. In-room chat** — SmartFox `chat` extension plus `SendPublicMessage` / `SendPrivateMessage`. Text is screened by REST `messagefilter/1/messagefilter/1/check`, with rules from `filter/1/rules/1/list`. Client model in `LKWD/Chat/` (`LifeChatSystem`, `ChatData`, `ChatUser`, `ChatReaction`, `eChatType`).

**2. LibChat (direct messages)** — protobuf over the shared Pipeline WebSocket, `Envelope.PayloadOneofCase.Chat`. Managed by `LKWD/LibChat/LibChatManager.cs`; domain types `ChatThread`, `ChatConversation`, `ChatMember`, `ChatDetails`, `ChatAction`. UI in `State_Conversation*` / `Panel_Conversation*`.

**3. ChatClient (group chat)** — its own WebSocket assembly. `Client.CreateDefaultClient(logger, endpoint, tokenProvider)` composes `WebSocketsTransport` (BestHTTP) + `HeartbeatTransportWrapper` + `ProtobufCodec`, with `ReconnectableCommunicationManager`, `ExponentialBackoff`, `GapFilingEventsManager` and `TokenCommunicationManagerAuthorizer`.

Routes: `cmd/auth`, `cmd/send_messages`, `cmd/get_events`, `cmd/subscribe`, `cmd/unsubscribe`.
Wired by `LKWD/Groups/Chat/GroupChatClient.cs`; endpoint comes from remote config `GroupsConfig.ChatConfiguration`.

---

## 5. Presence — raw TCP JSON

`LKWD/Presence/Client.cs` → **`presence.avakin.com:8080`** (overridable from config `servers.live.*`).

Defaults: keep-alive 180 s, reconnection timeout 90 s (+30 s offset), max 100 registered friends, 16-user initial list, offline purge after 180 s, read buffer 32 KB, expected max message 8192 B.

**Framing:** JSON messages terminated by byte **`0x1A`** (`MESSAGE_TERMINATOR = 26`).

Client → server: a `register` message carrying id, version, session token and the friend id list; then periodic `keepAlive`.
Server → client: `friendsOnline` (with SFS server addresses and `joinable` flags), `presence`, `roomUpdate`, `infoUpdate`, `disconnect`.

State model: `eUserState { Offline, Online }`, `eUserEvent { Initial, StateChange, RoomChange }`, plus a hint channel (`eHint`, up to 128 tracked).

---

## 6. Pipeline WebSocket — friends, feed, DMs

`LKWD/WebService/WebSocketClient.cs`. Protobuf `Envelope` (`LKWD/WebService/Models/Pipeline/Envelope.cs`). Max message **4000 bytes**. Request ids start at `9000`. Endpoint, ping, reconnection and transport parameters all come from remote config; the connection itself is built by `WebConnectionFactory` (either `BestHTTPWebConnection` or `WebSocketSharpWebConnection`).

### `Envelope.PayloadOneofCase`

| # | Case | | # | Case |
|---|---|---|---|---|
| 2 | `Error` | | 16 | `Item` |
| 3 | `Status` | | 17 | `GameRequest` |
| 7 | `Chat` | | 18 | `GameResponse` |
| 8 | `SocialEvents` | | 19 | `Feed` |
| 9 | `Void` | | 20 | `Relation` |
| 10 | `Presence` | | 21 | `FriendState` |
| 11 | `FriendList` | | 22 | `Auth` |
| 12 | `Friend` | | 23 | `SocialGraph` |
| 15 | `Event` | | 100 | `LastSeen` |

Model classes live in `LKWD/WebService/Models/Pipeline/` — `Friend`, `FriendList`, `Bond`, `Relation`, `Feed*`, `Counters`, `Presence`, `PartyOnline`, `LastSeen*`, plus reflection descriptors.
