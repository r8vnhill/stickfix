# [PLAN] Step 2: Extract `/setMode` as the First Application Slice

Status: implemented.

Implementation notes:

* `SetMode` now lives in `bot/application/use_cases/set_mode.py`.
* `StickfixUserRepository` adapts `StickfixDB` to the existing `UserRepository` port.
* `UserHandler.__set_mode` delegates mode-changing behaviour to the application layer while preserving Telegram replies.
* `UserHandler.__set_mode` keeps the raw Telegram user id when building the command so the legacy `StickfixDB` key shape remains compatible with the other handlers.
* Regression coverage was added for the use case, repository adapter, handler mapping, and application seam.

## Summary

Extract `/setMode` from `UserHandler` into the first small application-layer use case while preserving the current Telegram-visible behaviour exactly.

This step introduces the minimum application/infrastructure seam needed to move one command out of the Telegram handler. It must not redesign command dispatch, change the YAML persistence format, alter command names, or modify the existing user-facing replies.

The target shape is:

```text
Telegram handler
  -> parse Telegram-specific input
  -> build SetModeCommand
  -> call SetMode use case
  -> map application outcomes/errors to current Telegram replies/logging

Application use case
  -> validate mode
  -> load or create user
  -> mutate private_mode
  -> save through UserRepository
```

## Goals

* Move `/setMode` business behaviour out of `UserHandler`.
* Keep Telegram concerns out of `bot/application/`.
* Make user creation and mode mutation testable without Telegram objects.
* Add the first concrete adapter from the legacy `StickfixDB` store to the `UserRepository` port.
* Preserve all current runtime behaviour.

## Non-Goals

* Do not refactor `/shuffle`, `/random`, `/start`, or other commands.
* Do not introduce a generic command bus yet.
* Do not change `Commands.SET_MODE`.
* Do not change the YAML wire format.
* Do not change save timing beyond what `/setMode` already requires.
* Do not add case-insensitive modes unless current behaviour already supports them.
* Do not move Markdown reply text into the application layer.

## Behaviour Contract

Preserve the current `/setMode` behaviour:

| Input              | Application behaviour                                    | Telegram reply                 |
| ------------------ | -------------------------------------------------------- | ------------------------------ |
| `/setMode private` | create user if missing, set `private_mode = True`, save  | `"Leave it to me!"`            |
| `/setMode public`  | create user if missing, set `private_mode = False`, save | `"Leave it to me!"`            |
| `/setMode invalid` | reject without successful mutation                       | existing Markdown syntax error |
| `/setMode`         | no operation                                             | no reply                       |

The missing-argument no-op is a compatibility behaviour. Because `context.args` is Telegram-specific, it may remain in the handler for this step unless the existing `SetModeCommand` can naturally represent an absent mode.

## Design Decisions

### 1. Add a `SetMode` use case

Add the use case under:

```text
bot/application/use_cases/set_mode.py
```

The use case should depend only on application/domain abstractions:

```text
SetMode
  depends on UserRepository
  accepts SetModeCommand
  returns AcknowledgementResult
  raises InvalidCommandInputError
```

It must not import:

* `telegram`
* `telegram.ext`
* `Update`
* `ContextTypes`
* `UserHandler`
* presentation-layer logging helpers
* Markdown reply constants

### 2. Reuse existing DTOs

Use the existing request/result DTOs:

```text
SetModeCommand
AcknowledgementResult
```

Do not expand the DTO model unless implementation proves the current shape cannot represent the command cleanly.

If `AcknowledgementResult` currently has no meaningful payload, keep it as a simple success marker. Avoid adding status variants until a second command needs them.

### 3. Validate before mutating

The preferred application flow is:

```text
normalize/validate requested mode
load user by id
create user only if missing and mode is valid
mutate private_mode
save user
return acknowledgement
```

Invalid mode values should raise `InvalidCommandInputError`.

Add a regression test for invalid mode side effects if the repository fake can observe saves. The target behaviour should be: invalid input does not save a mutated user. If the current implementation behaves differently, lock the current behaviour first and document the discrepancy before changing it in a later cleanup.

### 4. Keep presentation mapping in the handler

The Telegram handler remains responsible for:

* reading `message`, `user`, and `context.args`
* preserving the missing-argument no-op
* constructing `SetModeCommand`
* calling `SetMode`
* replying with `"Leave it to me!"` on success
* replying with the existing Markdown syntax error on `InvalidCommandInputError`
* preserving the existing info/debug/error logging paths
* routing unexpected exceptions through `unexpected_error`

The application layer should communicate “invalid command input” as an application error, not as preformatted Telegram Markdown.

### 5. Add a small `StickfixDB` repository adapter

Add the minimum adapter needed for this slice, preferably under an infrastructure/persistence-oriented module rather than inside the handler file.

Suggested location:

```text
bot/infrastructure/persistence/stickfix_user_repository.py
```

or, if the project already has a repository adapter location, use that existing structure.

The adapter should implement the existing `UserRepository` port and delegate to `StickfixDB`.

Keep it intentionally narrow:

```text
StickfixUserRepository
  -> get user by id
  -> create/store user if needed
  -> save mutated user
```

Avoid introducing a new persistence abstraction in this step. The goal is to connect the already-defined port to the legacy store.

## Handler Integration

Keep the existing registration:

```text
CommandHandler(Commands.SET_MODE, ...)
```

Update only the internals of `UserHandler.__set_mode`.

Target flow:

