# [DONE] Resolve Dependabot Alert #20 — Tornado DoS (CVE-2026-31958)

## Context

Dependabot alert #20 reports a high-severity denial-of-service vulnerability in Tornado's `multipart/form-data` parsing:

* Advisory: `GHSA-qjxf-f2mg-c6mc`
* CVE: `CVE-2026-31958`
* Vulnerable versions: `<= 6.5.4`
* First patched version: `6.5.5`

The repository currently resolves:

```text
python-telegram-bot 13.15
└── tornado == 6.1
```

`python-telegram-bot` 13.15 declares an exact `tornado==6.1` dependency, so a normal dependency upgrade cannot select the patched release.

The bot currently starts through `Updater.start_polling()` and is not expected to expose Tornado's HTTP or multipart-parsing path. Exploitability is therefore believed to be negligible, but this assumption must be preserved as a tested or otherwise executable contract rather than relied upon informally.

## Remediation strategy

Use a bounded uv dependency override:

```toml
[tool.uv]
# PTB 13.15 pins tornado==6.1. This bot uses polling rather than PTB's
# Tornado-based webhook server. Remove this override after migrating PTB.
override-dependencies = ["tornado>=6.5.5,<7"]
```

The `<7` upper bound is intentional. It removes the vulnerable Tornado releases without silently allowing a future major version that PTB 13.15 was never designed to support.

This is an explicit override of upstream package metadata. It is acceptable only while the bot remains polling-only and the compatibility checks below remain green.

---

## Cycle 1 — Characterize the Polling-Only Runtime Contract [DONE]

### Goal

Establish evidence that normal bot startup uses polling and does not start PTB's Tornado webhook server.

### Scope

* `bot/stickfix.py`
* Existing startup tests or a narrowly scoped new test
* Deployment and configuration references related to webhook startup

Do not change transport behavior.

### Red

Add a BDD-style characterization test:

> Given a configured Stickfix bot, when its startup entry point runs, then polling is started and webhook startup is never requested.

The test should verify, where practical:

* `start_polling()` is invoked exactly once.
* `start_webhook()` is not invoked.
* Startup does not bind an HTTP listening port.

If the existing design does not expose a practical test seam, the initial test may fail because startup dependencies cannot be substituted safely.

If the test passes against existing code immediately, retain it as a characterization test; do not manufacture a production change solely to force a red state.

Also perform a repository search for webhook-related entry points and deployment configuration, including references such as:

```text
start_webhook
webhook_url
listen
cert
key
```

Search results must be reviewed rather than treated as proof by keyword absence alone.

### Green

If required, introduce the smallest behavior-preserving seam needed to test startup, such as extracting a short function that receives an already-constructed `Updater`.

Do not redesign the application bootstrap or dependency-injection architecture as part of this alert fix.

### Refactor

* Keep the startup seam narrowly focused and under approximately 25 lines.
* Reuse existing fixtures or mocks.
* Avoid duplicating updater construction logic.
* Remove any test setup that performs real Telegram or network requests.

### Acceptance criteria

* The startup characterization test passes.
* The test would fail if `start_polling()` were replaced by `start_webhook()`.
* No active application or deployment path starts a webhook server.
* Existing startup behavior remains unchanged.

### Non-goals

* Supporting webhook mode.
* Refactoring the complete bot bootstrap.
* Replacing `Updater`.
* Changing Telegram API behavior.

### Suggested execution order

Execute first so the justification for the override is recorded before changing the dependency graph.

### Status — ✅ Done (2026-06-21)

* **Seam:** Extracted module-level `start_polling_service(updater, logger)` in `bot/stickfix.py`; `Stickfix.run()` now delegates to it. The public entry point `Stickfix(token).run()` is unchanged, so `README.md`, `AGENTS.md`, and `ARCHITECTURE-PORTS-ANALYSIS.md` remain accurate.
* **Test:** Added `tests/test_startup_contract.py` with two BDD-style characterization tests:
  * `start_polling_service` invokes `start_polling()` exactly once and never `start_webhook()`.
  * `Stickfix.run()` (constructed via `__new__` to bypass the heavy constructor — no Telegram/network/filesystem) delegates to polling only and never binds a listener.
  * The tests would fail if `start_polling()` were swapped for `start_webhook()`.
