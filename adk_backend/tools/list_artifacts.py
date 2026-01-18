from typing import Any, Dict, List, Optional
from google.adk.tools.tool_context import ToolContext

async def list_artifacts(tool_context: ToolContext) -> Dict[str, Any]:
    """현재 세션에 저장된 아티팩트 파일명 목록을 반환합니다."""
    artifacts = await tool_context.list_artifacts()

    names: List[str] = []
    for a in artifacts or []:
        # 버전/타입에 따라 속성명이 다를 수 있어 안전하게 처리
        name = getattr(a, "name", None) or getattr(a, "filename", None) or str(a)
        names.append(name)

    return {
        "status": "success",
        "count": len(names),
        "filenames": sorted(names),
        "hint": "읽고 싶은 파일명을 골라 read_artifact_preview(filename=...) 또는 read_table_artifact(filename=...)를 호출하세요.",
    }
