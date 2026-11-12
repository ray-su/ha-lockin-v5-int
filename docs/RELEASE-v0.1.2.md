# v0.1.2 — privacy-safe setup diagnostics

**Experimental diagnostic release, not a verified fix for live authorization.** Only Lockin V5 Max INT (`loock.lock.v2203`), read-only.

## Changes

- Replace the generic post-callback failure with the failing stage: **token exchange** or **device discovery**.
- Show only a fixed error category and validated numeric HTTP/cloud API codes when available. Raw exception messages, response bodies, authorization URLs, tokens and account data are excluded from the displayed/logged diagnostic summary.
- Retain safe status metadata in the vendored OAuth/HTTP error paths. Preserve authentication-error classifications and the v0.1.1 dependency correction.
- Document first-install versus update restart behavior and the distinction between changing the final callback hostname after consent and editing the original OAuth redirect parameter.
- No changes to account grants, registered OAuth origin, device controls, decoding, observation storage format, or existing config entries. No automatic retries or monitoring.

## Validation

- **111 tests passed** on Python 3.14 / HA 2026.10.4, with external connections blocked; Ruff passed.
- Independent fresh **HA 2026.11.1** bootstrap: initial authenticated setup HTTP 200, actual local webhook callback, both forced error stages, safe abort responses, English message formatting, and cleanup verified. Cloud methods and credentials are synthetic; no real account/device was contacted.
- Full test-harness coverage on HA 2026.11.1 is not claimed. See [testing scope](TESTING.md) and the published execution reports.
- The smoke bootstrap explicitly loads HA's webhook component, normally supplied by `default_config`; minimal custom configurations without it are not covered.

## Update and report

1. Refresh this repository's release information in HACS/Marketplace if needed, then install **v0.1.2**.
2. Back up first and follow the manager's restart requirement. First installation can legitimately omit a restart prompt; already loaded code may require a Core restart, briefly interrupting automations.
3. Start a fresh setup attempt. If it fails, share **only the new diagnostic text**. Do not share the login/callback URL, authorization code, token, or raw logs.
4. Keep the existing Xiaomi Home integration until standalone authorization and reporting are actually verified.

Publication does not install this release, restart HA, or authorize an account. To roll back, reinstall **v0.1.1** through the manager's version selection and follow its restart requirement; no storage migration is introduced. The previous release remains available. The upstream non-commercial Home Assistant license and notices are unchanged.
