"""Help-content infrastructure adapters.

This package contains concrete implementations of the application-layer `HelpContentProvider` port.

These adapters are allowed to depend on infrastructure concerns, such as local files or deployment
paths. They keep that knowledge out of application use cases, which should request help text only
through the port contract.

Runtime composition code is responsible for choosing and injecting the adapter used in production.
"""

from .file_help_content_provider import FileHelpContentProvider

__all__ = ["FileHelpContentProvider"]
