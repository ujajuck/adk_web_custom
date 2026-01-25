
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
from .callback.before_tool_router import before_tool_callback_router

async def debug_context(tool_context: ToolContext) -> str:
    """현재 실행 컨텍스트(app/user/session)와 보이는 아티팩트 목록을 반환합니다."""
    artifacts = await tool_context.list_artifacts()  # ADK 문서에 나온 listing 메서드 :contentReference[oaicite:3]{index=3}
    return (
        f"app_name={tool_context.app_name}\n"
        f"user_id={tool_context.user_id}\n"
        f"session_id={tool_context.session_id}\n"
        f"artifacts={artifacts}\n"
    )

root_agent = Agent(
    name="root_agent",
    model=litellm_model,
    description="사용자의 요청에 따라 툴들을 적절히 사용하여 응답한다.",
    # instruction=(
    #     "파일이 업로드되면 먼저 list_artifacts를 호출해서 파일명을 확인한다.\n"
    #     "사용자가 특정 파일을 지정하면 read_artifact_preview 또는 read_table_artifact를 한 번만 호출해서 내용을 읽고 요약한다.\n"
    #     "같은 파일을 반복해서 자동 호출하지 않는다."
    # ),
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
    # before_model_callback=before_model_callback
)
app = App(
    name="adk_backend",
    root_agent=root_agent,
    plugins=[SaveFilesAsArtifactsPlugin()],
)
# adk api_server --allow_origins="*"

