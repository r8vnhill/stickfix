# `stickfix-application`

`stickfix-application` owns transport-neutral request/result DTOs, application errors,
repository/help ports, and command/query use cases. It depends on `stickfix-domain` and
Expression, but never on Telegram handlers, SQLAlchemy, PostgreSQL adapters, or migration code.

## Ownership and public contracts

| Area | Responsibility | Stability expectation |
|---|---|---|
| `requests` / `results` | Frozen adapter-facing DTOs | Preserve supported fields and meanings |
| `errors` | Application failures translated by handlers | Preserve user-visible behavior |
| `ports` | Narrow `Protocol` interfaces | Preserve `Option` absence and save semantics |
| `use_cases` | Transport-neutral orchestration | Preserve reply data, exceptions, and logging |
| `tests/support` | Test-only repository fakes | Must follow the production contracts |

The application `__all__` and ports' `__all__` are deliberately small. Update downstream
callers and existing architecture tests when an approved change affects their contracts.
`tests/test_application_seam.py` checks structural conformance and import isolation.

## Repository contract

`UserRepository` stores regular users identified by numeric `UserId` values.
`PublicPackRepository` owns the shared pack identified by `SF_PUBLIC` and does not model it
as a regular user. The PostgreSQL runtime adapter implements both ports; the application
must not assume that the ports share a concrete adapter.

Both repository read methods use Expression's `Option[StickfixUser]`:

- `Some(user)` contains a **detached** mutable aggregate; modifying it does not persist changes.
- `Nothing` means no stored regular user or no stored public sticker/cache associations.
- `ensure()` returns a usable public pack but **does not save it** when no associations exist.
- `save_user()` and `save()` are the only supported persistence operations for aggregates.
- `has_user()` and `delete_user()` belong to the regular-user repository only.

For example, the following test setup creates stored public associations:

```python
from stickfix_domain import SF_PUBLIC
from support.repositories import InMemoryPublicPackRepository

public = InMemoryPublicPackRepository()
pack = public.ensure()
assert pack.id == SF_PUBLIC
pack.add_sticker("sticker-1", ["wave"])
public.save(pack)
assert public.get().some.stickers == {"wave": ["sticker-1"]}
```

A fresh `get()` returns a detached snapshot, not the original object. Application use cases
resolve `Option` at their boundaries; domain services still operate on ordinary aggregates.
Do not replace `Option` with `None` or import Expression into the domain package without an
approved contract change.

## In-memory test doubles

`tests/support/repositories.py` deliberately models the **observable persistence boundary**,
not SQLAlchemy or PostgreSQL internals. It reconstructs only regular-user fields stored by
the current database mapping, normalizes preference values to booleans, and retains within-tag
association order. Both regular-user and public-pack saves omit tag lists containing no
sticker IDs, because those lists do not create association rows in PostgreSQL.

The fakes reject unsupported sticker identifiers and duplicate IDs within a single tag before
changing their stored state. These failures are local diagnostics (`ValueError`); the database
may report constraint errors under different exception classes. Avoid asserting matching error
classes across adapters unless the port explicitly standardizes them.

The lists `saved_users` and `saved_packs` hold independent copies of **save call observations**.
They are not the source of stored state and are not production port methods. Their entries may
be used to check whether a use case saved the intended aggregate; use fresh reads to check
what persisted. Clear histories **only during fixture arrangement** when a test intentionally
wants to count later saves. Avoid modifying private storage or relying on object identity.

For more examples, limitations, and a test matrix, see
[`tests/support/README.md`](tests/support/README.md).

## Testing and verification

From the workspace root:

```bash
uv lock --check
uv sync --all-packages --locked
uv run --locked pytest packages/stickfix-application/tests/test_repository_fakes.py -v
uv run --locked pytest packages/stickfix-application/tests/test_repository_fake_fidelity.py -v
uv run --locked pytest packages/stickfix-application/tests -v
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
```

The PostgreSQL counterpart lives in
`tests/infrastructure/persistence/test_postgres_repository_contract.py`. It is opt-in and
**truncates the explicitly configured test database**. Only configure
`STICKFIX_TEST_DATABASE_URL` for a disposable database; skipped integration tests do not prove
PostgreSQL conformance. Prefer focused BDD-style examples and a small data-driven matrix for
these contracts. Broader state-machine/property testing is deferred until behavior complexity
justifies it.

## Maintainers and AI agents

Read the repository root [`AGENTS.md`](../../AGENTS.md), this package's
[`AGENTS.md`](AGENTS.md), and the root [`CONTRIBUTING.md`](../../CONTRIBUTING.md) before
changing the application seam. Follow the workspace's two-space Python indentation, its
configured Ruff checks, locked dependency workflow, and current extraction plan.

The repository fakes and their tests are **test-only**. They must not become runtime adapters,
introduce infrastructure imports into this package, or replace the real PostgreSQL
integration contract suite. When behavior differs across adapters, characterize both before
proposing a production change; preserve existing command behavior unless explicitly approved.
