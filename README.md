# Lockin V5 Max INT for Home Assistant

**v0.1.0 · experimental · read-only · only `loock.lock.v2203`**

A standalone, single-model integration that turns cryptic lock reports into readable Home Assistant sensors and events. No existing integration is required for runtime operation. This project is unofficial and is not endorsed by the device or cloud vendor.

> **Test candidate, not a verified live migration.** The decoder and Home Assistant lifecycle are tested locally with networking disabled. Fresh authorization and event delivery through this standalone integration still need live verification. Keep your existing integration until comparison succeeds.

## Install with HACS

Requires **Home Assistant 2026.10.4 or later** and an existing HACS installation. This is a **custom repository**, not a default HACS catalogue entry.

1. In **HACS → ⋮ → Custom repositories**, add:
   ```text
   https://github.com/ray-su/ha-lockin-v5-int
   ```
2. Select type **Integration**, then **Add**.
3. Find **Lockin V5 Max INT**, open it, and download it.
4. Back up your HA configuration before restarting **Home Assistant Core**. Restarting briefly interrupts automations and entity availability; it does not change the lock's standalone operation.
5. Go to **Settings → Devices & services → Add integration → Lockin V5 Max INT**.
6. Select the account's actual region and complete authorization in your browser. Only `loock.lock.v2203` devices are selectable.
7. Keep the existing integration and automations untouched. Compare reports during normal, user-operated use before migrating references.

**Authorization callback:** the upstream registered callback origin is `http://homeassistant.local:8123`; it must resolve to this HA instance from your browser. Do not expose HA publicly, weaken TLS, or change DNS/proxy rules just to make setup work. The setup link expires after ten minutes; after authorization, return to the flow and press Submit. Never share login URLs, codes, or tokens.

**Manual alternative:** copy `custom_components/lockin_v5/` to `/config/custom_components/lockin_v5/`, then follow the restart/setup steps above. Do not overwrite another integration.

**Rollback:** remove the new config entry, remove this integration through HACS (or delete only `/config/custom_components/lockin_v5/` for a manual installation), and restart Core. Its own observation store is removed when its config entry is removed. Leave/re-enable the old integration; restore your backup if needed. No device settings or enrolled credentials are changed.

## Readable reports

| Input | Example display |
|---|---|
| Unlock, face, outside | **Unlocked — face recognition — outside** |
| Unlock, fingerprint, outside | **Unlocked — fingerprint — outside** |
| Lock, manual | **Locked — manual operation** |
| Warning 24 / 23 | **Door ajar** / **Door left open too long** |
| Battery-presence code 3 | **Both batteries installed** |
| Offline device/cloud | Connectivity shown separately; last observations retained |

Entities include last lock activity/operation, last reported lock state, last access method/side/time, last unlock, last warning, door-condition report, two battery percentages, battery/USB presence, doorbell/visitor observations, and connectivity diagnostics. Event entities allow repeated operations of the same type to trigger automations.

There are **no lock, switch, button or other actuator platforms**, and no device-control services. The adapter rejects property writes and actions. Camera streaming, credential enrolment, remote unlocking, and automatic person-name import are not implemented.

### Fingerprint, face and palm vein

- A user-labelled fingerprint use was received by an existing integration as standard event `2/1020`: method `2`, action `2`, side `2`. This standalone decoder recognises it. That verifies the source event's meaning, **not this new integration's live connection**.
- Face recognition is method `5`; fingerprint and face reports can carry different credential identifiers. Mi Home's user-name/Owner label is resolved separately, not included in the standard event. This version does not expose credential IDs or infer who entered.
- The [V5 Max INT manual](https://www.lockin.com.hk/wp-content/uploads/2024/02/V5-Max-User-Manual_en-1.pdf) documents both palm-vein and handle-fingerprint readers. The generic MIoT specification calls method `7` “Palm Print” and method `6` “Finger Vein”. Method `7` is conservatively displayed as **Palm recognition**; the exact palm-vein-to-code mapping still needs a user-labelled live sample. Raw method codes remain in lock-event attributes.
- BLE-specific event `12/1023` documents fingerprint success/failure, but was not observed during the known successful fingerprint use. It is not required for decoding standard fingerprint unlocks and remains an unmapped diagnostic here.

## Important limitations

- **Last reported is not guaranteed current.** Cloud outages or missed reports cannot be repaired by treating cached observations as fresh. Do not rely on this integration as your only security or life-safety signal.
- Unlock does **not** mean the physical door opened. The door-state property can remain Locked across an unlock; it is kept separate from operation-derived lock state. Warnings are historical, not a continuous door-contact or active-alarm sensor.
- Battery A is service `4/1003`; battery B is `10/1`. Their mapping to the two physical batteries is not verified. Battery/USB presence is not a charging-current measurement.
- An offline report does not prove the lock is asleep. Connectivity and retained observations are deliberately separate.
- Timestamped events use persisted duplicate detection and ordering. Restoration does not emit a fresh event, and events over two minutes old are not emitted as fresh automation events. A crash before a pending save can lose the newest duplicate marker.
- Untimed visitor/low-battery reports have only short-window duplicate suppression. Not every spec-defined visitor/tamper feature is supported by this firmware; some are marked unsupported in model translations. Their presence in the schema is not a live support claim.
- Raw operation/user IDs, face/debug data, video identifiers, stream URLs and cloud credentials are excluded from entity attributes and diagnostic exports. Existing HA history and user-name aliases are not imported.
- Only the INT model `loock.lock.v2203` is supported. Domestic `loock.lock.fcl201` and all other models are rejected. This is cloud-dependent, not a LAN-only integration.

## Testing and development

Test baseline: **Python 3.14 / Home Assistant 2026.10.4**. See [testing](docs/TESTING.md), [actual test output](docs/public-tests.txt), and [release notes](docs/RELEASE-v0.1.0.md).

```sh
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements-test.txt
.venv/bin/python -m pytest -q
.venv/bin/ruff check custom_components/lockin_v5 tests tools
.venv/bin/python tools/build_release.py
```

Tests use synthetic identifiers/credentials and mocked cloud responses, with network sockets disabled. Private histories and development environments are excluded from publication. The optional history replay tool accepts your own authorized export and prints aggregates, not raw identifiers. Do not upload the export or household activity output to an issue.

No installation scripts, CI schedules, monitoring jobs, or automatic device commands are included.

## Provenance and license

Transport reference: [`XiaoMi/ha_xiaomi_home`](https://github.com/XiaoMi/ha_xiaomi_home), pinned commit `75b3acb6325a3a8d295688b13904737d6738a6a5`. Selected OAuth/HTTP/MQTT modules retain their copyright headers and license; local modifications redact sensitive logging and harden malformed-message parsing. The exact model specification comes from [MIoT Spec](https://home.miot-spec.com/spec/loock.lock.v2203).

**The upstream license is restricted to non-commercial Home Assistant use and is not MIT/Apache or an OSI open-source license.** Its attribution, distribution and trademark conditions remain in force; see [LICENSE.md](LICENSE.md). The neutral lock icon is original project artwork, not a vendor logo. This repository does not claim default HACS catalogue eligibility. Report issues to [this repository](https://github.com/ray-su/ha-lockin-v5-int/issues), not the upstream transport project.
