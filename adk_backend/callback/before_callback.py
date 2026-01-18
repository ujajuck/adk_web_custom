# model_callbacks.py
import io
import os
import csv
import pandas as pd
from google.genai import types as gt

# ---- 한글 텍스트 디코딩(utf-8-sig/cp949/euc-kr 대응) ----
def _bytes_to_text(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return data.decode(enc)
        except Exception:
            pass
    return data.decode("utf-8", errors="replace")

# ---- 엑셀(xlsx) 미리보기(첫 시트, 앞부분) ----
def _xlsx_preview(data: bytes, max_rows: int = 60, max_cols: int = 40) -> str:
    # openpyxl 필요 (없으면 설치)
    xls = pd.ExcelFile(io.BytesIO(data), engine="openpyxl")
    sheet = xls.sheet_names[0] if xls.sheet_names else None
    if not sheet:
        return "(엑셀에 시트가 없습니다.)"
    df = pd.read_excel(xls, sheet_name=sheet, engine="openpyxl")
    if df.shape[1] > max_cols:
        df = df.iloc[:, :max_cols]
    df = df.head(max_rows)
    return f"[XLSX: {sheet}]\n" + df.to_string(index=False)

# ---- CSV 미리보기(깨진 따옴표 방어) ----
def _csv_preview(text: str, max_rows: int = 60, max_cols: int = 40) -> str:
    # 1) 자동 구분자 추정(sep=None) + bad line skip
    try:
        df = pd.read_csv(io.StringIO(text), sep=None, engine="python", on_bad_lines="skip")
    except Exception:
        # 2) 따옴표 파싱 무시(깨진 quote 방어)
        df = pd.read_csv(
            io.StringIO(text),
            sep=",",
            engine="python",
            quoting=csv.QUOTE_NONE,
            on_bad_lines="skip",
        )
    if df.shape[1] > max_cols:
        df = df.iloc[:, :max_cols]
    df = df.head(max_rows)
    return df.to_string(index=False)

def before_model_callback(callback_context, llm_request):
    """
    - PDF 입력: 모델로 전달되는 파일 파트를 제거(차단)
    - XLSX 입력: 파일 파트를 표 미리보기 텍스트로 치환
    - 나머지(텍스트/CSV 등): 필요 시 텍스트로 치환(안전)
    """
    contents = getattr(llm_request, "contents", None) or []
    for content in contents:
        parts = getattr(content, "parts", None) or []
        new_parts = []

        for p in parts:
            # 일반 텍스트는 유지
            if getattr(p, "text", None):
                new_parts.append(p)
                continue

            inline = getattr(p, "inline_data", None)
            if inline and getattr(inline, "data", None):
                filename = getattr(inline, "display_name", None) or "uploaded_file"
                ext = os.path.splitext(filename.lower())[1]

                # 1) PDF 차단
                if ext == ".pdf":
                    # 모델 입력에서 제거 + 사용자에게 안내 텍스트만 남김
                    new_parts.append(gt.Part(text=f"[PDF 차단됨] {filename} (PDF는 모델 입력으로 전달하지 않습니다.)"))
                    continue

                # 2) XLSX는 텍스트로 치환(이게 MIME 오류를 없앰)
                if ext in (".xlsx", ".xls"):
                    try:
                        preview = _xlsx_preview(inline.data)
                    except Exception as e:
                        preview = f"(엑셀 파싱 실패: {type(e).__name__}: {e})"
                    new_parts.append(gt.Part(text=f"[엑셀 미리보기: {filename}]\n{preview}"))
                    continue

                # 3) CSV는 안정 파싱 후 텍스트로
                # if ext in (".csv", ".tsv"):
                #     txt = _bytes_to_text(inline.data)
                #     preview = _csv_preview(txt)
                #     new_parts.append(gt.Part(text=f"[CSV 미리보기: {filename}]\n{preview}"))
                #     continue

                # 4) TXT 계열은 한글 디코딩 후 텍스트로
                # if ext in (".txt", ".md", ".log", ".json", ".yaml", ".yml"):
                #     txt = _bytes_to_text(inline.data)
                #     new_parts.append(gt.Part(text=f"[텍스트: {filename}]\n{txt[:8000]}"))
                #     continue

                # 기타 파일은 “파일 파트”를 텍스트 안내로 치환
                # new_parts.append(gt.Part(text=f"[파일 첨부됨: {filename}] (이 형식은 텍스트로 변환하지 않고 참조만 합니다.)"))
                # continue

            # file_data/file_uri 형태는 모델 입력에서 안전하게 안내만 남김
            # file_data = getattr(p, "file_data", None)
            # if file_data and getattr(file_data, "file_uri", None):
            #     new_parts.append(gt.Part(text=f"[파일 URI 첨부됨] {file_data.file_uri} (모델 입력에는 URI를 직접 전달하지 않습니다.)"))
            #     continue

            # 알 수 없는 파트는 제거/대체
            # new_parts.append(gt.Part(text="(지원되지 않는 입력 파트가 제거되었습니다.)"))

        content.parts = new_parts
    return None
