# main_server.py
import asyncio
from fastmcp import FastMCP
from plot_toolbox.server import plot_toolbox
from ml_toolbox.server import ml_toolbox

mcp = FastMCP(name="main_mcp_server")

async def setup():
    # ✅ 정적 합치기: prefix로 충돌 방지 + 네임스페이스 효과
    await mcp.import_server(plot_toolbox, prefix="plot")
    # await mcp.import_server(ml_toolbox, prefix="ml")

if __name__ == "__main__":
    asyncio.run(setup())
    mcp.run(transport="http", host="0.0.0.0", port=8001)
