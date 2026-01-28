# main_server.py
import asyncio
from fastmcp import FastMCP
from plot_toolbox.server import plot_toolbox
from ml_toolbox.server import ml_toolbox

mcp = FastMCP(name="main_mcp_server")

MCP_RESOURCE_ROOT = "C:/MyFolder/LLM/google-adk/.mcp/resources"
@mcp.resource("mcp://resources/{job_id}.csv",mime_type="text/csv")
async def get_job_csv(job_id:str)->bytes:
    path = MCP_RESOURCE_ROOT /f"{job_id}.csv"
    if not path.exists() or not path.is_file():
        raise ValueError("파일이 없다")
    return path.read_bytes()

async def setup():
    await mcp.import_server(plot_toolbox, prefix="plot")
    # await mcp.import_server(ml_toolbox, prefix="ml")

if __name__ == "__main__":
    asyncio.run(setup())
    mcp.run(transport="http", host="0.0.0.0", port=8001)
