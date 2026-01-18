import io
import os
from typing import Any, AsyncGenerator

import pandas as pd
from google.genai import types as gt
from google.adk.models.lite_llm import LiteLlm


def _xlsx_to_preview_text(filename: str, data: bytes, max_rows: int = 60, max_cols: int = 40) -> str:
    """xlsx를 첫 시트 기준으로 표 미리보기 텍스트로 변환"""
    xls = pd.ExcelFile(io.BytesIO(data), engine="openpyxl")  # openpyxl 필요
    sheet = xls.sheet_names[0] if xls.sheet_names else None
    if not sheet:
        return f"[엑셀: {filename}] (시트 없음)"
    df = pd.read_excel(xls, sheet_name=sheet, engine="openpyxl")
    if df.shape[1] > max_cols:
        df = df.iloc[:, :max_cols]
    df = df.head(max_rows)
    return f"[엑셀 미리보기: {filename} / sheet={sheet}]\n{df.to_string(index=False)}"


class SafeLiteLlm(LiteLlm):
    """
    - PDF: 모델 입력에서 차단(텍스트 안내로 대체)
    - XLSX: MIME 파트 -> 텍스트 미리보기로 치환 (xlsx MIME 오류 방지)
    - CSV/TXT: 절대 건드리지 않음(원본 파트 그대로 유지)
    """

    def _sanitize_llm_request_inplace(self, llm_request: Any) -> None:
        contents = getattr(llm_request, "contents", None) or []
        for content in contents:
            parts = getattr(content, "parts", None) or []
            new_parts = []

            for p in parts:
                # 텍스트 파트는 그대로
                if getattr(p, "text", None):
                    new_parts.append(p)
                    continue

                inline = getattr(p, "inline_data", None)
                if inline is None:
                    # inline_data가 아니면 건드리지 않음 (csv/txt 포함 가능)
                    new_parts.append(p)
                    continue

                mime = getattr(inline, "mime_type", None) or ""
                data = getattr(inline, "data", None)
                filename = getattr(inline, "display_name", None) or "uploaded_file"
                ext = os.path.splitext(filename.lower())[1]

                # PDF 차단
                if mime == "application/pdf" or ext == ".pdf":
                    new_parts.append(gt.Part(text=f"[PDF 차단됨] {filename} (PDF는 모델 입력으로 전달하지 않습니다.)"))
                    continue

                # XLSX만 텍스트로 치환
                if (
                    mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    or ext in (".xlsx", ".xls")
                ):
                    if isinstance(data, (bytes, bytearray)):
                        try:
                            preview = _xlsx_to_preview_text(filename, bytes(data))
                        except Exception as e:
                            preview = f"[엑셀 파싱 실패] {filename} ({type(e).__name__}: {e})"
                    else:
                        preview = f"[엑셀 파싱 실패] {filename} (no bytes)"
                    new_parts.append(gt.Part(text=preview))
                    continue

                # CSV/TXT 등 나머지는 그대로 둠
                new_parts.append(p)

            content.parts = new_parts

    async def generate_content_async(self, *args, **kwargs) -> AsyncGenerator[Any, None]:
        """
        ADK는 여기서 반환되는 값을 `async for`로 순회한다.
        따라서 반드시 AsyncGenerator를 반환해야 한다.
        """
        # llm_request는 kwargs 또는 args[0]로 들어오는 케이스 둘 다 대응
        llm_request = kwargs.get("llm_request", None)
        if llm_request is None and len(args) >= 1:
            llm_request = args[0]

        if llm_request is not None:
            self._sanitize_llm_request_inplace(llm_request)

        # 부모 호출
        result = super().generate_content_async(*args, **kwargs)

        # result가 async generator인지 확인: __aiter__가 있으면 async for 가능
        if hasattr(result, "__aiter__"):
            async for item in result:
                yield item
            return

        # result가 coroutine(단일 응답)인 경우: await 후 1회 yield로 감싼다
        item = await result
        yield item
