# Token Management Improvement Plan

Context: the bot currently relies on a local `secret.yml` loaded by a user-created `bot.py`. This is awkward to automate and does not distinguish between dev and deploy tokens. The goal is to remove `secret.yml`, make token loading environment-driven, and support separate dev/prod secrets without risking commits.

## Proposed design
- Switch to environment-based config: `STICKFIX_ENV` (`dev` default, `prod` for deployments) selects between `STICKFIX_TOKEN_DEV` and `STICKFIX_TOKEN_PROD`; also accept a generic `STICKFIX_TOKEN` override.
- Support file-based secrets (Docker/K8s/GitHub Actions) via `STICKFIX_TOKEN_FILE` so deployments can mount secrets safely.
- Optional local `.env` loading for developers using `python-dotenv`, but the primary contract is env vars.
- Provide a first-party entrypoint (`python -m bot` or `uv run stickfix`) that resolves the token and runs the bot—no need for users to author `bot.py`.

## Work plan
1) Config module: add `bot/config.py` (or `settings.py`) with a small dataclass to resolve env, token, and optional log path. Resolution order: explicit CLI `--token` > `STICKFIX_TOKEN` > env-specific token (`STICKFIX_TOKEN_DEV`/`STICKFIX_TOKEN_PROD`) > `STICKFIX_TOKEN_FILE`. Fail fast with a clear error when no token is found.
2) Entry point: add `bot/__main__.py` that parses `--env`, `--token`, `--token-file`, calls the config loader, then starts `Stickfix`. This removes the need for the ad-hoc `bot.py`.
3) Developer ergonomics: add `.env.example` with placeholders for dev/prod tokens; keep `.env*` gitignored. Document `uv run python -m bot` picking up `.env` for local work.
4) Docs: update `README.md` (and any contributor docs) to drop `secret.yml`, describe env vars, and show deploy snippets (systemd/docker/CI) that set `STICKFIX_ENV=prod` and inject tokens securely.
5) Tests: add `tests/test_config.py` covering token resolution paths (env selection, file-based secret, missing-token error). Optionally add a smoke test ensuring `Stickfix` starts when provided a dummy token.
6) CI/deploy: if/when CI exists, ensure it sets a dummy token or skips networked tests; add a short section on using secret stores (GitHub Actions secrets, Docker secrets) to keep tokens out of the repo.

## Acceptance criteria
- Running `STICKFIX_ENV=prod STICKFIX_TOKEN_PROD=xxxx uv run python -m bot` starts without needing `secret.yml`.
- Local dev can run with `.env` containing `STICKFIX_TOKEN_DEV=...`.
- README and examples no longer reference `secret.yml`; guidance exists for both dev and deployment tokens.