```text
__set_mode(update, context)
  extract message/user safely
  if no args: return
  command = SetModeCommand(user_id=str(user.id), mode=context.args[0])
  try:
      set_mode(command)
  except InvalidCommandInputError:
      reply existing Markdown syntax error
      keep existing handled-error debug logging
      return
  except Exception:
      route through unexpected_error
      return

  reply "Leave it to me!"
  keep existing info log wording
```

Prefer injecting the `SetMode` use case into `UserHandler` instead of constructing it inside the method. If the current handler construction makes that too large for this slice, use a small factory/wiring helper, but keep direct construction out of the command body where possible.

## Test Plan

### 1. Characterisation tests first

Before changing implementation, add or verify handler-level tests that describe the current `/setMode` behaviour:

* valid `private` replies `"Leave it to me!"`
* valid `public` replies `"Leave it to me!"`
* invalid mode replies the existing Markdown syntax message
* missing argument produces no reply
* unexpected exceptions still go through the existing unexpected-error path, if already covered

These tests protect Telegram-visible behaviour before extraction.

### 2. Application unit tests

Add focused tests for `SetMode` using an in-memory fake repository.

Suggested file:

```text
tests/application/use_cases/test_set_mode.py
```

Cover:

* creates a missing user when mode is `"private"`
* creates a missing user when mode is `"public"`
* sets an existing user to private
* sets an existing user to public
* saves the mutated user on valid input
* rejects an invalid mode with `InvalidCommandInputError`
* does not save on invalid mode, unless current behaviour explicitly requires otherwise
* does not import Telegram through application modules

Use BDD-style test names, for example:

```text
describe SetMode
  when the requested mode is private
    it creates a missing user in private mode
    it updates an existing user to private mode

  when the requested mode is public
    it creates a missing user in public mode
    it updates an existing user to public mode

  when the requested mode is invalid
    it rejects the command without acknowledging it
```

### 3. Handler regression tests

Add or update handler tests for the integration seam:

* handler builds `SetModeCommand` with `user_id=str(user.id)`
* handler passes only the first argument as the requested mode
* success maps to `"Leave it to me!"`
* `InvalidCommandInputError` maps to the existing Markdown syntax reply
* missing args short-circuit before calling the use case
* unexpected exceptions still use `unexpected_error`

Use a fake use case for handler tests. The handler tests should not depend on `StickfixDB`.

### 4. Infrastructure adapter tests

Add a small adapter test only if the adapter contains behaviour beyond direct delegation.

Cover:

* existing user can be loaded through the repository port
* missing user is represented consistently with the port contract
* saved mutations are reflected in the underlying `StickfixDB`

Avoid over-testing `StickfixDB` itself in this step.

## Suggested Implementation Order

### Step 2.1: Lock current behaviour

Run the existing relevant tests and add missing characterisation tests before moving code.

```sh
uv run pytest tests/application/test_application_seam.py
```

Then run the current handler tests for `/setMode`, or add them if they do not exist yet.

### Step 2.2: Add failing application tests

Add `SetMode` tests against a fake `UserRepository`.

Expected initial state: tests fail because the use case does not exist or is not wired.

### Step 2.3: Implement `SetMode`

Implement only enough behaviour to pass the application tests:

* mode validation
* missing-user creation
* `private_mode` mutation
* repository save
* `InvalidCommandInputError`

Keep functions short and avoid introducing a broader command framework.

### Step 2.4: Add the `StickfixDB` adapter

Implement the minimal `UserRepository` adapter for the legacy store.

Do not alter the YAML format or persistence semantics.

### Step 2.5: Wire the handler

Update `UserHandler.__set_mode` to call the use case.

Keep reply text, Markdown parsing, logging, and unexpected-error handling behaviour stable.

### Step 2.6: Run targeted and full tests

Run:

```sh
uv run pytest tests/application/test_application_seam.py
uv run pytest tests/application/use_cases/test_set_mode.py
uv run pytest <targeted-handler-setmode-tests>
uv run pytest
```

Replace `<targeted-handler-setmode-tests>` with the concrete test file or `-k set_mode` selector used by the project.

## Architecture Checks

Add or preserve a seam test that ensures application modules do not depend on Telegram.

The check should fail if any module under:

```text
bot/application/
```

imports from:

```text
telegram
telegram.ext
```

This protects the purpose of the extraction and prevents the first application slice from becoming presentation-coupled.

## Risks and Mitigations

### Risk: changing missing-argument behaviour accidentally

Mitigation: keep the no-argument branch in the handler for this step and cover it with a regression test.

### Risk: leaking Telegram Markdown into the application layer

Mitigation: application raises `InvalidCommandInputError`; handler owns the exact reply text.

### Risk: adapter becomes a second persistence model

Mitigation: implement only the existing `UserRepository` port over `StickfixDB`. Do not introduce new serialization logic.

### Risk: invalid input creates or saves users unexpectedly

Mitigation: validate before mutation and add an explicit invalid-input side-effect test, unless current behaviour requires the opposite.

### Risk: handler tests become too coupled to Telegram internals

Mitigation: use a fake use case and assert observable handler behaviour: command built, reply sent or not sent, error path selected.

## Definition of Done

* `SetMode` exists under `bot/application/use_cases/`.
* `UserHandler.__set_mode` delegates mode-changing behaviour to `SetMode`.
* `bot/application/` has no Telegram imports.
* Valid `/setMode private` and `/setMode public` still reply `"Leave it to me!"`.
* Invalid mode still replies with the existing Markdown syntax message.
* Missing mode still produces no reply.
* The legacy YAML format remains unchanged.
* `StickfixDB` is accessed through a `UserRepository` adapter for this slice.
* Targeted application, handler, adapter/seam, and full test suites pass.
