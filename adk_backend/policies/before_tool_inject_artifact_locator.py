# agent/policies/before_tool_inject_artifact_locator_v1.py

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext


def _latest_version_from_disk(artifact_root: Path, session_id: str, artifact_name: str) -> Optional[int]:
    """
    artifacts/<artifact_name>/versions/ 아래에서 가장 큰 버전 번호를 찾아 반환한다.
    실패하면 None.
    """
    versions_dir = (
        artifact_root
        / "user"
        / "sessions"
        / session_id
        / "artifacts"
        / artifact_name
        / "versions"
    )

    if not versions_dir.exists():
        return None

    candidates = []
    for p in versions_dir.iterdir():
        if p.is_dir() and p.name.isdigit():
            candidates.append(int(p.name))

    return max(candidates) if candidates else None


async def before_tool_inject_artifact_locator(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
) -> Optional[Dict[str, Any]]:
    """
    MCP 툴 실행 직전, artifact_locator를 '정확한 값'으로 보강한다.
    - user_id/session_id 자동 주입
    - version 미지정 시 디스크에서 최신 버전 탐색
    - 필요 필드 없으면 에러
    """
    locator = args.get("artifact_locator")
    if not isinstance(locator, dict):
        raise ValueError("artifact_locator가 필요합니다.")

    # 최소 식별자: artifact_name 또는 file_name 중 하나는 있어야 함
    artifact_name = locator.get("artifact_name")
    file_name = locator.get("file_name")

    if not isinstance(artifact_name, str) or not artifact_name.strip():
        # file_name만 왔다면 artifact_name을 file_name 기반으로 유추(확장자 제거)
        if isinstance(file_name, str) and file_name.strip():
            artifact_name = Path(file_name).stem
        else:
            raise ValueError("artifact_locator에는 artifact_name 또는 file_name이 필요합니다.")

    if not isinstance(file_name, str) or not file_name.strip():
        # file_name이 없으면 기본으로 artifact_name + ".csv" 같은 규칙을 둘 수도 있음
        # (여기선 안전하게 에러 처리)
        raise ValueError("artifact_locator에는 file_name이 필요합니다. (예: dataset.csv)")

    # 세션/유저 보강 (ADK가 알고 있는 값이 제일 정확)
    user_id = getattr(tool_context, "user_id", None)
    session_id = getattr(tool_context, "session_id", None)

    if not isinstance(session_id, str) or not session_id:
        raise ValueError("tool_context에서 session_id를 얻지 못했습니다.")

    # version 보강: 없으면 디스크에서 최신 버전 탐색
    version = locator.get("version")
    if version is None:
        # ✅ ADK_ARTIFACT_ROOT는 run.py에서 두 프로세스(ADK/MCP)에 동일하게 주입하는 걸 권장
        artifact_root = Path(os.environ.get("ADK_ARTIFACT_ROOT", ".adk")).resolve()

        latest = _latest_version_from_disk(artifact_root, session_id=session_id, artifact_name=artifact_name)
        if latest is None:
            raise ValueError(
                f"최신 버전을 찾지 못했습니다. artifact_name={artifact_name}, session_id={session_id}"
            )
        version = latest

    # 정규화된 locator 구성 (MCP가 이 형태를 신뢰하고 path 조합하면 됨)
    normalized_locator = dict(locator)
    normalized_locator["user_id"] = user_id
    normalized_locator["session_id"] = session_id
    normalized_locator["artifact_name"] = artifact_name
    normalized_locator["file_name"] = file_name
    normalized_locator["version"] = int(version)

    new_args = dict(args)
    new_args["artifact_locator"] = normalized_locator
    return new_args
