# MelonLoader Mods in This Workspace

The workspace around this repo contains five MelonLoader mod projects built against the decompiled client. They're documented here because **how they hook the game is itself a description of how the game works** — each one names a real class and method in `Assembly-CSharp`.

> These are client-side research tools. Anything that changes what the client *believes* it owns does not change what the server records, and using them against live servers risks a ban. See the disclaimer in the [README](../README.md).

---

## Common technique

All of them share one pattern, and it's the right pattern for an IL2CPP target:

1. **Never `typeof()` a game type.** Il2Cpp proxy types are regenerated per game version, so a compile-time reference breaks on every update. Instead, walk `AppDomain.CurrentDomain.GetAssemblies()` for `Assembly-CSharp` and resolve types and methods by **name** via reflection.
2. **Patch every overload.** Iterate `type.GetMethods(Public|NonPublic|Instance|Static)` and patch each match, skipping abstracts.
3. **Only skip `void` or `bool` methods.** A Harmony prefix that returns `false` on a method with a reference return type hands `null` back to the caller and crashes the game. `AvakinLocalPlace/Patches.cs` documents this explicitly after hitting it.
4. **Wait for the interop layer.** `OnInitializeMelon()` fires while MelonLoader is still standing up IL2Cpp interop; `Assembly-CSharp.GetTypes()` can throw `ReflectionTypeLoadException` there. `AvakinAdminConsole` retries on a coroutine for up to 120 s before patching.
5. **Gate every patch behind a static bool**, toggled from a panel injected into CinematicUnityExplorer.

---

## `AvakinUnlockMod` (v3.0.1)

Harmony id `com.avakinunlock.mod`. ~137 lines.

Patches every `bool`-returning method named **`IsItemOwned`** or **`IsItemIdOwned`**, anywhere in `Assembly-CSharp`, with a prefix that forces `__result = true` and skips the original — gated on `Core.PatchOwned`.

*What it tells you about the game:* ownership checks are not centralised in one service. The mod has to sweep the whole assembly and reports a patch count at startup, which implies the same predicate is duplicated across several types.

---

## `AvakinLocalPlace` (v1.0.0)

Harmony id `com.avakinlocalplace.mod`. ~259 lines. Targets the apartment editor.

| Target | Kind | Effect |
|---|---|---|
| `ApartmentFileHandler.RemoveUnownedItems` | prefix (void) | Skip the coroutine that strips unowned furniture on load |
| `ApartmentFileHandler.DisplayUnownedErrorMessage` | prefix (void) | Suppress the warning |
| `ApartmentFileHandler.ForceApartmentReload` | prefix (void) | Prevent the forced reload |
| `ApartmentFileHandler.SaveApartmentCallback` | **postfix** | Let the real server callback run, then call `PopupController.DestroyAll()` to dismiss the error popup |
| `PlacementObject.CanBePlaced` | prefix (bool) | Force `true` |
| `PlacementObject.ValidPlacement` | prefix (bool) | Force `true` |

The `SaveApartmentCallback` handling is the interesting one: it is a **postfix, not a skip**, precisely because the server still rejects the save. The mod cannot make the save succeed — it only hides the resulting popup. That's a clean demonstration that apartment layout is server-authoritative (`ws/1/area/1/save`), and that these patches are purely local/visual.

---

## `AvakinAdminConsole` / `AvakinConfigDump` (v1.4.0)

Harmony id `com.avakinconfigdump.mod`. ~1,028 lines — the largest of the five.

Resolves `LKWD.Configuration` and dumps the client's **remote configuration** to disk, with an `OverridesProfile` that can feed values back in. Because config drives real behaviour (see [ARCHITECTURE.md](ARCHITECTURE.md) §3 — generator version, `useSHA`, server lists, feature gates), this is the most useful of the mods for understanding the client.

Note the assembly name (`AvakinAdminConsole`) and the `MelonInfo` name (`AvakinConfigDump`) differ — the project was renamed but the manifest wasn't.

---

## `AvakinMarketFeed` (v1.0.0)

~161 lines, no Harmony patching at all. Registers a MelonPreferences hotkey (default `M`), then finds the live `LKWD.UI.TopBarManager` MonoBehaviour in the scene and invokes `OpenMarketFeed()` on it by reflection, with a 0.3 s debounce.

A minimal example of driving existing game UI rather than modifying it. Its own warning text ("is this Avakin 2.21+?") dates the `OpenMarketFeed` entry point.

---

## `MeshDumper`

~7,789 lines in a single file — geometry extraction from the loaded scene.

---

## Build setup

Each project is a .NET SDK-style `.csproj` targeting the MelonLoader `net6` runtime, referencing stub assemblies from a local `libs/` folder (or the shared `dummydll3/` set) rather than the real game DLLs. Output drops into `Mods/`.

Runtime dependencies present in the workspace: MelonLoader (net6/CoreCLR), `CinematicUnityExplorer.ML.IL2CPP.CoreCLR`, `UniverseLib.ML.IL2CPP.Interop`, HarmonyX.

Panels are injected into CinematicUnityExplorer's **Misc** tab (F7) rather than building bespoke UI.

## AvakinTrafficCapture

Wire capture (HTTP + SmartFox + UDP). Much of the protocol detail in these notes was confirmed against captures from this mod rather than read out of the decompile alone. Neither its source nor the compiled DLL is included here.
