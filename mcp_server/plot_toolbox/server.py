# plot_toolbox/server.py
from fastmcp import FastMCP
from .bar_plot import bar_plot
from .histogram import histogram
from .scatter_plot import scatter_plot
from .line_plot import line_plot
from .pie_chart import pie_chart

plot_toolbox = FastMCP(name="plot_toolbox")

plot_toolbox.tool(bar_plot)
plot_toolbox.tool(histogram)
plot_toolbox.tool(scatter_plot)
plot_toolbox.tool(line_plot)
plot_toolbox.tool(pie_chart)
