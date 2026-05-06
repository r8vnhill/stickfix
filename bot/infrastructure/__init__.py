"""Infrastructure adapters implementing application ports.

This package provides concrete implementations of application port contracts. Adapters bridge use 
cases with infrastructure systems (YAML storage, files, APIs) without exposing infrastructure 
details to the application layer.

Adapters are instantiated by handlers and injected into use cases at runtime. This preserves a 
clear boundary: handlers manage Telegram I/O, use cases own business logic, adapters handle 
external systems.

Current adapters:
- persistence.StickfixUserRepository: implements UserRepository port
- help.FileHelpContentProvider: implements HelpContentProvider port
"""
