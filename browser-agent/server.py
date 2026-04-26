import asyncio
from contextlib import AsyncExitStack
from typing import Any, Literal

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.server.fastmcp import FastMCP


AGENT_TOOL_USE_INSTRUCTIONS = (
    "IMPORTANT: You only get one browser tool call for each user request. "
    "Choose the single best tool call. If navigation is needed, call "
    "browser_navigate exactly once with the final, complete destination URL. "
    "Include all required path segments, query parameters, search terms, filters, "
    "and encoded values in that first URL. Do not navigate to a homepage first "
    "and do not rely on follow-up browser tool calls to search, click, type, "
    "or refine the page."
)

mcp = FastMCP("playwright", instructions=AGENT_TOOL_USE_INSTRUCTIONS)

PLAYWRIGHT_MCP_URL = "http://localhost:8931/mcp"

_playwright_stack: AsyncExitStack | None = None
_playwright_session: ClientSession | None = None
_playwright_lock = asyncio.Lock()


async def get_playwright_session() -> ClientSession:
    global _playwright_stack, _playwright_session

    if _playwright_session is not None:
        return _playwright_session

    _playwright_stack = AsyncExitStack()
    streams = await _playwright_stack.enter_async_context(
        streamable_http_client(
            PLAYWRIGHT_MCP_URL,
            terminate_on_close=False,
        )
    )
    read_stream, write_stream, *_ = streams

    _playwright_session = await _playwright_stack.enter_async_context(
        ClientSession(read_stream, write_stream)
    )
    await _playwright_session.initialize()

    return _playwright_session


def dump_mcp_model(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)

    if hasattr(value, "dict"):
        return value.dict(exclude_none=True)

    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if item is not None
        }

    return value


async def call_remote_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    clean_arguments = {
        key: value
        for key, value in (arguments or {}).items()
        if value is not None
    }

    async with _playwright_lock:
        session = await get_playwright_session()
        result = await session.call_tool(tool_name, arguments=clean_arguments)

    return dump_mcp_model(result)


@mcp.tool()
async def list_playwright_tools() -> str:
    """List the default tools exposed by the Playwright MCP server.

    IMPORTANT: The agent may only use one browser tool call per user request.
    """

    async with _playwright_lock:
        session = await get_playwright_session()
        result = await session.list_tools()

    tools = getattr(result, "tools", []) or []

    if not tools:
        return "No Playwright MCP tools found."

    return "\n".join(
        f"- {tool.name}: {tool.description or 'No description'}"
        for tool in tools
    )


async def browser_close() -> dict[str, Any]:
    """Close the page."""

    return await call_remote_tool("browser_close")


@mcp.tool()
async def browser_resize(width: float, height: float) -> dict[str, Any]:
    """Resize the browser window.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool("browser_resize", {"width": width, "height": height})


@mcp.tool()
async def browser_console_messages(
    level: Literal["error", "warning", "info", "debug"] = "info",
    all: bool | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    """Return console messages from the browser page.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    arguments = {"level": level, "all": all, "filename": filename}
    return await call_remote_tool("browser_console_messages", arguments)


@mcp.tool()
async def browser_handle_dialog(
    accept: bool,
    promptText: str | None = None,
) -> dict[str, Any]:
    """Accept or dismiss a browser dialog.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool(
        "browser_handle_dialog",
        {"accept": accept, "promptText": promptText},
    )


@mcp.tool()
async def browser_evaluate(
    function: str,
    element: str | None = None,
    ref: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    """Evaluate a JavaScript function on the page or a snapshot element.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool(
        "browser_evaluate",
        {"function": function, "element": element, "ref": ref, "filename": filename},
    )


@mcp.tool()
async def browser_file_upload(paths: list[str] | None = None) -> dict[str, Any]:
    """Upload one or more files, or cancel the file chooser when paths is omitted.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool("browser_file_upload", {"paths": paths})


@mcp.tool()
async def browser_fill_form(fields: list[dict[str, Any]]) -> dict[str, Any]:
    """Fill multiple form fields using refs from browser_snapshot.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool("browser_fill_form", {"fields": fields})


@mcp.tool()
async def browser_press_key(key: str) -> dict[str, Any]:
    """Press a key on the keyboard.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool("browser_press_key", {"key": key})


@mcp.tool()
async def browser_type(
    ref: str,
    text: str,
    element: str | None = None,
    submit: bool | None = None,
    slowly: bool | None = None,
) -> dict[str, Any]:
    """Type text into an editable element identified by a browser_snapshot ref.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool(
        "browser_type",
        {
            "element": element,
            "ref": ref,
            "text": text,
            "submit": submit,
            "slowly": slowly,
        },
    )


