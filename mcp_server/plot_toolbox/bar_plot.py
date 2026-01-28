import re
import base64
import pandas as pd
import plotly.io as pio
import plotly.graph_objects as go
from typing import List,Dict,Any

def bar_plot(
    labels: List[str],
    values: List[float],
    title: str = "Bar_Chart",
    label_name: str = "category",
    value_name: str = "Value",
    top_k:int =30
    ) -> Dict[str,Any]:

    """
    labels/values로 Plotly 막대그래프를 생성해 JSON(Plotly figure JSON)으로 반환합니다.

    Args:
        labels (List[str]): X축 카테고리 라벨 리스트입니다. values와 길이가 같아야 합니다.
        values (List[float]): 각 라벨에 대응하는 수치 리스트입니다. labels와 길이가 같아야 합니다.
        title (str): 그래프 제목입니다. 기본값은 "Bar Chart" 입니다.
        label_name (str): X축 제목(라벨명)입니다. 기본값은 "category" 입니다.
        value_name (str): Y축 제목 및 trace name(값의 의미)입니다. 기본값은 "Value" 입니다.
        top_k (int): value 기준 내림차순 정렬 후 상위 K개만 시각화합니다. 기본값은 30 입니다.

    Returns:
        Dict[str, Any]: FastMCP 표준 응답 딕셔너리를 반환합니다.
            - 성공 시:
                {
                  "status": "success",
                  "outputs": [
                    { "graph": "<plotly_figure_json_string>" }
                  ]
                }
            - 실패 시(입력 검증 실패: labels/values 비어있음 또는 길이 불일치):
                {
                  "status": "error",
                  "outputs": [
                    { "type": "라벨과 값의 길이는 일치해야 한다." }
                  ]
                }

    Notes:
        - 출력의 "graph" 값은 pio.to_json(fig)로 직렬화된 Plotly Figure JSON 문자열입니다.
        - x축 라벨이 길 경우 가독성을 위해 tickangle=45가 적용됩니다.
    """
    if not labels or not values or len(labels)!=len(values):
        return {
            "status":"error",
            "outputs":[
                {
                    "type":"라벨과 값의 길이는 일치해야 한다.",
                }
            ]
        }
    df = pd.DataFrame({"label":labels, "value": values})
    view_df = df.sort_values("value",ascending=False).head(int(top_k))
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=view_df["label"],
        y=view_df["value"],
        name=value_name
    ))
    fig.update_layout(
        title=title,
        xaxis_title = label_name,
        yaxis_title = value_name,
        template = "plotly_white"
    )
    fig.update_xaxes(tickangle=45)
    fig.show()
    graph_json = pio.to_json(fig)
    #safe_title = re.sub(r'[^\w\s-]',title).strip().replace('','_')///
    png_bytes = fig.to_image(format="png")
    png_base64 = base64.b64encode(png_bytes).decode("utf-8")
    return {
            "status":"success",
            "outputs":[
                {
                    "graph":graph_json
                }
                # ,{
                #     "filename":f"{title}.png",
                #     "mime_type":"image/png",
                #     "data_base64": png_base64
                # }
            ]
        }
