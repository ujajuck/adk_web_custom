# ml_toolbox/server.py
from fastmcp import FastMCP
from .linear_regression import linear_regression
from .random_forest_classifier import random_forest_classifier
from .kmeans_clustering import kmeans_clustering
# from .xgboost import xgboost_train  # 구 형식, 필요시 업데이트

ml_toolbox = FastMCP(name="ml_toolbox")

ml_toolbox.tool(linear_regression)
ml_toolbox.tool(random_forest_classifier)
ml_toolbox.tool(kmeans_clustering)
