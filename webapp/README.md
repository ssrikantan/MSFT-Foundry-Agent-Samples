# Foundry Agent Web App

A modern, responsive chat interface for Azure AI Foundry Published Agents with real-time streaming and tool action visibility.

## Features

- 🚀 **Real-time Streaming** - Token-by-token response streaming via SSE
- 🔧 **Tool Visibility** - ChatGPT-style expandable cards showing agent actions
- 🌙 **Dark Mode** - Automatic theme switching based on system preference
- 📱 **Responsive** - Works on desktop and mobile devices
- 📚 **Citations** - Display source references when available

## Quick Start

### 1. Install Dependencies

```bash
# From the webapp directory
pip install fastapi uvicorn

# Or add to your requirements.txt
```

### 2. Configure Environment

Make sure your `.env` file in the project root has:

```env
AZURE_AI_FOUNDRY_APP_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>/applications/<app-name>/protocols/openai
```

### 3. Run the Server

```bash
# From the webapp directory
cd webapp
uvicorn server:app --reload --port 8000

# Or run directly with Python
python server.py
```

### 4. Open the App

Navigate to: **http://localhost:8000**

## Project Structure

```
webapp/
├── server.py           # FastAPI backend with SSE streaming
├── static/
│   ├── index.html      # Main chat interface
│   ├── styles.css      # Modern responsive styling
│   └── app.js          # Frontend logic & SSE handling
└── README.md           # This file
```

## How It Works

### Backend (server.py)

The FastAPI server:
1. Authenticates with Azure AD using `DefaultAzureCredential`
2. Connects to your published Foundry agent endpoint
3. Streams responses via Server-Sent Events (SSE)
4. Forwards tool/MCP events for UI display

### Frontend (static/)

The web interface:
1. Sends chat messages to the `/chat` endpoint
2. Receives SSE events for text, tools, and citations
3. Displays tool actions as expandable cards
4. Streams text with a typing cursor effect

## SSE Event Types

| Event | Description |
|-------|-------------|
| `text_delta` | Streaming text content |
| `tool_start` | Tool call started |
| `tool_args` | Tool arguments (for expandable display) |
| `tool_done` | Tool call completed |
| `tool_discovery` | Searching knowledge base |
| `citations` | Source references |
| `done` | Stream complete |
| `error` | Error occurred |

## Customization

### Styling

Edit `static/styles.css` to customize:
- Colors (CSS variables in `:root`)
- Typography (font-family, sizes)
- Layout (max-width, spacing)

### Example Prompts

Edit `static/index.html` to change the welcome screen example buttons.

### Tool Display

Edit `static/app.js` to customize how tool cards are rendered:
- `addToolCard()` - Tool card creation
- `formatToolName()` - Name formatting
- `updateToolArguments()` - Argument display

## Troubleshooting

### "AZURE_AI_FOUNDRY_APP_ENDPOINT not set"

Ensure your `.env` file is in the project root (parent of `webapp/`) and contains the endpoint URL.

### Authentication Errors

1. Run `az login` to authenticate with Azure CLI
2. Ensure you have access to the published agent
3. Check that the endpoint URL is correct

### CORS Issues

The server includes CORS middleware for local development. For production, update the `allow_origins` list in `server.py`.

## Dependencies

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `openai` - Azure OpenAI SDK
- `azure-identity` - Azure authentication
- `python-dotenv` - Environment variables
