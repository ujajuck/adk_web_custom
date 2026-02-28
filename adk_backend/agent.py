
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm 
from google.adk.apps import App
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin
from google.adk.tools import load_artifacts 
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams


from .tools.get_data import load_csv_from_path_and_save_artifact
from .tools.get_current_time import get_current_time
from .utils.read_artifact_preview import read_artifact_preview
from .safelitellm import SafeLiteLlm

from .tools.get_current_time import get_current_time

OLLAMA_API_BASE = "http://localhost:11434/v1"
OLLAMA_API_MODEL = "openai/gpt-oss:latest"
OPENAI_API_KEY = "ollama"
MCP_URL = "http://localhost:8001/mcp"

litellm_model = SafeLiteLlm(
    OLLAMA_API_MODEL,
    api_base=OLLAMA_API_BASE,
    api_key="",    
    supports_vision=False,
    supports_audio=False,
)

from google.adk.tools.tool_context import ToolContext
from .callback.before_tool_callback_router import before_tool_callback_router
from .callback.after_tool_callback_router import after_tool_callback_router

async def debug_context(tool_context: ToolContext) -> str:
    """현재 실행 컨텍스트(app/user/session)와 보이는 아티팩트 목록을 반환합니다."""
    artifacts = await tool_context.list_artifacts() 
    return (
        f"app_name={tool_context.app_name}\n"
        f"user_id={tool_context.user_id}\n"
        f"session_id={tool_context.session_id}\n"
        f"artifacts={artifacts}\n"
    )

root_agent = Agent(
    name="root_agent",
    model=litellm_model,
    instruction=(
        "사용자의 요청에 따라 툴들을 적절히 사용하여 응답한다.\n"
        "요청에 반드시 한국말로 답하며 추측하거나 불확실한 정보를 말하지 않는다.\n\n"
        "## 사용 가능한 툴:\n"
        "- load_csv_from_path_and_save_artifact: CSV 파일을 읽어 아티팩트로 저장\n"
        "- plot_histogram: 히스토그램 그리기 (source_type='artifact', artifact_name, columns 사용)\n"
        "- plot_bar_plot: 막대 그래프 그리기\n"
        "- plot_scatter_plot: 산점도 그리기\n"
        "- plot_line_plot: 선 그래프 그리기\n"
        "- plot_pie_chart: 파이 차트 그리기\n\n"
        "## 시각화 툴 사용법:\n"
        "데이터 시각화 시 source_type='artifact'와 artifact_name으로 저장된 아티팩트를 참조한다.\n"
        "예: plot_histogram(source_type='artifact', artifact_name='input.csv', columns=['weight_kg'])"
    ),
    tools=[
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=MCP_URL,
            ),
        ),
        get_current_time,
        load_csv_from_path_and_save_artifact,
        load_artifacts
    ],
    before_tool_callback=before_tool_callback_router,
    after_tool_callback=after_tool_callback_router,
    # before_model_callback=before_model_callback
)
app = App(
    name="adk_backend",
    root_agent=root_agent,
    plugins=[SaveFilesAsArtifactsPlugin()],
)
# adk api_server --allow_origins="*"

