import io
import os
import csv as pycsv
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from google.adk.tools.tool_context import ToolContext


def _guess_delimiter(sample_text: str) -> str:
    """CSV 구분자를 샘플 텍스트로 추정합니다."""
    try:
        dialect = pycsv.Sniffer().sniff(sample_text, delimiters=[",", "\t", ";", "|"])
        return dialect.delimiter
    except Exception:
        return ","


def _bytes_to_text(data: bytes) -> str:
    """바이트를 텍스트로 디코딩(UTF-8 우선, 실패 시 cp949 등으로 시도)합니다."""
    for enc in ("utf-8", "utf-8-sig", "cp949", "euc-kr", "latin-1"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    # 최후: 깨진 문자는 대체
    return data.decode("utf-8", errors="replace")


def _df_head_to_records(df: pd.DataFrame, max_rows: int, max_cols: int) -> Tuple[List[Dict[str, Any]], List[str]]:
    """DataFrame 앞부분을 JSON-serializable records로 변환합니다."""
    if df is None:
        return [], []
    df2 = df.copy()
    if df2.shape[1] > max_cols:
        df2 = df2.iloc[:, :max_cols]
    df2 = df2.head(max_rows)
    cols = [str(c) for c in df2.columns.tolist()]
    records = df2.to_dict(orient="records")
    return records, cols


async def read_artifact_preview(
    filename: str,
    max_rows: int = 20,
    max_cols: int = 30,
    max_chars: int = 4000,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    아티팩트 파일(txt/csv/xlsx)을 로드해 내용 미리보기를 반환합니다.

    Args:
        filename: 아티팩트 파일명(예: '과제정보.txt', 'data.csv', 'sheet.xlsx')
        max_rows: 표 형식(csv/xlsx) 미리보기 행 수
        max_cols: 표 형식(csv/xlsx) 미리보기 열 수
        max_chars: 텍스트(txt) 미리보기 문자 수

    Returns:
        dict: status, file_type, preview(텍스트 또는 표 head), 메타데이터를 포함한 결과
    """
    # 1) bytes 로드
    data = await tool_context.load_artifact(filename=filename)
    if data is None:
        return {"status": "error", "error": f"artifact not found: {filename}"}

    if not isinstance(data, (bytes, bytearray)):
        # 어떤 환경에서는 dict/Artifact 객체가 올 수도 있어 방어
        data = bytes(str(data), "utf-8", errors="ignore")

    ext = os.path.splitext(filename.lower())[1]

    # 2) TXT
    if ext in (".txt", ".md", ".log", ".json", ".yaml", ".yml"):
        text = _bytes_to_text(data)
        return {
            "status": "success",
            "file_type": "text",
            "filename": filename,
            "preview": text[:max_chars],
            "total_chars": len(text),
            "note": "더 길게 보려면 max_chars를 늘리거나, 필요한 범위를 지정해달라고 요청하세요.",
        }

    # 3) CSV/TSV
    if ext in (".csv", ".tsv"):
        text = _bytes_to_text(data)
        sample = text[:5000]
        delimiter = "\t" if ext == ".tsv" else _guess_delimiter(sample)

        df = pd.read_csv(io.StringIO(text), sep=delimiter, engine="python")
        records, cols = _df_head_to_records(df, max_rows=max_rows, max_cols=max_cols)

        return {
            "status": "success",
            "file_type": "table",
            "filename": filename,
            "format": "csv/tsv",
            "delimiter": delimiter,
            "shape": [int(df.shape[0]), int(df.shape[1])],
            "columns": cols,
            "head": records,
            "note": "원하면 특정 컬럼 통계/필터/요약도 이어서 처리할 수 있어요.",
        }

    # 4) XLSX
    if ext in (".xlsx", ".xls"):
        bio = io.BytesIO(data)
        # engine=openpyxl은 xlsx에서 안정적(이미 설치돼 있는 경우가 많음)
        # sheet_name=None이면 모든 시트를 dict로 반환하지만, 여기선 첫 시트만 미리보기
        xls = pd.ExcelFile(bio)
        sheet_names = xls.sheet_names
        first_sheet = sheet_names[0] if sheet_names else None
        if first_sheet is None:
            return {"status": "error", "error": "xlsx has no sheets", "filename": filename}

        df = pd.read_excel(xls, sheet_name=first_sheet)
        records, cols = _df_head_to_records(df, max_rows=max_rows, max_cols=max_cols)

        return {
            "status": "success",
            "file_type": "table",
            "filename": filename,
            "format": "xlsx",
            "sheet_names": sheet_names,
            "used_sheet": first_sheet,
            "shape": [int(df.shape[0]), int(df.shape[1])],
            "columns": cols,
            "head": records,
            "note": "다른 시트를 보려면 read_table_artifact(filename=..., sheet_name='...')를 사용하세요.",
        }

    # 5) 그 외
    return {
        "status": "error",
        "error": f"unsupported file type: {ext}",
        "filename": filename,
        "hint": "지원: txt, csv, tsv, xlsx(xls).",
    }
