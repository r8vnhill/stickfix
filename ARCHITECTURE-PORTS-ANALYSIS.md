# Stickfix architecture

Stickfix uses a small ports-and-adapters architecture with PostgreSQL as its
only runtime persistence backend.

```text
Telegram handlers
        ↓
application use cases → application ports ← PostgreSQL adapters
        ↓                                      ↑
domain rules                              runtime composition

migration CLI → legacy YAML records → migration PostgreSQL gateway
```

## Runtime boundaries

- `stickfix_domain` (`packages/stickfix-domain/`) contains Telegram-free sticker
  and user rules. It has no persistence, YAML, SQLAlchemy, logging, or
  infrastructure dependencies -- and no runtime dependencies at all.
- `bot.application` contains request/result DTOs, errors, use cases, and
  narrow repository/content ports. It does not import concrete adapters.
- `bot.handlers` translates Telegram updates and results. It receives use cases
  from `Stickfix` and does not construct persistence or migration adapters.
- `bot.infrastructure.persistence.postgres` implements the runtime repository
  ports. `PostgresUserRepository` uses one transaction per mutation and also
  implements `PublicPackRepository` for the shared pack.
- `bot.infrastructure.help` provides `FileHelpContentProvider`. One instance
  is shared by `/help` and empty inline-query help.
- `bot.infrastructure.logging` configures Python's standard logging handlers.
  Runtime modules obtain loggers with `logging.getLogger(__name__)`.
- `bot.stickfix.Stickfix` is the composition root. `Stickfix(token).run()` is
  the stable public entry point.

## Migration boundary

Historical YAML is input to the one-shot migration command only. The restricted
reader in `bot.infrastructure.migration.legacy_yaml` recognizes the two known
historical Python-object tag strings but maps them to immutable migration
records. It never imports or instantiates the classes named by those tags.

`PostgresMigrationGateway` owns migration-only operations:

- importing a validated logical snapshot atomically;
- checking whether the target database is empty;
- projecting PostgreSQL back to a logical snapshot for verification.

These operations are intentionally absent from `UserRepository` and
`PublicPackRepository`, and the runtime composition does not import the
migration package.

The historical `SF-PUBLIC` identifier remains data inside the migration
boundary. Runtime application contracts use `PublicPackRepository` instead.

## Executable rules

`tests/architecture/test_dependency_boundaries.py` checks the import direction
with the standard library's `ast` and `pathlib`. It protects at least these
rules:

- domain cannot import Telegram, application, handlers, infrastructure,
  project utilities, database modules, or logging;
- application cannot import Telegram, handlers, concrete infrastructure,
  legacy database modules, SQLAlchemy, or psycopg;
- handlers cannot import persistence, migration, legacy database modules,
  SQLAlchemy, or psycopg;
- runtime composition cannot import migration infrastructure.

The checks report the importing module and forbidden imported module so a
boundary regression is actionable.

## Persistence contracts

`UserRepository` owns regular users identified by numeric `UserId` values.
`PublicPackRepository` owns the shared pack without exposing a synthetic user
identity. Runtime mutations are committed before their use cases return.

The PostgreSQL schema and Alembic history are unchanged by the infrastructure
boundary work. The legacy YAML runtime backend (`StickfixDB` and its adapter)
has been removed; YAML backup rotation and recovery are therefore not runtime
requirements.
