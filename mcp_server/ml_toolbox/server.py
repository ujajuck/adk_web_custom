# ml_toolbox/server.py
from fastmcp import FastMCP
from .xgboost import xgboost_train
# from .randomforest import randomforest_train

ml_toolbox = FastMCP(name="ml_toolbox")

ml_toolbox.tool(xgboost_train)
# ml_toolbox.tool(randomforest_train)
