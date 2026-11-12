# v0.1.4 — Add one lock-report binary sensor

Adds exactly one read-only binary sensor named **Front door lock** with Home Assistant device class `lock`:

- **off = Locked**
- **on = Unlocked**
- **unknown** until a recognized report is available

It projects the existing **Last reported lock state**. All existing sensors/events, entity unique IDs, decoder, subscriptions, OAuth and persistence behavior are unchanged. No new polling, timers, services or device commands. A saved report is restored after reload; cloud disconnection does not turn an old report into a fresh one. `observed_at`, cloud connection and a last-observation warning are exposed as attributes.

## NeonPlan3D

After installing the update and following your manager's restart requirement, open the Lockin device page and find **Front door lock** under binary sensors. Choose its generated entity ID in your door binding if supported. If used as a contact-sensor input, the display represents **unlocked/locked**, not actual physical door open/closed. NeonPlan3D rendering has not been live-verified; do not use this as a security-grade door-contact substitute.

## Verification and limits

118 offline tests exercise real HA entities with mocked cloud transport, including binary unknown/on/off mapping, ignored door-condition and interior-lock reports, retained disconnect state, stable reload identity, restoration and unload cleanup. Existing sensor/event tests remain passing. See the generated test and smoke reports for exact scope. No live HA installation, restart, lock operation or NeonPlan3D modification was performed for publication.

The earlier isolated token-exchange evidence belongs to v0.1.3, whose OAuth code is unchanged here; no new live authorization test was performed. Full standalone HA device/MQTT validation remains outstanding.

## Update and rollback

Refresh the custom repository, download **v0.1.4**, and follow HACS/Marketplace's restart requirement. A required Core restart briefly interrupts automations/entity availability. Existing integrations and automations should remain in place.

Rollback by selecting **v0.1.3** and following its restart requirement. The new binary sensor is then no longer supplied; existing sensors/events remain. No storage/config-entry schema migration occurs. Public release copies cannot be recalled.
