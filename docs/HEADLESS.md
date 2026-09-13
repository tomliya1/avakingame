# What Is Reachable Without the Client

The client is one implementation of two documented protocols, not a privileged one. This page sets out which parts of the game are protocol and which parts are genuinely Unity — i.e. what another implementation could in principle speak to, and what it could not.

This repository contains **notes only**; no client, no tooling. What follows is analysis, not instructions.

---

## 1. The split

| Plane | Nature | Reachable in principle | Notes |
|---|---|---|---|
| **REST** `api-sni.avkn.co` | JSON over HTTPS, 141 endpoints | Yes — it is an ordinary signed HTTP API | Every call after login needs a valid `X-Avkn-Journey-Seq`; see [SESSIONS.md §3](SESSIONS.md#3-journey-seq--why-every-later-call-is-signed) |
| **SmartFox** zone `Life` | SmartFoxServer 1.x, JSON-framed extensions | Yes, but stateful and **exclusive** | One live session per account — a second login evicts the first |
| **UDP movement** | 48-byte header, HMAC-SHA256 per packet | Yes, where the scene enables it | Key comes from the SFS room user object; falls back to SFS TCP |
| **Pipeline / group chat** | protobuf WebSockets | Yes | Friends, DMs, feed |
| **Presence** | raw TCP, `0x1A`-terminated JSON | Yes | Online + joinable state |
| **Avatar generation** | Unity mesh + texture pipeline | **No** | `AvakinGenerator_V1/V2`, texture streaming, AvaCraft — this is renderer work, not protocol |

The dividing line is clean: **anything the server decides is on the wire; anything the GPU decides is not.**

## 2. Why minigames sit on the protocol side

Because the client contains none of them. A minigame is a server script driving generic primitives — spawn actors, attach components, push a UI tree, wait for a ref to be notified. Nothing about the loop requires rendering; the rendering is a consequence of the messages, not a participant in them.

The `qte_slider` is the clearest case. The pointer animates locally, the server never sees it, and the success zone is written into the background image's own URL. The server's entire view of the minigame is one reported integer. See [MINIGAMES.md §6.1](MINIGAMES.md#61-a-qte-catch--prefab-panel-client-side-skill).

## 3. What constrains an alternative implementation

Four things, in descending order of how much trouble they cause:

1. **Request signing is build-pinned.** `X-Avkn-Journey-Seq` derives from 28 constants regenerated every client build, combined on a 90-minute rotation. A stale table produces a signature that is well-formed and wrong, and the server answers `401 invalid request` — indistinguishable from an expired session unless you know to look.

2. **`LifeAction` is a tagged union.** One unmodelled action tag invalidates the entire `data_actors` frame it arrived in, discarding everything batched alongside it. Coverage gaps present as missing gameplay, not as parse errors.

3. **Refs cannot be predicted.** Callback addresses embed the account id and an instance stamp, and are renumbered per session. They can only be read from the frames that carry them — sometimes several levels deep inside a panel payload.

4. **Sessions are exclusive.** Minting a SmartFox ticket disconnects whatever else holds one for that account. The HTTP plane has no such rule.

## 4. Terms of service

Everything above describes how the protocol is put together. Connecting a non-official client to Lockwood's live servers is a separate question, governed by the game's Terms of Service rather than by anything technical — and one this repository takes no position on beyond the disclaimer in the [README](../README.md).
