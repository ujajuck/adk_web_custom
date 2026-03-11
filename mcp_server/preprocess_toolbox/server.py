# preprocess_toolbox/server.py
from fastmcp import FastMCP
from .fill_missing import fill_missing
from .normalize import normalize
from .encode_categorical import encode_categorical
from .remove_outliers import remove_outliers
from .scale_features import scale_features
from .train_test_split import train_test_split

preprocess_toolbox = FastMCP(name="preprocess_toolbox")

preprocess_toolbox.tool(fill_missing)
preprocess_toolbox.tool(normalize)
preprocess_toolbox.tool(encode_categorical)
preprocess_toolbox.tool(remove_outliers)
preprocess_toolbox.tool(scale_features)
preprocess_toolbox.tool(train_test_split)