@mcp.tool()
async def browser_navigate(url: str) -> dict[str, Any]:
    """Navigate to a URL.

    IMPORTANT: You only get one browser tool call for this user request. Use
    this as the first and only browser action when navigation or search is
    needed. The url must already be the final destination URL and must include
    all path segments, query parameters, search terms, filters, and encoded
    values. Do not navigate to a homepage first. Do not assume you can click,
    type, search, or refine the page afterward.
    """

    return await call_remote_tool("browser_navigate", {"url": url})


@mcp.tool()
async def browser_navigate_back() -> dict[str, Any]:
    """Go back to the previous page in browser history.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool("browser_navigate_back")


@mcp.tool()
async def browser_network_requests(
    static: bool = False,
    requestBody: bool = False,
    requestHeaders: bool = False,
    filter: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    """Return network requests observed by the browser page.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool(
        "browser_network_requests",
        {
            "static": static,
            "requestBody": requestBody,
            "requestHeaders": requestHeaders,
            "filter": filter,
            "filename": filename,
        },
    )


@mcp.tool()
async def browser_run_code(
    code: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    """Run a JavaScript Playwright code snippet against the page.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool("browser_run_code", {"code": code, "filename": filename})


@mcp.tool()
async def browser_take_screenshot(
    type: Literal["png", "jpeg"] = "png",
    filename: str | None = None,
    element: str | None = None,
    ref: str | None = None,
    fullPage: bool | None = None,
) -> dict[str, Any]:
    """Take a screenshot of the current page or a snapshot element.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool(
        "browser_take_screenshot",
        {
            "type": type,
            "filename": filename,
            "element": element,
            "ref": ref,
            "fullPage": fullPage,
        },
    )


@mcp.tool()
async def browser_snapshot(
    filename: str | None = None,
    depth: float | None = None,
) -> dict[str, Any]:
    """Capture an accessibility snapshot for locating elements by ref.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool("browser_snapshot", {"filename": filename, "depth": depth})


@mcp.tool()
async def browser_click(
    ref: str,
    element: str | None = None,
    doubleClick: bool | None = None,
    button: Literal["left", "right", "middle"] | None = None,
    modifiers: list[Literal["Alt", "Control", "ControlOrMeta", "Meta", "Shift"]] | None = None,
) -> dict[str, Any]:
    """Click an element identified by a browser_snapshot ref.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool(
        "browser_click",
        {
            "element": element,
            "ref": ref,
            "doubleClick": doubleClick,
            "button": button,
            "modifiers": modifiers,
        },
    )


@mcp.tool()
async def browser_drag(
    startElement: str,
    startRef: str,
    endElement: str,
    endRef: str,
) -> dict[str, Any]:
    """Drag and drop between two elements identified by browser_snapshot refs.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool(
        "browser_drag",
        {
            "startElement": startElement,
            "startRef": startRef,
            "endElement": endElement,
            "endRef": endRef,
        },
    )


@mcp.tool()
async def browser_hover(
    ref: str,
    element: str | None = None,
) -> dict[str, Any]:
    """Hover over an element identified by a browser_snapshot ref.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool("browser_hover", {"element": element, "ref": ref})


@mcp.tool()
async def browser_select_option(
    ref: str,
    values: list[str],
    element: str | None = None,
) -> dict[str, Any]:
    """Select one or more dropdown options on an element identified by ref.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool(
        "browser_select_option",
        {"element": element, "ref": ref, "values": values},
    )


@mcp.tool()
async def browser_tabs(
    action: Literal["list", "new", "close", "select"],
    index: float | None = None,
) -> dict[str, Any]:
    """List, create, close, or select a browser tab.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool("browser_tabs", {"action": action, "index": index})


@mcp.tool()
async def browser_wait_for(
    time: float | None = None,
    text: str | None = None,
    textGone: str | None = None,
) -> dict[str, Any]:
    """Wait for time to pass, text to appear, or text to disappear.

    IMPORTANT: You only get one browser tool call for this user request.
    """

    return await call_remote_tool(
        "browser_wait_for",
        {"time": time, "text": text, "textGone": textGone},
    )


@mcp.tool()
async def call_playwright_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fallback escape hatch: call a Playwright MCP tool by exact name.

    IMPORTANT: You only get one browser tool call for this user request. If
    you use this to navigate, call browser_navigate with the complete final URL,
    including all query parameters, in this single call.
    """

    return await call_remote_tool(tool_name, arguments)


if __name__ == "__main__":
    mcp.run()
