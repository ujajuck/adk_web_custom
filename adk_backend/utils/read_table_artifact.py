import io
import os
from typing import Any, Dict, List, Optional
import csv
import pandas as pd
from google.adk.tools.tool_context import ToolContext


async def read_table_artifact(
    filename: str,
    sheet_name: Optional[str] = None,
    delimiter: Optional[str] = None,
    header: Optional[int] = 0,
    max_rows: int = 50,
    max_cols: int = 50,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    CSV/TSV/XLSX 아티팩트를 표로 파싱해 반환합니다.

    Args:
        filename: 아티팩트 파일명
        sheet_name: 엑셀 시트명(엑셀일 때만)
        delimiter: CSV 구분자(지정 시 그대로 사용)
        header: 헤더 행 인덱스(None이면 헤더 없음)
        max_rows: 반환할 행 수(앞부분)
        max_cols: 반환할 열 수(앞부분)

    Returns:
        dict: status, columns, head(records), shape 등
    """
    data = await tool_context.load_artifact(filename=filename)
    if data is None:
        return {"status": "error", "error": f"artifact not found: {filename}"}
    if not isinstance(data, (bytes, bytearray)):
        data = bytes(str(data), "utf-8", errors="ignore")

    ext = os.path.splitext(filename.lower())[1]

    if ext in (".csv", ".tsv"):
        text = data.decode("utf-8", errors="replace")
        sep = delimiter or ("\t" if ext == ".tsv" else ",")
        df = pd.read_csv(
            io.StringIO(text),
            sep=sep,
            header=header,
            engine="python",
            quoting=csv.QUOTE_NONE,
            on_bad_lines="skip",
        )

    elif ext in (".xlsx", ".xls"):
        bio = io.BytesIO(data)
        xls = pd.ExcelFile(bio)
        use_sheet = sheet_name or (xls.sheet_names[0] if xls.sheet_names else None)
        if use_sheet is None:
            return {"status": "error", "error": "xlsx has no sheets", "filename": filename}
        df = pd.read_excel(xls, sheet_name=use_sheet, header=header)

    else:
        return {"status": "error", "error": f"unsupported table file: {ext}"}

    # 자르기
    if df.shape[1] > max_cols:
        df = df.iloc[:, :max_cols]
    df_head = df.head(max_rows)

    return {
        "status": "success",
        "filename": filename,
        "shape": [int(df.shape[0]), int(df.shape[1])],
        "columns": [str(c) for c in df.columns.tolist()],
        "head": df_head.to_dict(orient="records"),
    }
