async def strip_file_parts_before_model(
    *, llm_request: LlmRequest, callback_context: CallbackContext
) -> None:
    # llm_request 안의 contents/messages를 순회하면서
    # text 이외의 part(inline_data/file_data 등)를 텍스트 placeholder로 교체
    for content in llm_request.contents:
        new_parts = []
        for part in content.parts:
            if getattr(part, "text", None):
                new_parts.append(part)
                continue

            # 아래 조건들은 버전에 따라 달라질 수 있음 (inline_data/file_data 등)
            if getattr(part, "inline_data", None) or getattr(part, "file_data", None):
                # 실제 artifact 이름/uri를 여기서 구성해도 되고,
                # 이미 저장되어 있다면 “저장됨” 안내만 남겨도 됨
                from google.genai import types
                new_parts.append(types.Part(text="(업로드 파일은 artifacts에 저장되었습니다. 필요 시 tool로 읽겠습니다.)"))
                continue

            # 기타 파트는 보수적으로 제거
            from google.genai import types
            new_parts.append(types.Part(text="(지원되지 않는 입력 파트가 제거되었습니다.)"))

        content.parts = new_parts

