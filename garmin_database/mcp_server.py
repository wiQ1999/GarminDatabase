"""Lokalny MCP stdio; konfiguracja i uruchamianie: docs/12-running-and-testing.md."""

import argparse
import logging
import sys
from threading import Event
from typing import Annotated

import anyio
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .mcp_data import MAX_BYTES, MCPData


class CatalogInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    cursor: Annotated[str | None, Field(max_length=4096)] = None


class PeriodInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    date_from: Annotated[
        str,
        Field(
            pattern=r"^\d{4}-\d{2}-\d{2}$",
            description="Pierwszy dzień Europe/Warsaw, YYYY-MM-DD",
        ),
    ]
    date_to: Annotated[
        str,
        Field(
            pattern=r"^\d{4}-\d{2}-\d{2}$",
            description="Ostatni dzień włącznie, najpóźniej wczoraj",
        ),
    ]
    metrics: Annotated[
        list[Annotated[str, Field(max_length=200)]],
        Field(
            min_length=1,
            max_length=5,
            description="Jawne klucze parametrów z garmin_catalog",
        ),
    ]


class DailyInput(PeriodInput):
    cursor: Annotated[str | None, Field(max_length=4096)] = None


TOOLS = {
    "garmin_catalog": (
        CatalogInput,
        "catalog",
        "Katalog włączonych metryk: jednostki, dostępność, limity. Wywołaj jako pierwsze.",
    ),
    "get_daily": (
        DailyInput,
        "daily",
        "Dzienne średnie dostępnych próbek w Europe/Warsaw, min/max i jakość. Do 92 dni na stronę; kontynuuj przez cursor.",
    ),
    "get_period_stats": (
        PeriodInput,
        "period",
        "Średnia całego okresu ważona liczbą poprawnych próbek, min/max i liczby dni. Bez próbek, median i interpretacji medycznej.",
    ),
}


def tool_definitions():
    annotations = types.ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    return [
        types.Tool(
            name=name,
            description=description,
            inputSchema=model.model_json_schema(),
            outputSchema={
                "type": "object",
                "required": ["schema_version", "data_revision"],
            },
            annotations=annotations,
        )
        for name, (model, method, description) in TOOLS.items()
    ]


def error_result(message):
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=message)], isError=True
    )


async def call(service, name, arguments, limiter):
    if name not in TOOLS:
        return error_result("Nieznane narzędzie. Użyj tools/list.")
    model, method, _ = TOOLS[name]
    stop = Event()
    try:
        values = model.model_validate(arguments).model_dump()
        payload = await anyio.to_thread.run_sync(
            lambda: getattr(service, method)(**values, stop=stop),
            abandon_on_cancel=True,
            limiter=limiter,
        )
        result = types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text="Wynik w structuredContent; wartości opisują dostępne obserwacje.",
                )
            ],
            structuredContent=payload,
        )
        if (
            len(
                result.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8")
            )
            > MAX_BYTES
        ):
            return error_result("Odpowiedź przekracza limit. Zawęź wybór metryk.")
        service.check_policy(payload["policy_revision"])
        return result
    except ValidationError:
        return error_result(
            "Nieprawidłowe argumenty. Sprawdź schemat narzędzia i katalog metryk."
        )
    except ValueError as error:
        return error_result(str(error))
    except Exception:
        return error_result(
            "Odczyt nie powiódł się. Sprawdź ustawienia i bazę w aplikacji."
        )
    finally:
        stop.set()


def create_server(settings_path=None):
    service = MCPData(settings_path)
    server = Server("garmin_database_mcp", version="1.0.0")
    limiter = anyio.CapacityLimiter(1)

    @server.list_tools()
    async def list_tools():
        return tool_definitions()

    @server.call_tool(validate_input=False)
    async def call_tool(name, arguments):
        return await call(service, name, arguments, limiter)

    return server


async def serve(settings_path=None):
    server = create_server(settings_path)
    # Reuse Python's streams: SDK-created TextIOWrappers would own the same
    # buffers twice and close sys.stdout before PyInstaller's final flush.
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8")
    async with stdio_server(
        stdin=anyio.wrap_file(sys.stdin), stdout=anyio.wrap_file(sys.stdout)
    ) as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="GarminDatabase — MCP stdio tylko do odczytu"
    )
    parser.add_argument("--settings-file")
    args = parser.parse_args(argv)
    logging.getLogger("mcp").setLevel(logging.CRITICAL)
    anyio.run(serve, args.settings_file)


if __name__ == "__main__":
    main()
