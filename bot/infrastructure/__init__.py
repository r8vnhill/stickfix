"""Concrete adapters implementing application ports.

This package bridges application-facing ports (e.g., UserRepository) with
infrastructure details (YAML persistence, filesystem, etc.). Adapters are
injected into use cases by handlers. They may depend on storage/database
details but not on Telegram handler logic.

Current adapters:
  - persistence.StickfixUserRepository: implements UserRepository port
    wrapping the legacy StickfixDB YAML store
"""
