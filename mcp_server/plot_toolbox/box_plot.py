from __future__ import annotations

import base64
from typing import Any, Dict

from google.adk.tools import ToolContext
from google.genai import types 

async def box_plot(
    artifact_locator: List[Dict[str, Any]],
    html_base64: str,
    tool_context: ToolContext,
) -> Dict[str, Any]:
    """박스플롯 요약 통계를 계산한다.

    Args:
        values (list[float]): 수치 데이터 목록
    """


    html_b64 = base64.b64encode(html_bytes).decode("utf-8")
    return { 
        "status": "success",
        "outputs": [
             {
                "type": "plot", 
                "filename": f"image.html", 
                "mime_type": "text/html", 
                "html_base64": html_base64, 
            }, 
            ] 
        }