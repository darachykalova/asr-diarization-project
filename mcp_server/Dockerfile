# Собирается ПОСЛЕ asr-app (как call-agent):
#   docker compose build api && docker compose build mcp-server
FROM asr-app

COPY mcp_server/requirements.txt /app/mcp_server/requirements.txt
RUN pip install --no-cache-dir -r /app/mcp_server/requirements.txt
COPY mcp_server/ /app/mcp_server/

ENV MCP_TRANSPORT=http
CMD ["python", "mcp_server/server.py"]
