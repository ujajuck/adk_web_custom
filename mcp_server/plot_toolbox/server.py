# plot_toolbox/server.py
from fastmcp import FastMCP
from .bar_plot import bar_plot
# from .line_plot import line_plot
# from .scatter_plot import scatter_plot

plot_toolbox = FastMCP(name="plot_toolbox")

plot_toolbox.tool(bar_plot)
# plot_toolbox.tool(line_plot)
# plot_toolbox.tool(scatter_plot)
