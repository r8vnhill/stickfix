"""Application outbound ports.

## Overview

This package defines the infrastructure-facing contracts used by the application layer.

A port is a narrow `Protocol` that states what a use case needs from an external system. It must not
expose Telegram objects, filesystem details, database client types, or adapter-specific
implementation concerns.

## Dependency flow:

    handlers -> use cases -> ports -> infrastructure adapters

## Examples:

- `UserRepository` describes how use cases load and save Stickfix users.
- `HelpContentProvider` describes how use cases obtain raw help text.

Concrete implementations belong in `bot.infrastructure`, where they may delegate  to YAML files,
local files, databases, HTTP clients, or other external systems.

Keeping these contracts here gives Stickfix a stable application boundary: use cases remain easy to 
test with fakes, while production wiring can choose the appropriate adapter.
"""

from .help_content import HelpContentProvider
from .user_repository import UserRepository

__all__ = ["HelpContentProvider", "UserRepository"]
