"""In-memory store for Plotly figure JSON objects."""

from __future__ import annotations

from typing import Any


class PlotlyStore:
    def __init__(self) -> None:
        self._figs: dict[str, dict[str, Any]] = {}

    def store(self, fig_id: str, title: str, fig: dict[str, Any]) -> None:
        self._figs[fig_id] = {"fig_id": fig_id, "title": title, "fig": fig}

    def get(self, fig_id: str) -> dict[str, Any] | None:
        return self._figs.get(fig_id)

    def remove(self, fig_id: str) -> None:
        self._figs.pop(fig_id, None)

    def remove_by_prefix(self, prefix: str) -> None:
        to_del = [fid for fid in self._figs if fid.startswith(prefix)]
        for fid in to_del:
            self.remove(fid)


# singleton
plotly_store = PlotlyStore()
