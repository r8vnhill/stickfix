# Application package guidance for AI agents

This file adds package-specific instructions to the repository's root `AGENTS.md`.
Follow the root collaboration rule first: present meaningful alternatives, explain tradeoffs,
and obtain maintainer approval before changing architecture, dependencies, or production
semantics. Keep code, tests, and documentation in English.

## Scope and dependency boundary

- The application package owns DTOs, use cases, errors, and explicit ports.
- Runtime storage is PostgreSQL in `bot/infrastructure/persistence/postgres/`; it does not
  belong here. Historical YAML access is migration-only.
- The application uses Expression `Option[StickfixUser]` at repository read boundaries.
  `Nothing` represents absence, and `Some` contains a detached aggregate.
- The domain must remain independent of Expression, Telegram, and persistence infrastructure.
- Do not make application tests import SQLAlchemy or runtime adapters to obtain shared helpers.
- Retain the project's two-space Python indentation and Ruff configuration, even when generic
  recommendations suggest four spaces.

## Repository-fake rules

Files: `tests/support/repositories.py`, `tests/test_repository_fakes.py`, and
`tests/test_repository_fake_fidelity.py`.

1. Arrange state with `save_user()` / `save()`. `ensure()` does not persist public state.
2. Read state using `get_user()` / `get()` and inspect `Option`; use fresh reads for
   persistence assertions. Do not inspect or mutate `_users`, `_stickers`, or `_cached_stickers`.
3. Save-history lists are **observations**, not storage. Clear them only at a known fixture
   boundary when a scenario must count subsequent write calls.
4. Model stored user fields explicitly: ID, `private_mode`, `shuffle`, sticker associations,
   and cached associations. Do not silently persist arbitrary dynamic attributes.
5. Omit empty association lists on storage round trips. Retain ordering within a tag; do not
   assume ordering across unrelated tags or promise deterministic set-derived sticker order.
6. Reject unsupported or repeated sticker IDs before changing fake state. PostgreSQL error
   classes can differ; do not claim identical exceptions without a documented contract.
7. Keep public `get()` empty when no sticker/cache association exists, even after `ensure()` or
   an empty `save()`; persisted public reads always use `SF_PUBLIC`.
8. Keep fake functions focused and avoid introducing a general repository framework or new
   dependencies merely for test setup.

## Test-first workflow

- **Red:** identify one measurable difference between a fake and the existing port/backend;
  write a BDD-style example or small data-driven case that demonstrates it.
- **Green:** make the smallest coherent change to restore contract fidelity; preserve runtime
  use-case behavior and expected Telegram/logging results.
- **Refactor:** reduce repetition without hiding explicit persistence boundaries.
- Run `uv run --locked pytest packages/stickfix-application/tests -v` and the repository's
  required lock, Ruff, architecture, and full pytest checks from root `AGENTS.md`.
- For PostgreSQL confirmation, consult the opt-in contract suite and use only a disposable
  database. A skipped PostgreSQL test is not evidence of successful integration.

## Review and reporting checklist

Before presenting a patch, state which observations are confirmed by repository sources,
which are newly proposed conventions, and which tests actually ran. Document assumptions
where database ordering, exceptions, or normalization semantics are not portable.

Keep modifications to production ports/use cases, dependency declarations, and extraction
milestones outside a test-fake refactor unless the maintainer approves them. Update the
package README, support README, and root contributor guidance when the fake contract changes.
