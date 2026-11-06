try:
    from . import agent
    from .agent import root_agent

    __all__ = ["agent", "root_agent"]
except ModuleNotFoundError as exc:
    # Allow offline CLI tools (`workflow_cli.py`) to import `vibe_studio_agent.db`
    # even before the `google-adk` virtualenv is activated.
    if exc.name and exc.name.startswith("google"):
        agent = None  # type: ignore[assignment]
        root_agent = None  # type: ignore[assignment]
        __all__ = ["agent", "root_agent"]
    else:
        raise
