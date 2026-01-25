import plotly.graph_objects as go

def bar_plot(labels: list, values: list, title: str = "Bar Chart") -> go.Figure:
    """
    라벨과 수치 리스트를 받아 Plotly Bar 차트 객체를 생성합니다.
    
    Args:
        labels: X축에 표시될 항목 리스트 (예: ['A', 'B', 'C'])
        values: Y축에 표시될 수치 리스트 (예: [10, 20, 30])
        title: 그래프의 제목
    """
    # 1. Plotly Figure 생성
    fig = go.Figure(data=[
        go.Bar(x=labels, y=values)
    ])

    # 2. 레이아웃 설정
    fig.update_layout(
        title=title,
        xaxis_title="Category",
        yaxis_title="Value",
        template="plotly_white"
    )

    # 3. Figure 객체 리턴
    return fig
