# `stickfix-application`

The application package contains Stickfix's transport-agnostic use cases and
their explicit contracts. It depends on `stickfix-domain` and must not import
Telegram, SQLAlchemy, PostgreSQL drivers, or other concrete infrastructure.

## Maintainer contract

- `requests` and `results` are frozen DTOs crossing the adapter boundary.
- `errors` contains failures that handlers translate into user-facing replies.
- `ports` defines narrow protocols implemented by infrastructure adapters.
- `use_cases` contains one callable class per application command or query.

The package-level `__all__` lists the supported facade. Preserve its shape and
the DTO fields when changing the package; handler mappings and downstream
integrations rely on them.

Application tests live beside this package in `tests/`. They use in-memory
fakes and architecture checks to prove that the package can be built and
imported without the Telegram or persistence runtime.
