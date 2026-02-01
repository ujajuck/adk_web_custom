import re
import uuid
import base64
import pandas as pd 
import numpy as np
import plotly.io as pio
import plotly.graph_objects as go
import plotly.figure_factory as figure_factory
from typing import Any,Dict,List
from ..utils.path_resolver import resolve_artifact_path,get_mcp_resource_path 


def histogram(
    embedding_1d: List[float],
    labels : List[str] =[],
    title : str = "1D Distribution Analysis"
)-> Dict[str,Any]:
    """
    1차원 차원 축소 데이터를 히스토그램과 밀도 곡선(KDE)으로 시각화합니다.

    Args:
        embedding_1d(list): 1차원 수치 리스트[val1,val2,...]
        labels(list): 각 데이터의 타겟 레이블
        title(str):차트 제목
    """
    try:
        if not embedding_1d or len(embedding_1d)<2:
            return {"status":"error","outputs":[{"message":"데이터가 부족합니다"}]}
        df= pd.DataFrame({"val":embedding_1d,"label":labels if labels else "Total"})
        hist_data = []
        group_labels = []

        has_variance = True
        for g_name,g_df in df.groupby("label"):
            vals = g_df["val"].to_list()
            if len(vals) >= 2:
                hist_data.append(vals)
                group_labels.append(str(g_name))
                if np.std(vals)<1e-9:
                    has_variance = False

            if not hist_data:
                return {"status":"error","outputs":[{"message":"유효한 데이터 그룹이 없습니다."}]}
            
            if not has_variance:
                fig = go.Figure()
                for i,data in enumerate(hist_data):
                    fig.add_trace(go.Histogram(x=data,name=group_labels[i],opacity=0.75))
                fig.update_layout(barmode='overlay',title_text = title)
            else:
                fig = figure_factory.create_distplot(hist_data=hist_data,group_labels=group_labels,show_hist=True,show_rug=True)
                fig.update_layout(title_text=title)
            
            fig.update_layout(template="plotly_white")

            html_str = pio.to_html(fig,full_html=True,include_plotlyjs="cdn")
            html_bytes = html_str.encode("utf-8")
            html_base64 = base64.b64encode(html_bytes).decode("utf-8")
            png_bytes = fig.to_image(format="png")
            png_base64 = base64.b64encode(png_bytes).decode("utf-8")
            graph_json = pio.to_json(fig)

            job_id = uuid.uuid4().hex
            get_mcp_resource_path(graph_json,job_id)

            safe_title = re.sub(r'[^\w\s-]',title).strip().replace('','_')


            return {
                "status":"error",
                "outputs" : [
                    {
                        "type": "resource_link",
                        "uri":f"mcp://resource/{job_id}.json",
                        "filename":safe_title,
                        "mime_type" : "application/json",
                        "description":f"입력된 데이터 셋의 히스토그램입니다."
                    }
                ]
            }
    except Exception as e:
        return {"status":"error","outputs":[{"message":f"histogram 생성오류: {str(e)}"}]}
            
