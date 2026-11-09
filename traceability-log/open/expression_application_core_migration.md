# Progressive Expression adoption in the application core

## Decision

On 2026-11-09, the maintainer requested a progressive migration to
[Expression](https://github.com/dbrattli/Expression), starting with the files
already under review and targeting the functional core.

This first slice uses Expression `Option` at the application repository ports.
`Some` carries a detached user or public pack; `Nothing` represents absence.
Application use cases and the PostgreSQL adapter convert the option to ordinary
domain values at the point where existing use-case behavior needs a fallback or
`UserNotFoundError`.

The dependency is declared by `stickfix-application`, where the port imports
live, and by the root bot distribution, whose PostgreSQL adapter constructs the
same `Option` values. The domain remains standard-library-only. Telegram
responses and persistence semantics remain unchanged.

## Scope for this slice

- Add Expression to the application runtime dependency surface and lock it.
- Keep repository reads detached and preserve empty public-pack semantics.
- Update port consumers, fakes, PostgreSQL adapters, architecture policy, and
  dependency documentation together.
- Defer `Result`, effect builders, immutable domain aggregates, and further
  package migrations to separately reviewed slices.

## Verification

The Expression release line is bounded to `>=5.8,<6`. PyPI lists Expression
5.8.0 as the current release and declares Python `>=3.10,<4`, including Python
3.14. See [Expression on PyPI](https://pypi.org/project/Expression/5.8.0/).
