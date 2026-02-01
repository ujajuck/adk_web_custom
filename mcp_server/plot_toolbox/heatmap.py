import re
import base64
import pandas as pd 
import numpy as np
import plotly.express as px
import plotly.io as pio
from typing import Any,Dict,List

def histogram(
    data: List[Dict[str,Any]],
    method : str = "pearson"
)-> Dict[str,Any]:
    """
    데이터의 상관관계 히트맵을 생성하고 표준 출력 형식으로 반환합니다.
    
    Args:
        data: 히트맵을 계산할 데이터
        method: 상관계수 계산 방법 'pearson','kendall','spearman' 중 선택가능 (기본값: 'pearson')
    """
    corr = pd.DataFrame(data)
    mask = np.triu(np.ones_like(corr,dtype=bool),k=0)
    masked_corr = corr.mask(mask)
    fig = px.imshow(
        masked_corr,
        text_auto=".2f",
        aspect="auto",
        color_continuous_scale="RdBu_r",
        range_color=[-1,1],
        labels=dict(color = "Correlation"),
        title = f"Correlation heatmap({method})"
    )
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        width = max(600,corr.shape[1]*40),
        height = max(500,corr.shape[0]*40),
        margin = dict(l=50,r=50,t=80,b=50)
    )
    html_str = pio.to_html(fig,full_html=True,include_plotlyjs="cdn")
    html_bytes = html_str.encode("utf-8")
    html_base64 = base64.b64encode(html_bytes).decode("utf-8")
    png_bytes = fig.to_image(format="png")
    png_base64 = base64.b64encode(png_bytes).decode("utf-8")

    return {
        "status":"error",
        "outputs" : [
            {
                "filename": "heatmap.html",
                "mime_type": "text/html",
                "data_base64": html_base64
            }
        ]
    }