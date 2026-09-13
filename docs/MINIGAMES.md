# Minigames & Server-Driven UI

**How a minigame actually works: NetActors, Homebrew panels, and the callback refs that tie them together.** Client `2.23.0`. Sources: `Avkn/Smartfox/Networking/`, `Smartfox/Networking/Components/`, `Homebrew/`.

---

## 1. There is no minigame code in the client

This is the single most useful fact about Avakin Life, and it explains almost everything else on this page.

The client ships **no** implementation of Magical Fishing, the Cottagecore meadow, the diner, the cafe job, or any seasonal event. What it ships is a **generic runtime**:

- a way for the server to spawn objects in a room and attach typed behaviours to them (**NetActors**),
- a fixed library of UI widgets the server can assemble into arbitrary screens (**Homebrew**),
- a fixed catalogue of prefabricated dialogs the server can pop by name,
- and a convention for the client to call back — a **ref**.

A minigame is therefore a *script running on the server* that drives those four things. That is why events appear and vanish without a client patch, why the same build plays content it has never seen, and why the client-side source tells you the **grammar** but never the **content**. To learn what a specific minigame does you read the wire, not the decompile. The decompile tells you what is *possible*, and what shape the answers must take.

```
  server (GLM script)                          client (generic runtime)
        │
        │  create_actors   ─────────────▶  spawn actors, attach components
        │  data_actors     ─────────────▶  run actions on those components
        │       └─ push_homebrew_panel ─▶  build a UI tree out of JSON
        │       └─ open_ui_panel       ─▶  pop a prefab dialog by name
        │                                          │
        │                                          │ player does something
        │◀──── ae/pa  nop {ref: "<ref>"} ──────────┘
        │
        │  data_actors (reward, next step, close panel) ─▶ …
```

---

## 2. NetActors — the object model

A **NetActor** is a server-owned object in the room. It is not a Unity prefab; it is an id plus a list of **components**. `NetActorSystem` (`Avkn/Smartfox/Networking/NetActorSystem.cs`) handles exactly three inbound commands and ignores everything else:

| `r` | Effect |
|---|---|
| `create_actors` | Instantiate actors; attach and initialise their components |
| `data_actors` | Deliver **actions** to existing actors' components |
| `destroy_actors` | Tear actors down |

Actor ids are structured and carry meaning. A real one:

```
homebrew_ui_sdk_1181155972#n=2006000176_758325_T1787313400010
└──── component/system tag ────┘ └─ area ─┘ └ uid ┘ └ instance ─┘
```

Note the **account id embedded in the id**. Ids, and the refs derived from them, are minted per user and per instance — they can only be read off the wire, never predicted or reused.

### Components

Each component is a C# class tagged `[NetActorComponent("<identifier>", version)]`. **35 exist.** Each declares handler methods tagged `[NetActionProcessor("<action>")]` — **212 distinct actions** in total. When `data_actors` delivers an action, `NetActor` routes it by name to the component that claims it.

```csharp
[NetActorComponent("homebrew_ui_proxy", 1)]
public class HomebrewUIProxyComponent : NetActorComponent
{
    [NetActionProcessor("push_homebrew_panel")]
    private IEnumerator ActionPushHomebrewPanel(ExecutionContext context, LifeAction lAction) { … }
}
```

