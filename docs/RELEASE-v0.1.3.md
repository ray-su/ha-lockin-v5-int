# v0.1.3 — OAuth compatibility correction

Experimental, unofficial, read-only integration for **Lockin V5 Max INT (`loock.lock.v2203`) only**.

## Changes

- Preserve the pinned upstream transport's `v0.5.0` User-Agent version rather than substituting the independent Lockin release number.
- Supply HA system metadata and use the SDK-derived OAuth state and decimal callback-identifier convention.
- Retain the OAuth client from login URL generation through token exchange; close it on completion, abort or expiry.
- Preserve constant-time callback-state validation, local-only delivery, expiry and safe stage-specific diagnostics; explicitly reject callback replay.
- No actuator capabilities, decoder changes, config-entry migration or observation-store migration.

## Verification

- **Real isolated candidate token exchange: HTTP 200 / API code 0**, required token fields present. The test used the actual candidate login initialization and token client on a Mac, not the user's HA VM.
- The preceding same-Mac comparison succeeded with upstream-style defaults and failed with v0.1.2-style defaults (API -6). Several compatibility conventions changed together; this does not identify one causal field or rule out provider variability.
- **115 offline tests** on HA 2026.10.4, lint and independent fresh HA 2026.11.1 setup/callback/error smoke checks.
- Tokens stayed in memory and were discarded; no HA storage, device discovery/control, refresh or revocation. Temporary listener shutdown was verified. Discarding local tokens does not revoke vendor-side authorization.

**Not yet verified:** complete setup, device discovery and MQTT/event delivery on the HA host. Keep the existing integration and automations until those work. Full pytest coverage on HA 2026.11.1 is not claimed; see [testing scope](TESTING.md).

## Update

Refresh this custom repository's release information in HACS/Marketplace, download **v0.1.3**, and follow the manager's restart requirement. Then begin a fresh Lockin setup flow. Do not reuse an earlier authorization URL/code or edit the original redirect_uri. Share only safe diagnostic text if a later stage fails.

No live HA installation, restart, networking change or automation migration was performed as part of publication. An update restart, if required, briefly interrupts HA automations and entity availability; the physical lock continues independently.

## Rollback

Select **v0.1.2** in the manager and follow its restart requirement. Its safe diagnostics/dependency correction remain, but the previous OAuth failure may return. The old release/tag is retained. Removing the standalone integration does not remove another integration or alter lock enrollment. Public copies of a published release cannot be recalled.
