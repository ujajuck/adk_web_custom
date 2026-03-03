import pandas as pd
from fastmcp import Context
from typing import List, Literal, Optional, Union, Any, Dict, Sequence
from pydantic import BaseModel,Field,ConfigDict
from ..utils.path_resolver import get_artifact_path

class LinePlotSegment(BaseModel):
    name: str
    x: List[Any]
    y_series: Dict[str, List[float]]

class DirectSource(BaseModel):
    source_type: Literal["direct"]
    segments: Sequence[LinePlotSegment]

    def resolve_segments(self,ctx:Context|None=None)->Sequence[LinePlotSegment]:
        return self.segments
    
def build_segments_from_df(
        df:pd.DataFrame,
        *,
        x_col:Optional[str]=None,
        y_cols:Optional[Sequence[str]] = None
)->Sequence[LinePlotSegment]:
    if df is None or df.empty:
        raise ValueError("df 가 비어 있습니다.")
    
    x_name = ""
    if x_col is None or str(x_col).strip() =="":
        x_values : List[Any] = df.index.to_list()
        x_name = "(index)"
    else:
        if x_col not in df.columns:
            raise ValueError(f"x_cols='{x_col}' 컬럼이 DataFrame에 없습니다.")
        x_values = df[x_col].to_list()
        y_name = x_col
    
    y_series: Dict[str,List[float]] = {}
    for y in y_cols:
        y_series[y] = pd.to_numeric(df[y],errors="coerce").tolist()

    seg = LinePlotSegment(name=x_name,x=x_values,y=y_series)
    
    return [seg]

class AritfactSource(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source_type : Literal["artifact"]
    artifact_name:str
    user_id : Optional[str] = None
    session_id : Optional[str] = None  
    version: Optional[int] = 0
    x_col : Optional[str] = None
    y_cols: Optional[List[str]] = None

    def resolve_segments(self, ctx:Context|None=None) -> Sequence[LinePlotSegment]:
        csv_path = get_artifact_path(user_id=self.user_id,session_id=self.session_id,artifact_name=self.artifact_name,version=self.version)
        df = pd.read_csv(csv_path)
        return build_segments_from_df(df=df,x_col=self.x_col,y_cols=self.y_cols)
    
class FileSource(BaseModel):
    source_type : Literal["file"]
    path:str
    columns:List[str]


ChartSource = Union[AritfactSource,FileSource,DirectSource]

class LineChartRequest(BaseModel):
    source : ChartSource = Field(...,discriminator="source_type")
    title: str = "Line_Plot"
    x_mode:Literal["concat","align","keep"] = "concat"
    add_boundaries : bool = True
    hovermode : str = "x unitied"