Full table in [§7](#7-component--action-reference).

Actions are ordered and can block — the processor is a coroutine, and `ExecutionContext` can interrupt a sequence mid-flight. The client also has a **fast-forward** mode (`eMode.FASTFORWARD`, `eNetActionExecutionMode.FASTFORWARD`) used when joining a room that is already in progress: queued actions are replayed without animation until the actor catches up.

> **A trap worth knowing.** `LifeAction` is a tagged union. A single unrecognised action tag makes the whole `data_actors` frame fail validation and be discarded — silently taking down everything batched alongside it. A reimplementation that models 99% of the tags will appear to work and then lose entire interactions.

---

## 3. Refs — how the client talks back

The server hands the client **refs**: opaque callback addresses, usually prefixed `remote://` or `sfs://`.

```
remote://1181155972#n=2006000176_758325_T1787313400010_closeRef
```

A ref arrives wherever an interaction is possible — as an action parameter (`action_ref`, `panel_action_ref`, `ok_ref`, `cancel_ref`, `close_action`), or as a component field (`enter_event_ref` / `exit_event_ref` on a trigger volume). To act, the client *notifies* the ref:

```csharp
// LifeClient.cs
public void NotifyRemote(string actionUri, Dictionary<string, object> payload = null) {
    string text = Regex.Replace(actionUri, "sfs:\\/\\/|remote:\\/\\/", "");
    LifeAction a = new LifeAction {
        m_Action = "nop", m_Ref = text, m_Params = payload,
        m_SetOriginAtStart = true };            // ← attaches avatar position
    a.AddPositionalInfo(LiveAvatar.Action.Transform);
    LiveAvatar.ParallelAction(null, a);         // → SendXt("ae", "pa", …, "json")
}
```

So **every notify is a `nop` action posted on the `ae` extension with command `pa`**, and by default it carries the avatar's current position. Three variants exist:

| Method | Attaches |
|---|---|
| `NotifyRemote` | position |
| `NotifyRemotePosRot` | position + euler rotation |
| `NotifyRemoteNoPos` | nothing |

The position matters: if the server enforces proximity, a notify sent from the wrong place is legitimately refused. On the wire the action serialises as (`LifeAction.ToHashtable`):

```jsonc
{ "id": <int>, "uid": "<id>", "a": "nop", "c": <critical>,
  "o": [x,y,z],            // origin, when m_SetOriginAtStart
  "r": [x,y,z],            // euler, when m_SetRotationAtStart
  "p": { … },              // your payload
  "ref": "<the ref, scheme stripped>",
  "t": <elapsed server ms> }
```

---

## 4. Three families of server-driven UI

The server has three different ways to put a screen in front of you, and **they are not interchangeable — they have different reply envelopes.** Getting this wrong is a classic silent no-op.

| Family | Component | Action | What the server controls | Reply envelope |
|---|---|---|---|---|
| **Homebrew** | `homebrew_ui_proxy` | `push_homebrew_panel`, `load_panel_layout` | **everything** — the layout tree is authored server-side | payload **+ `panel_id` + `element_id` + `error`** |
| **Minigame panels** | `ui_minigame_proxy` | `open_ui_panel` / `update_ui_panel` / `close_ui_panel` | picks one of **16** prefab dialogs by name, and its parameters | bare payload, no panel/element keys |
| **Client panels** | `client_proxy` | `client_ui_panel` / `client_close_ui` | picks one of **17** prefab dialogs by name | bare payload |

Two more components round out the HUD: `sidebar_proxy` (15 actions creating and badging the side buttons) and `ui_score` (9 actions driving the score widget — `score_set_label`, `score_glow`, …).

### The prefab catalogues

Anything not on these lists is ignored by the client, so an unfamiliar panel name in a capture is always one of these:

**`ui_minigame_proxy` / `open_ui_panel`** — `contents_table_dialog`, `insufficient_funds_dialog`, `award_item_dialog`, `apply_badge_dialog`, `rewards_overview_dialog`, `rewards_claim_dialog`, `scene_entry_requirements_dialog`, `shop_item_picker`, `avatar_builder`, `quiz_tutorial_dialog`, `tutorial_dialog`, `on_demand`, `minigame_tutorial`, `community_goals`, **`qte_slider`**, `countdown_timer`.

**`client_proxy` / `client_ui_panel`** — `levelup_panel`, `nux`, `confirm_dialog`, `item_replacement_dialog`, `workrota_dialog`, `career_workrota_dialog`, `customer_queue_dialog`, **`item_picker`**, `exchange_dialog`, `notifications_inbox`, `reward_tab`, `info_popup`, `confirm_purchase`, `mini_travel_panel`, `information_panel`, `custom_advert_panel`, `salon_teleport`.

---

## 5. Homebrew in depth

**Homebrew** is Lockwood's server-authored UI framework — 157 classes under `Homebrew/`, including **48 element types** and **39 response verbs**. The server sends a JSON tree; the client builds real Unity UI from it.

### 5.1 Addressing: buckets and panel refs

Every panel belongs to a **bucket**, and is addressed by a composite:

```csharp
CreatePanelRef(bucketName, panelID) => $"{bucketName}#{panelID}"
```

The bucket name comes from the component's own init data (`bucket_name`); the panel id from the action. A `DataBucket` is the key/value store the panel binds against — data paths look like `@bucket/…`, `@panel/…`, `@local/…`, with `/` separators, `*` wildcards and `#` for array counts.

### 5.2 Pushing a panel

`push_homebrew_panel` carries, in order of how the client uses them:

| Key | Meaning |
|---|---|
| `panel_id` | **required** |
| `panel_action_ref` / `back_button_ref` | **required** — the ref the panel reports to. Remembered per panel |
| `template_urls` | fetched and registered first |
| `panel_layout` *or* `panel_url` | the layout JSON inline, or a `cdn://` URL to fetch |
| `action_list` | directives applied after the panel exists (see 5.3) |
| `responses` | named response programs the elements refer to |
| `back_response_key` | which response the back button runs |
| `control_locks`, `allow_movement` | what the player may do while it is open. **Movement is locked unless `allow_movement` is true** |

Layouts are **not** in the client. `ResourceController.FetchDefinition` resolves the URL through `Globals.EvaluateCDNUrl` and downloads it, which means a panel's full button set and response chain can be read from the CDN ahead of time instead of discovered by triggering it.

`load_panel_layout` is the same thing but leaves the panel hidden — a preload.

### 5.3 The data bucket is the model

`action_list` entries are applied in order. `merge` is special-cased and folded straight into the bucket; everything else is dispatched through `PanelActions.Execute` (**32 actions**):

```
back  bind_back  close  close_all  push_panel  deep_link  play_animation
play_kf_animation  set_active_states  bind  bindings  bind_responses  merge
block_panel_interaction  move_element  enable_chat  hide_panel  response_activate
loading_screen  spinner  start_countdown  stop_countdown  reset_countdown
data_path_set  data_path_remove  array_add  array_insert  array_replace
array_replace_by_value  array_remove  array_remove_by_value  nop
```

**The panel's visible state is the accumulation of the merges, not the layout.** The layout is an empty scaffold with bindings; the item grid, the prices, the dialogue text all arrive as bucket data. Anything reading a Homebrew panel must apply the whole `action_list` before the content exists.

A real `push_homebrew_panel`, captured live — note the payload nested four levels deep:

```json
{"a":"push_homebrew_panel","p":{
  "panel_id":"dialogue_panel",
  "action_list":[{"scheme":"@global","action":"merge",
    "bucket_name":"data_bucket_sdk_758325",
    "data":{"dialogue_panel":{
      "close_action":"remote://1181155972#n=…_closeRef",
      "text":"Shall we go to the Collection Minigame now?",
      "choice":{"3":{"active":true,"text":"Yes"},
                "4":{"active":true,"text":"No"}}}}}]}}
```

The only copy of the callback ref is at `p.action_list[0].data.dialogue_panel.close_action`. Shallow key lookups miss it.

### 5.4 Responses — a mini-language on every element

Each interactive element carries a comma-separated program. `PanelResponse.Extract` parses it into 39 verbs:

| Group | Verbs |
|---|---|
| Navigation | `close` `close_active` `close_all` `close_all_animate` `open` `back` `push` `push_all` `pop` `pop_all` `clear` |
| Data | `set` `set_array` `copy` `copy_strict` `copy_array` `copy_array_strict` `move` `move_strict` `remove` `add` `multiply` `str_length` `replace_data_path` |
| Payload | `payload` `payload_array` `rem_payload` `bind` |
| Control flow | `if` `continue` `stop` |
| Visibility | `set_active` `toggle_active` `spinner` `loading_screen` |
| Other | **`notify`** `nop` `debug` `metric` |

`@responses/<key>` indirects into the named `responses` block, and nests. **`notify` is the only verb that reaches the server** — everything else mutates local state. A program builds up a payload with `payload(…)`, then ends in `notify`. `Process` short-circuits on the first error or `stop`, and an error forces a notify carrying the error string.

### 5.5 The Homebrew reply envelope

This is the part that differs from the other two families (`Homebrew.Core.Utils.CreateNotifyServerPayload`):

```csharp
payload["panel_id"]   = FetchPanelID(panelRef);   // the part after '#'
payload["element_id"] = elementID;
payload["error"]      = error;                    // null on success
Services.LifeClient.NotifyRemote(actionRef, payload);
```

So a Homebrew button replies with **your payload plus three injected keys**. A NetActor prefab panel replies with the payload alone. Sending a Homebrew-shaped reply to a prefab panel (or vice versa) is accepted by the transport and ignored by the server.

---

## 6. Two worked examples

### 6.1 A QTE catch — prefab panel, client-side skill

`UIMinigameProxyPanels.OpenQuickTimeEventSlider` handles `open_ui_panel {panel:"qte_slider"}`. The server sends `action_ref`, `slider_background` (**required**), `timer_end_iso`, `pointer_speed`, `auto_close`, `apply_control_locks`, `state`. The client replies on `action_ref` with exactly two shapes:

```jsonc
{"state":"stop", "pointer_pos": <int px>, "normalised_pointer_pos": <int 0-100>}
{"state":"close"}                       // from OnPanelDestroyedCallback
```

`pointer_pos` is `(int)anchoredPosition.x`; the normalised value is `pos / sliderWidth * 100`.

**The slider is entirely client-side.** The pointer animates locally; the server never observes it and only ever sees the number you report. The success zone is not secret either — it is encoded in the background image's own URL (`.../qte_slider/185-265/...`). The skill check is advisory.

### 6.2 A collect loop — trigger volumes and published refs

A gathering minigame (berries, flowers, shards) is built from ordinary NetActors:

1. `create_actors` spawns one actor per collectable, each with a `volume_trigger` component.
2. The component's init data carries `volume_data` (a sphere or box with `center`/`radius`) plus **`enter_event_ref`** and `exit_event_ref`.
3. Walking in fires `NotifyRemote(_enterEventRef)` — position attached, which is how the server verifies you were actually there.
4. The server answers with `data_actors`: a reward particle, a bucket merge updating the HUD, a `destroy_actors` for the picked item.

Enrolment in a round is the same mechanism at a larger scale — a 30 m play-area volume whose `enter_event_ref` is the "I'm playing" signal.

**The refs are the whole game, and they are numbered per instance** — the same berry is `customref_10` in one session and `customref_2606` in another. There is nothing to hardcode.

Progress is published separately as SmartFox **user variables** (`sv.<event>_balance`, `sv.max_…`), which is also where quotas live. An exhausted quota looks exactly like a broken script unless you read them.

---

## 7. Component & action reference

All 35 components and the actions each claims, from `[NetActorComponent]` / `[NetActionProcessor]`.

| Component | Actions |
|---|---|
| `advert` | `audiomob` |
| `anchor` | `anchor_attach` `anchor_release` |
| `anchor_between` | `anchor_between_attach` `anchor_between_release` |
| `animation` | `model_animation` |
| `audio_proxy` | `audio_play_clip` `audio_stop_clip` `audio_set_volume` |
| `audio_track` | `start` `stop` `change_track` |
| `avakin` | `avakin_animation` `avakin_bundle_animation` `avakin_attach` `avakin_detach` `avatar_add_animset` `avatar_remove_animset` `avatar_override_lighting` `avakin_update_outfit` `avakin_replace_config` |
| `avakin_attachment` | `avakin_attachment_update` `avakin_attachment_remove` |
| `avatar_proxy` | `avatar_add_animset` `avatar_remove_animset` `avatar_animation` `avatar_sit_on_ride` `avatar_exit_ride` `avatar_add_outfit` `avatar_remove_outfit` `avatar_set_current_config` `avatar_set_nametag` `avatar_set_nametag_label_overlay` `avatar_unset_nametag` `avatar_hide_nametag` `avatar_show_nametag` `avatar_enable_interactions` `avatar_disable_interactions` `avatar_cancel_interact` `avatar_hide` `avatar_show` `avatar_set_config` `avatar_revert_config` `avatar_play_particle` |
| `bundle_asset` | `bundle_set_visible` `bundle_play_particle` |
| `camera_proxy` | `camera_orbit_enter` `camera_orbit_leave` `camera_orbit_focus` `camera_orbit_item_focus` `camera_orbit_item_focus_clear` `camera_follow_enter` `camera_follow_leave` `camera_hide_avakins_enter` `camera_hide_avakins_leave` |
| `client_proxy` | 40 actions — camera control, control locks, awards, notifications, purchases, deep links, **`client_ui_panel`**, `client_push_actions`, `client_refresh_balance`, … |
| `data_binding_proxy` | `update_binding_data` `clear_data` |
| `ftue_proxy` | `ftue_dialogue` `ftue_avatar_select` `ftue_username_select` `ftue_item_picker_select` `ftue_refresh_profile` `ftue_get_avakin_details` `ftue_generate_avatars` |
| **`homebrew_ui_proxy`** | `push_actions` `nop_action` `action_chain` `update_bucket` **`push_homebrew_panel`** `load_panel_layout` `block_panel_interaction` `clear_panel_layout` `close_homebrew_panel` `add_single_template_definition` `add_template_definition` `add_template_definitions` |
| `interaction` | `interaction_add` `interaction_remove` `interaction_update` `interaction_update_name` `interaction_update_icon` |
| `material` | `add_material` `set_material` `update_material` |
| `model` | `model_set_visible` `model_animation` `model_animation_stop` `model_animation_reset` `model_attach_ready` `model_play_particle` |
| `multitrack_player` | `play` `stop` `change_track` |
| `navigation` | `navigation_teleport` `navigation_path` `navigation_path_target` `navigation_follow_target` `navigation_clear_target` |
| `navigation_blocker` | *(state only)* |
| `net_actor_node` | *(state only)* |
| `particle_system` | `particle_system_play` `particle_system_resume` `particle_system_stop` `particle_system_clear` `particle_system_pause` `particle_system_update` |
| `petkin` | `petkin_set_visible` `petkin_play_particle` `petkin_set_laying` |
| `petkin_bundle_asset` | *(state only)* |
| `scene_camera` | `add_camera` `take_photo` `share_photo` `start_live_feed` `stop_live_feed` |
| `sidebar_proxy` | `sb_button_create` `sb_button_remove` `sb_button_alert` `sb_button_show` `sb_button_hide` `sb_button_enable` `sb_button_disable` `sb_button_disable_on_touch` `sb_button_update_icon` `sb_button_icon_colour` `sb_button_animate` `sb_button_increment_dot` `sb_button_dot_label` `sb_button_dot_icon` `sb_button_remove_dot` |
| `slide` | `set_material` `play` `stop` `setup` |
| `tween` | `tween_position` `tween_rotation` `tween_scale` |
| `ugc_proxy` | `ugc_add_outfit` `ugc_remove_outfit` `ugc_add_dynamic_outfit` `ugc_generate_thumbnail` `ugc_get_details` `ugc_notify_item` `ugc_hide_underwear_datapath` `ugc_hide_underwear` |
| **`ui_minigame_proxy`** | **`open_ui_panel`** `close_ui_panel` `update_ui_panel` `chat_min_max_enabled` `hud_side_buttons_enabled` `hud_top_buttons_enabled` |
| `ui_score` | `score_show` `score_hide` `score_enable_touch` `score_disable_touch` `score_update_icon` `score_enable` `score_disable` `score_set_label` `score_glow` |
| `video_capture` | `video_start_capture` `video_stop_capture` `video_capture_support` `video_share_tiktok` `video_share_native` `video_share_existing_tiktok` `video_check_user_has_capture` `video_subscribe_on_gallery_save` |
| `volume` | *(state only)* |
| `volume_trigger` | `volume_enable` `volume_disable` — plus the `enter_event_ref` / `exit_event_ref` fields that do the real work |

---

## 8. Reading this in the source

| Question | File |
|---|---|
| How do actors arrive and dispatch? | `Avkn/Smartfox/Networking/NetActorSystem.cs`, `NetActor.cs` |
| What can a component be told to do? | `Smartfox/Networking/Components/*.cs` |
| How is a Homebrew panel built? | `Homebrew/HomebrewManager.cs`, `Homebrew/Core/PanelCreator.cs` |
| What can the server change after the fact? | `Homebrew/Core/PanelActions.cs` |
| What does a button do when pressed? | `Homebrew/Responses/PanelResponse.cs` + `Homebrew/Responses/*.cs` |
| What exactly gets sent back? | `Homebrew/Core/Utils.cs` (`CreateNotifyServerPayload`), `LifeClient.NotifyRemote` |
| Which prefab dialogs exist? | `UIMiniGameProxyComponent.cs`, `ClientProxyComponent.cs` |

Every `LogService` call in the decompile keeps its original build path, so grepping a log line from `Player.log` lands you on the exact source file.
