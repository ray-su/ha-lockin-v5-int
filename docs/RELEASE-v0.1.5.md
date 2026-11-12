# v0.1.5 — NeonPlan3D Contact compatibility

Changes only the existing **Front door lock** binary sensor's device class from `lock` to `door`. No new entities, controls, polling or timers. Name, unique ID, existing entity ID and state mapping are preserved. All original sensors/events, decoder, runtime, OAuth and storage behavior remain unchanged.

## Mapping

- **Closed / off = last reported Locked**
- **Open / on = last reported Unlocked**
- **Unknown = no recognized report available**

This is deliberately a visualization proxy. **Unlocked is not proof that the physical door is open.** Retained reports may be stale; observation metadata and the warning remain on the entity.

## Use in NeonPlan3D

Update to **v0.1.5** through HACS/Marketplace and follow its restart requirement. A required Core restart briefly interrupts HA automations and entity availability. Then reopen the door editor and select **Front door lock** under **Contact**, not Smart lock. Its `door` class matches the inspected Contact selector's filter. Live rendering still needs user confirmation. No live HA installation, restart or NeonPlan3D edit was performed during publication.

## Checks and rollback

118 offline tests pass, including real HA entity classification, the inspected picker eligibility rule, on/off/unknown mapping, restoration and unchanged original sensor behavior. Independent HA 2026.11.1 setup/error smoke and dependency checks are recorded separately; the full suite runs on HA 2026.10.4. No new live OAuth/device test was performed.

Rollback: install **v0.1.4** and follow its restart requirement. This restores the binary sensor's `lock` class and its exclusion from the Contact selector. No config-entry or observation-store migration occurs. Earlier releases remain available; public copies cannot be recalled.
