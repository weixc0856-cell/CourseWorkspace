"""Delivery context: orders, delivery packages and incremental rebuild.

Submodules are imported directly; this package intentionally re-exports nothing,
because the orchestrator depends on the build pipeline and an eager package
import would close a cycle.
"""
