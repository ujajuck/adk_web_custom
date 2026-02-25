# preprocess_toolbox/server.py
from fastmcp import FastMCP
from .fill_missing import fill_missing
from .normalize import normalize
from .encode_categorical import encode_categorical
# from .remove_sparse_columns import remove_sparse_columns  # 구 형식, 필요시 업데이트

preprocess_toolbox = FastMCP(name="preprocess_toolbox")

preprocess_toolbox.tool(fill_missing)
preprocess_toolbox.tool(normalize)
preprocess_toolbox.tool(encode_categorical)
