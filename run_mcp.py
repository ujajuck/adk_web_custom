#!/usr/bin/env python
"""MCP 서버 실행 스크립트"""
import asyncio
from mcp_server.main_server import mcp, setup

if __name__ == "__main__":
    asyncio.run(setup())
    mcp.run(transport="http", host="0.0.0.0", port=8001)
