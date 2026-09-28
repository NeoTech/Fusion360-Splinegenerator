# Fusion360-SplineGenerator — Status & TODO

## TL;DR — the loading problem is SOLVED
The add-in kept showing a generic **"SCRIPT ERROR"** with no traceback. After
comparing against the two working reference add-ins in
`%APPDATA%\...\API\AddIns\` (SprocketGenerator, Cycloid Rack and Pinion), the
real root cause was found:

> **Fusion's add-in loader calls `run(context)`, not `start(context)`.**
> Our file only defined `start()`, so Fusion never initialized the add-in.

Fixed: renamed `start()` -> `run()`. Verified in the live Fusion process that
`run()` returns `True` and the toolbar button registers. **No need to start
over** — the code is sound.

## Bugs found & fixed (all verified against live Fusion)
1. **Entry point** — `start()` -> `run()` (the actual blocker).
2. **Manifest fields** — `type: "addin"`, `autodeskProduct: "Fusion"`,
   `supportedOS: "windows|mac"` (string, not array), added `version`.
3. **File/folder name casing** — files renamed to match the folder exactly.
4. **Handler base class** — `CommandInputChangedEventHandler` ->
   `InputChangedEventHandler`.
5. **Icon path** — `addButtonDefinition` 4th arg must be a *folder*
   (`resources/`), not a `.png`. Created `resources/` with a placeholder icon.
6. **Reference command** — `addCommand`'s 2nd arg must be a *real* command id in
   the panel. Changed `"SolidSplineGen"` (nonexistent) -> `"Extrude"`.

## Current state
- [x] Pure-math engines (`core/`) — complete, unit-tested.
- [x] CAD builders (`cad/`) — complete, unit-tested.
- [x] Add-in wiring (`Fusion360-Splinegenerator.py`) — loads and registers.
- [x] 63 unit tests pass (`python -m unittest discover -s tests -t .`).

## Next steps (functional testing in Fusion)
- [ ] Toggle the add-in **Run** switch off/on (or restart Fusion) to reload.
- [ ] Click the toolbar button -> dialog should open.
- [ ] Smoke-test each standard end to end:
  - [ ] DIN 5480 metric involute — external shaft.
  - [ ] DIN 5480 metric involute — internal hub.
  - [ ] ANSI B92.1 imperial involute (diametral pitch).
  - [ ] SAE J499 parallel-side PTO presets (6T / 21T).
- [ ] Verify circular pattern + chamfer features build without errors.
- [ ] Check preset dropdown auto-fills and locks the right inputs.

## Housekeeping
- [ ] Remove the temporary `try/except` import-logging block in the main file
      once stable (writes `splinegenerator_import_error.log`).
- [ ] Replace placeholder `resources/default.png` with a real icon.
- [ ] Decide whether to keep `debugEnabled`/`editEnabled` in the manifest.

## How to debug a silent "SCRIPT ERROR" in the future
Use the Fusion MCP to run the module in the live process and print the real
traceback:
```python
import sys, importlib, traceback
sys.path.insert(0, r'C:/Users/andre/Projects/Fusion360-Splinegenerator')
m = importlib.import_module('Fusion360-Splinegenerator')
importlib.reload(m)
print(m.run('ctx'))   # True = OK; if False, reproduce run() body inline
```
