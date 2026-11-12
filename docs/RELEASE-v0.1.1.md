# v0.1.1 — Home Assistant dependency compatibility fix

Experimental, read-only, single-model integration for `loock.lock.v2203`.

## Fix

Remove the redundant `python-slugify==9.1.2` requirement and let Home Assistant provide its own required version. HA 2026.11.1 requires 9.1.3, so the old pin is incompatible and can prevent setup. No OAuth, device-control, network, credential, or decoder behavior is changed.

## Verification

- 74 tests pass on the HA 2026.10.4 full-suite baseline, including new dependency and setup-HTTP regression tests.
- A fresh isolated HA 2026.11.1 instance returns HTTP 200 and the region form from the authenticated setup endpoint, without using the older pytest HA harness.
- Actual dependency resolution succeeds with the corrected manifest against both Core versions; the removed pin reproduces the 2026.11.1 conflict.
- The full suite is not claimed on 2026.11.1 because the available harness targets 2026.10.4. See `docs/TESTING.md` and generated reports for the exact scope.
- Live standalone OAuth, MQTT delivery, and resolution of any additional live setup error remain unverified.

## Update

In HACS, refresh this custom repository if needed, then download v0.1.1. Back up HA and restart **Home Assistant Core** before retrying setup. Restarting briefly interrupts HA automations and entity availability; it does not change the lock's standalone operation. Keep the existing integration.

Do not manually downgrade HA's Python packages. If setup still errors, copy the relevant traceback from **Settings → System → Logs**, removing secrets and authorization URLs.

v0.1.0 remains unchanged but retains the known compatibility defect. Roll back by removing this new integration and restarting Core, leaving the original integration in place, or restore your backup. This release performs no data migration and changes no enrolled credentials or device settings.
