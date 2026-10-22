from time import perf_counter
from typing import Any, Callable


class ToolExecutionError(RuntimeError):
    def __init__(self, agent: str, tool: str, cause: Exception) -> None:
        self.agent = agent
        self.tool = tool
        self.detail = str(cause)
        self.original_error_type = type(cause).__name__
        super().__init__(f"{agent}.{tool} failed: {cause}")


def execute_tool(
    trace: list[dict],
    agent: str,
    tool: str,
    inputs: dict,
    operation: Callable[[], Any],
) -> Any:
    started_at = perf_counter()
    entry = {
        "agent": agent,
        "tool": tool,
        "input": inputs,
        "output": None,
        "duration_ms": 0.0,
        "status": "running",
    }
    trace.append(entry)

    try:
        output = operation()
    except Exception as error:
        entry.update({
            "output": {"error": str(error), "error_type": type(error).__name__},
            "duration_ms": round((perf_counter() - started_at) * 1000, 3),
            "status": "failed",
        })
        raise ToolExecutionError(agent, tool, error) from error

    entry.update({
        "output": output,
        "duration_ms": round((perf_counter() - started_at) * 1000, 3),
        "status": "success",
    })
    return output
