# plot_toolbox/box_plot.py
def box_plot(values: list[float]) -> dict:
    """박스플롯 요약 통계를 계산한다.

    Args:
        values (list[float]): 수치 데이터 목록

    Returns:
        dict: {"min": float, "max": float} 형태(예시)
    """
    return {"min": min(values), "max": max(values)}