* **Repository search:** `start_webhook`, `webhook_url`, `listen`, `cert`, `key` — the only transport call site in `bot/` is `start_polling()` in `bot/stickfix.py`. No webhook entry point or deployment config exists.
* **Result:** Full suite green (`uv run pytest` → 121 passed). Polling-only contract is now executable evidence, justifying the Cycle 2 override.

---

## Cycle 2 — Enforce the Patched Tornado Constraint [DONE]

### Goal

Replace the vulnerable locked Tornado version with a patched 6.x release and prevent accidental regression to the vulnerable range.

### Scope

* `pyproject.toml`
* `uv.lock`
* A dependency-policy test or equivalent executable assertion

### Red

Add an executable dependency security check with the BDD contract:

> Given the resolved runtime environment, when the Tornado version is inspected, then it is at least 6.5.5 and remains below 7.0.

Before applying the override, confirm that the check fails because Tornado 6.1 is resolved.

Prefer the repository's existing dependency-policy testing mechanism if one exists. Otherwise, use a small test based on `importlib.metadata.version("tornado")` or a lockfile assertion without introducing a substantial testing framework solely for this check.

DDT and PBT are not justified here: there is one dependency and one patched-version boundary.

### Green

1. Add the bounded override to `pyproject.toml`:

   ```toml
   [tool.uv]
   override-dependencies = ["tornado>=6.5.5,<7"]
   ```

   If `[tool.uv]` already exists, extend it rather than creating a duplicate table.

2. Include a concise comment documenting:

   * Why the PTB pin is being overridden.
   * Why polling makes the affected server path unreachable.
   * That the override should be removed during a future PTB migration.

3. Regenerate the lockfile through uv:

   ```shell
   uv lock --upgrade-package tornado
   ```

4. Do not hand-edit `uv.lock`.

5. Re-run the dependency security check.

### Refactor

* Keep any dependency lookup helper generic enough to inspect another locked package later.
* Do not add abstraction layers if the repository has no other dependency-policy tests.
* Review the generated lockfile diff and remove no transitive packages manually.

### Acceptance criteria

* `uv.lock` resolves exactly one Tornado package.
* The locked Tornado version satisfies `>=6.5.5,<7`.
* `python-telegram-bot` remains at 13.15.
* No unrelated direct dependency is upgraded unless uv requires it for a valid resolution.
* The dependency security check changes from failing to passing.
* A fresh lock operation produces no unexpected dependency churn.

### Non-goals

* Upgrading `python-telegram-bot`.
* Allowing Tornado 7.x.
* Editing third-party package metadata or installed files.
* Suppressing the Dependabot alert without first attempting the patched dependency.

### Suggested execution order

Execute after the polling-only contract is established.

### Status — ✅ Done (2026-06-21)

* **Override:** Added `[tool.uv]` with `override-dependencies = ["tornado>=6.5.5,<7"]` and a concise comment documenting the PTB 13.15 pin, Stickfix's polling-only runtime, and removal during a future PTB migration.
* **Lockfile:** Regenerated `uv.lock` with `uv lock --upgrade-package tornado`. The lock now contains exactly one Tornado package at `6.5.7`, and `python-telegram-bot` remains at `13.15`.
* **Test:** Added `tests/test_dependency_policy.py`, covering the installed Tornado version boundary and the committed lockfile boundary `>=6.5.5,<7`.
* **Result:** `uv run pytest tests/test_dependency_policy.py` passes.

---

## Cycle 3 — Prove Compatibility and Decide the Rollout Path [DONE]

### Goal

Verify that the upstream-pin override remains compatible with Stickfix's actual runtime and establish an explicit fallback if it does not.

### Scope

* Environment synchronization
* Import compatibility
* Automated test suite
* Polling startup smoke coverage
* Dependabot post-push verification

### Red

Treat any failure in the following gates as the red state:

```shell
uv sync --locked --extra dev
uv run python -c "import telegram.ext; import tornado; print(tornado.version)"
uv run pytest
```

Also run the polling-only characterization test independently when the suite supports targeted execution.

No real Telegram connection or production token should be required.

### Green

Resolve only failures directly caused by the dependency override.

Permitted fixes include:

* Updating a test double that incorrectly depends on Tornado 6.1 internals.
* Adjusting an import-only compatibility check.
* Correcting the uv configuration or lock regeneration.

