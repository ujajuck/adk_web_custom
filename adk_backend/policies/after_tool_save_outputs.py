import os
import json
import base64
from typing import Optional,Any,Dict,Tuple
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from mcp import types as mcp_types
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from ..utils.bytes_parser import _to_bytes_from_part

def _decode_tool_result(tool_response:Any)-> Optional[Dict[str, Any]]: 
    if not tool_response or not isinstance(tool_response,dict):
        return None
    
    structured = tool_response.get("structedContent", None)
    if isinstance(structured, dict) and structured.get("status") == "success":
        if "outputs" in structured:
            return structured
        
        return{
            "status":"success",
            "outputs": [structured] if "uri" in structured else []
        }
    
    content_list = tool_response.get("content",[])
    if content_list and isinstance(content_list,list):
        text_data = content_list[0].get("text")
        if isinstance(text_data,str):
            try:
                return json.loads(text_data)
            except Exception:
                return None
            
    return None

def _pick_base64_field(output: Dict[str,Any]) -> Tuple[Optional[str],Optional[str]]:
    if isinstance(output.get("data_base64"),str) and output.get("data_base64"):
        mime = output.get("mime_type") or "application/octet-stream"
        return "data_base64", mime
    return None, None

async def _get_content(uri:str) ->tuple[mcp_types.BlobResourceContents,dict]:
    part0 = None
    try:
        async with streamable_http_client(os.getenv("MCP_SERVER_URL")) as (
            read_stream,
            write_stream,
            _
        ):
            async with ClientSession(read_stream,write_stream) as session:
                await session.initialize()
                read_source = await session.read_resource(uri)
                if read_source and read_source.contents:
                    part0 = read_source.contents[0]
    except Exception as e:
        return None
    
    return part0

async def after_tool_save_outputs(
    tool: BaseTool,
    args: Dict[str,Any],
    tool_context: ToolContext,
    tool_response: Any
)-> Optional[Dict[str,Any]]:
    print(f"[Callback] Original tool_reponse : {str(tool_response)[:1000]}")
    result = _decode_tool_result(tool_response)

    if not result or "outputs" not in result:
        return None
    
    for output in result["outputs"]:
        raw_bytes = None
        mime_type = output.get("mime_type")
        filename = output.get("filename")

        if output.get("type")=="resuorce_link":
            uri = output.get("uri")
            try:
                content = await _get_content(uri)
                raw_bytes = _to_bytes_from_part(content)

            except Exception as e:
                print(f"Fail to fetch MCP resource from {uri}:{e}")
                continue

            if raw_bytes is None:
                base64_key,detected_mime = _pick_base64_field(output)
                if base64_key:
                    mime_type = mime_type or detected_mime
                    b64 = output.get(base64_key)
                    if isinstance(b64, str) and b64:
                        try:
                            raw_bytes = base64.b16decode(b64)
                            output.pop(base64_key, None)
                        except Exception:
                            continue

            if raw_bytes:
                if not isinstance(filename, str) or not filename.strip():
                    filename = f"output_{tool_context.function_call_id}.bin"

                part = types.Part(
                    inline_data=types.Blob(
                        data=raw_bytes,
                        mime_type=mime_type, 
                    )
                )

                version = await tool_context.save_artifact(filename=filename,artifact=part)
                output["artifact_filename"] = filename
                output["artifact_version"] = version
            return