# ml_toolbox/server.py
from fastmcp import FastMCP
from .linear_regression import linear_regression
from .random_forest_classifier import random_forest_classifier
from .kmeans_clustering import kmeans_clustering
from .logistic_regression import logistic_regression
from .decision_tree import decision_tree
from .pca import pca

ml_toolbox = FastMCP(name="ml_toolbox")

ml_toolbox.tool(linear_regression)
ml_toolbox.tool(random_forest_classifier)
ml_toolbox.tool(kmeans_clustering)
ml_toolbox.tool(logistic_regression)
ml_toolbox.tool(decision_tree)
ml_toolbox.tool(pca)
