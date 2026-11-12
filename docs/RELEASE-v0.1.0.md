# v0.1.0 — experimental read-only release

Single-model Home Assistant integration for **Lockin V5 Max INT (`loock.lock.v2203`)**.

- Standalone authorization and cloud transport; no dependency on another integration's entities.
- Readable lock/unlock, method/side, warning, battery and doorbell/visitor observations.
- Fingerprint method decoding; conservative Palm recognition wording until a palm-vein event is verified.
- Retained last observations with separate connectivity and timestamped-event duplicate suppression.
- No device controls, biometric payloads, automatic name inference, or enrolment changes.
- HACS custom-repository metadata and original neutral brand icon.

## Install

Add `https://github.com/ray-su/ha-lockin-v5-int` to **HACS → Custom repositories**, type **Integration**, then download **Lockin V5 Max INT**. Back up HA before restarting Core and adding the integration. Minimum HA version: **2026.10.4**.

**Keep the existing integration until a normal user-operated comparison succeeds.** Fresh live authorization/event delivery through this standalone build is unverified; automated tests are offline. This is not a production-reliability or physical-security guarantee.

Read the README for callback prerequisites, limitations and rollback. Upstream non-commercial Home Assistant licensing is preserved. This is not a default HACS catalogue listing.
