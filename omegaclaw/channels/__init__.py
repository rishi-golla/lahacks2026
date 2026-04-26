"""OmegaClaw channel adapters."""

__all__ = ["BackendChannel", "GlassesTask"]


def __getattr__(name: str):
    if name in ("BackendChannel", "GlassesTask"):
        from .backend_channel import BackendChannel, GlassesTask  # noqa: F401

        return {"BackendChannel": BackendChannel, "GlassesTask": GlassesTask}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
