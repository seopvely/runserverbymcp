from mcp.server.fastmcp import FastMCP
import os
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

mcp = FastMCP(
    "Framelink Figma MCP",  # Name of the MCP server
    instructions="You are a framelink figma assistant that can answer questions about the framelink figma project about link.",  # Instructions for the LLM on how to use this tool
    host="0.0.0.0",  # Host address (0.0.0.0 allows connections from any IP)
    port=8006,  # Port number for the server
)

# 환경 변수에서 API 키 가져오기
figma_api_key = os.getenv('FIGMA_API_KEY')
if not figma_api_key:
    raise ValueError("FIGMA_API_KEY 환경 변수가 설정되지 않았습니다.")

@mcp.tool()
async def generating_figma_project_html_css_js_code(figma_api_key: str) -> str:
    """
	피그마 프로젝트 링크를 보고 하이라이트된 디자인된 내용의 html, css, js 코드를 생성해주세요.

    Args:
		figma_api_key: str: The API key for the framelink figma project

    Returns:
        str: A string containing the framelink figma project html, css, js code
    """
    # Return a mock framelink figma project html, css, js code response
    # In a real implementation, this would call a framelink figma project html, css, js code API
    return f"Framelink Figma Project HTML, CSS, JS Code"


if __name__ == "__main__":
    # Print a message indicating the server is starting
    print("mcp framelink figma html, css, js code server is running...")

    # Start the MCP server with SSE transport
    # Server-Sent Events (SSE) transport allows the server to communicate with clients
    # over HTTP, making it suitable for remote/distributed deployments
    mcp.run(transport="sse")
    