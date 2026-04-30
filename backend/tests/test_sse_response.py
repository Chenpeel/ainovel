import asyncio
from pathlib import Path
import sys
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

fastapi_module = types.ModuleType("fastapi")
responses_module = types.ModuleType("fastapi.responses")


class _StreamingResponseStub:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


responses_module.StreamingResponse = _StreamingResponseStub
fastapi_module.responses = responses_module
sys.modules.setdefault("fastapi", fastapi_module)
sys.modules.setdefault("fastapi.responses", responses_module)

from app.utils.sse_response import HEARTBEAT, wrap_stream_with_heartbeat


def test_wrap_stream_with_heartbeat_yields_heartbeat_when_stream_stalls() -> None:
    async def source():
        await asyncio.sleep(0.02)
        yield "chunk"

    async def collect():
        items = []
        async for item in wrap_stream_with_heartbeat(source(), heartbeat_interval=0.005):
            items.append(item)
        return items

    items = asyncio.run(collect())

    assert HEARTBEAT in items
    assert items[-1] == "chunk"


def test_wrap_stream_with_heartbeat_passes_fast_stream_through() -> None:
    async def source():
        yield "a"
        yield "b"

    async def collect():
        items = []
        async for item in wrap_stream_with_heartbeat(source(), heartbeat_interval=0.1):
            items.append(item)
        return items

    items = asyncio.run(collect())

    assert items == ["a", "b"]
