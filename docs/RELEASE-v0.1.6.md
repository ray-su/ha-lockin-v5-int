# v0.1.6 — App-correlated activity descriptions

Read-only readability update for Lockin V5 Max INT only. No entity additions/removals, identity changes, control features or new polling.

## Changes

- Add `app_description` attributes to matched lock reports: **Door closed report**, **Inside-handle opening**, **Fingerprint unlock**, **Face unlock**, **Palm recognition unlock**.
- Preserve Locked/Unlocked states, existing lock summaries, entity names/IDs and event types. The NeonPlan3D-compatible binary sensor retains its door class and mapping (on/Open=Unlocked, off/Closed=Locked).
- Visitor display wording becomes **Someone appeared at the door**; its event type remains `passed_by`. Automations relying on exact display text rather than event type may need adjustment.
- Preserve legacy deduplication identities: description additions do not re-emit previously seen reports after upgrade. New attributes appear on subsequent matching reports; old history is not rewritten.

## Evidence and limits

Private comparison of app activity screenshots and recorded Xiaomi reports corroborated fingerprint method 2, face method 5, palm method 7 and selected inside-handle/closed/visitor/doorbell correspondences. Selected matching events were also recorded by the standalone integration. This verifies live delivery for those examples, not full coverage or reliability. Public tests use synthetic inputs, not household activity.

“Door closed report” is an app-correlated description, not an independent physical contact measurement. No person names are inferred or imported; unverified firmware diagnostics remain undecoded. Photos, names, credentials, activity timestamps and credential IDs are excluded from publication.

125 offline tests on HA 2026.10.4 plus independent HA 2026.11.1 setup/error smoke checks. Full pytest coverage on HA 2026.11.1 and live NeonPlan3D rendering are not claimed.

## Update / rollback

Refresh the repository and download **v0.1.6** through HACS/Marketplace; follow its restart requirement. Any required Core restart briefly interrupts HA automations/entity availability. No live HA install/restart or new authorization was performed during publication.

Rollback by selecting **v0.1.5** and following its restart requirement. Prior visitor wording returns for future reports; previously persisted description attributes may remain until replaced. No config-entry/observation-store schema migration. Existing binary/sensor/event entities remain. Public copies cannot be recalled.