If PTB polling or bot startup is genuinely incompatible with patched Tornado, do not patch PTB internals or widen the scope into a framework migration. Revert the override and use the documented dismissal fallback.

### Refactor

* Remove temporary diagnostic code.
* Keep the final compatibility coverage focused on observable bot behavior.
* Ensure comments describe why the override exists, not a detailed history of the debugging process.

### Acceptance criteria

All local merge gates pass:

* `uv sync --locked --extra dev` succeeds from the committed lockfile.
* `telegram.ext` and Tornado import successfully in the synchronized environment.
* The reported Tornado version satisfies `>=6.5.5,<7`.
* The full test suite passes.
* The bot's polling startup contract remains green.
* No webhook server is started.
* The final diff contains only intentional source, test, configuration, and generated lockfile changes.

After pushing:

* Verify that Dependabot alert #20 closes or is marked fixed.
* Treat alert closure as post-push verification, not as a deterministic local test.
* If GitHub does not close it despite the patched lockfile, inspect the dependency path reported by Dependabot before making further changes.

### Fallback decision

If the override cannot be resolved or fails runtime compatibility:

1. Revert the override and regenerated lockfile.
2. Retain the polling-only characterization evidence.
3. Dismiss alert #20 as **“Vulnerable code is not actually used.”**
4. Record that:

   * Stickfix uses polling.
   * No Tornado HTTP server is started.
   * The vulnerable multipart parser is not reachable through the deployed bot.
5. Open a separate migration issue for upgrading to a supported modern `python-telegram-bot` release.

Do not combine that migration with this security-alert fix.

### Non-goals

* Migrating to `python-telegram-bot` 20+ or 21+.
* Rewriting handlers for PTB's async API.
* Replacing PTB with another Telegram framework.
* Adding webhook support.
* Broad dependency modernization.

### Suggested execution order

Execute last. Merge the override only if all local compatibility gates pass.

### Status — ✅ Done (2026-06-21)

**Rollout decision: keep the override.** All local compatibility gates passed, so
the documented dismissal fallback was not required.

* **Environment sync:** `uv sync --locked --extra dev` succeeds from the committed
  lockfile. (The in-place `.venv` could not be recreated because a system Python
  patch bump, 3.14.3 → 3.14.5, made uv want to rebuild it while editor language
  servers held the directory; the gates were therefore run in an isolated,
  throwaway environment via `UV_PROJECT_ENVIRONMENT`, which is the same locked
  resolution. The temporary environment was deleted afterward — no working-tree
  artifacts remain.)
* **Imports:** `import telegram.ext; import tornado` both succeed; reported
  `tornado.version == 6.5.7`, satisfying `>=6.5.5,<7`. The only warnings are the
  pre-existing PTB-on-upstream-urllib3 and apscheduler `pkg_resources` notices,
  unrelated to this override.
* **Tests:** `uv run pytest` → **123 passed**. The targeted gates
  `tests/test_startup_contract.py` and `tests/test_dependency_policy.py` →
  **4 passed**; polling-only startup and the Tornado version boundary both remain
  green. No webhook server is started.
* **Diff:** The final working tree contains only intentional source, test,
  configuration, and generated lockfile changes — no temporary diagnostic code.
* **Post-push verification (pending):** After this branch is pushed/merged,
  confirm Dependabot alert #20 closes against the patched lockfile. If GitHub
  does not close it, inspect the dependency path Dependabot reports before making
  further changes — treat closure as post-push verification, not a local test.

---

## Final acceptance criteria

The remediation is complete when:

1. ✅ Polling-only startup is covered by an executable characterization test or equivalent repository-level verification. (`tests/test_startup_contract.py`)
2. ✅ `pyproject.toml` contains the documented bounded override `tornado>=6.5.5,<7`.
3. ✅ `uv.lock` is regenerated by uv and contains a patched Tornado release. (`tornado==6.5.7`)
4. ✅ A synchronized environment imports PTB and Tornado successfully.
5. ✅ The complete automated test suite passes. (123 passed)
6. ✅ No production behavior has intentionally changed.
7. ⏳ Dependabot alert #20 is verified as closed after the updated lockfile is pushed. (pending push/merge)

If compatibility fails, the accepted outcome is the documented alert dismissal plus a separate PTB migration issue—not an increasingly broad override or an unplanned framework migration.

