# Repository test doubles — maintainer guide

`repositories.py` provides in-memory fakes implementing application repository ports. Their
purpose is to make missing saves and unsupported persistence assumptions visible in small,
fast tests. They are deliberately not SQLAlchemy/transaction simulators and are not exported
from the published application wheel.

## Observable behavior

| Operation | Regular-user fake | Public-pack fake |
|---|---|---|
| Absent read | `Nothing` | `Nothing` |
| Existing read | `Some` with a detached user | `Some` with detached `SF_PUBLIC` pack |
| Save | Upsert regular user snapshot | Replace saved public associations |
| Empty associations | User persists without them | No retrievable public pack |
| `ensure()` | Not available | Constructs unsaved canonical pack when absent |
| Deletion | `delete_user()` returns existence boolean | Not exposed |
| Observations | `saved_users` | `saved_packs` |

Regular user state is projected to the database-backed fields: numeric ID, the two boolean
preferences, ordered sticker lists, and ordered cached-sticker lists. Attributes attached to
an aggregate for a temporary application purpose do not survive a save/read cycle.

The PostgreSQL adapter stores association **rows**, not empty tag lists. Saving
`{"wave": [], "smile": ["s1"]}` therefore round-trips as `{"smile": ["s1"]}`. This is
true for both regular and public sticker/cache associations. An empty public pack, even one
passed to `save()`, is absent on subsequent reads.

## Arrange, act, assert

```python
from stickfix_domain import StickfixUser, UserId
from support.repositories import InMemoryUserRepository

repository = InMemoryUserRepository()
user = StickfixUser(UserId(1))
repository.save_user(user)  # Arrange persisted state, rather than setting _users.
repository.saved_users.clear()  # Optional: count only saves during the action.

loaded = repository.get_user(UserId(1)).some
loaded.private_mode = True
assert repository.get_user(UserId(1)).some.private_mode is False
repository.save_user(loaded)
assert repository.get_user(UserId(1)).some.private_mode is True
assert len(repository.saved_users) == 1
```

`Option.some` is appropriate after a test explicitly arranged present state; when absence is
possible, assert `is_some()`/`Nothing` before accessing the aggregate. Use `get()` rather than
holding onto an earlier `ensure()` result when asserting persisted public state.

## Observation histories

Each save appends a *detached copy* of the submitted state to a public observation list.
For regular users, the observation is projected to persistable fields; for public packs, it
records the input aggregate. Stored snapshots do not share mutable sticker/cache lists with
observations.
`save()` on an empty public pack still records an invocation even though `get()` is `Nothing`.

Use histories to assert **that saving happened** and to inspect submitted values. Use fresh
reads to assert **what was stored**. Mutating the observation list itself changes the test's
observation record and is not a persistence action.

## Validation and limits

- The regular-user fake matches the runtime ID requirement: an integer other than `bool`.
- Nonempty string sticker IDs and uniqueness within each tag are required for supported
  persistence. The fake raises `ValueError` before changing stored state; the database can
  instead raise an `IntegrityError` for duplicate association rows.
- A failed fake save leaves prior stored state and save observations unchanged.
- The public adapter ignores the supplied aggregate's `id` on persistence and reconstructs
  `SF_PUBLIC` on read. The fake follows this observable behavior, without making the submitted
  identifier a new application-port validation rule.
- The fakes do not reproduce sessions, SQL transactions, cross-tag ordering from database ID
  allocation, foreign-key behavior, or database connectivity failures.
- Save histories are test-only observations; their exact layout is not part of the repository
  `Protocol`s. They do not represent an audit log or durable event history.

## Where to verify

| Concern | Evidence |
|---|---|
| Fake contract | `../test_repository_fakes.py` and `../test_repository_fake_fidelity.py` |
| Application behavior | `../use_cases/` and `../test_application_seam.py` |
| PostgreSQL behavior | Root persistence contract suite |
| Port declarations | `../../src/stickfix_application/ports/` |

Run from the workspace root:

```bash
uv run --locked pytest packages/stickfix-application/tests/test_repository_fakes.py -v
uv run --locked pytest packages/stickfix-application/tests/test_repository_fake_fidelity.py -v
uv run --locked pytest packages/stickfix-application/tests -v
```

`STICKFIX_TEST_DATABASE_URL` activates PostgreSQL integration tests that truncate the configured
DB. Only use a disposable test database and report skipped checks as *not verified*.
