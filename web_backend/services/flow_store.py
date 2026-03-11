"""Flow store – in-memory storage for artifact flow graphs.

세션별로 아티팩트 흐름 그래프를 저장하고 조회한다.
"""

from __future__ import annotations

import logging
from typing import Optional
from threading import Lock

from .flow_parser import ArtifactFlow

log = logging.getLogger(__name__)


class FlowStore:
    """세션별 아티팩트 흐름 저장소."""

    def __init__(self) -> None:
        self._flows: dict[str, ArtifactFlow] = {}
        self._lock = Lock()

    def get(self, session_id: str) -> Optional[ArtifactFlow]:
        """세션의 플로우 조회."""
        with self._lock:
            return self._flows.get(session_id)

    def get_or_create(self, session_id: str) -> ArtifactFlow:
        """세션의 플로우 조회 또는 생성."""
        with self._lock:
            if session_id not in self._flows:
                self._flows[session_id] = ArtifactFlow(session_id=session_id)
            return self._flows[session_id]

    def update(self, session_id: str, flow: ArtifactFlow) -> None:
        """세션의 플로우 업데이트."""
        with self._lock:
            self._flows[session_id] = flow
            log.debug(
                "Updated flow for session %s: %d nodes, %d edges",
                session_id,
                len(flow.nodes),
                len(flow.edges),
            )

    def delete(self, session_id: str) -> bool:
        """세션의 플로우 삭제."""
        with self._lock:
            if session_id in self._flows:
                del self._flows[session_id]
                return True
            return False

    def list_sessions(self) -> list[str]:
        """플로우가 있는 세션 목록."""
        with self._lock:
            return list(self._flows.keys())

    def clear(self) -> None:
        """모든 플로우 삭제."""
        with self._lock:
            self._flows.clear()


# 싱글톤 인스턴스
flow_store = FlowStore()
