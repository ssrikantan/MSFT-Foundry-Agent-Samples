# Azure AI Foundry Sample Applications

This repository contains sample Python applications demonstrating how to interact with Azure AI Foundry using the Python SDK.

## Overview

| File | Description |
|------|-------------|
| `foundry-client-app.py` | Direct model interaction using the Responses API |
| `foundry-agent-app.py` | Agent-based interaction with MCP (Model Context Protocol) support |
| `ops/create-agent.py` | Programmatically create agents in Azure AI Foundry |

## Prerequisites

- Python 3.10+
- Azure subscription with Azure AI Foundry access
- Azure CLI installed and authenticated (`az login`)

## Setup

### 1. Create a Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
# Required for all scripts
AZURE_AI_FOUNDRY_PROJECT_ENDPOINT=https://your-project.services.ai.azure.com/api/projects/your-project-id

# Required for foundry-client-app.py and ops/create-agent.py
AZURE_AI_FOUNDRY_MODEL_DEPLOYMENT_NAME=gpt-4o

# Required for foundry-agent-app.py
AZURE_AI_FOUNDRY_AGENT_NAME=your-agent-name
```

## Usage

### Foundry Client App (Direct Model Interaction)

This script interacts directly with a deployed model without using an agent. Best for simple LLM interactions without tools or knowledge bases.

```powershell
python foundry-client-app.py
```

**Features:**
- Interactive chat loop with continuous user input
- Multi-turn conversations with server-side context (via conversation ID)
- Type `new` to start a fresh conversation
- Press `Ctrl+C` to exit

**Example:**
```
You: What is the capital of France?
Assistant: The capital of France is Paris.

You: What's its population?
Assistant: Paris has a population of approximately 2.1 million people in the city proper...
```

### Foundry Agent App (Agent with MCP Support)

This script interacts with a pre-configured agent that has access to knowledge bases and tools via MCP (Model Context Protocol).

```powershell
python foundry-agent-app.py
```

**Features:**
- Connects to a named agent configured in Azure AI Foundry portal
- Automatic approval of MCP tool calls (e.g., knowledge base queries)
- Multi-turn conversations with context preservation
- Type `new` to start a fresh conversation
- Press `Ctrl+C` to exit

**Example:**
```
You: What insurance policies does Contoso offer?
Approving MCP request: mcpr_xxx...
Assistant: Contoso offers the following insurance policies...

You: How do they compare with competitors?
Approving MCP request: mcpr_xxx...
Assistant: Compared to other providers...
```

### Create Agent (Programmatic Agent Creation)

This script demonstrates how to create agents programmatically using the SDK.

```powershell
python ops/create-agent.py
```

**Note:** Agent names must:
- Start and end with alphanumeric characters
- Only contain hyphens (not underscores) in the middle
- Not exceed 63 characters

## Key Concepts

### Conversations

Both apps use the `conversations` API to maintain context across multiple exchanges:

```python
conversation = openai_client.conversations.create()
response = openai_client.responses.create(
    conversation=conversation.id,
    input="Your message here",
)
```

### MCP (Model Context Protocol)

When an agent uses MCP-enabled tools (like knowledge bases), it returns approval requests that must be handled:

1. Agent sends response with `mcp_approval_request` items
2. Client approves by sending `mcp_approval_response`
3. Agent continues with the approved tool call
4. Process repeats until response is complete

The `foundry-agent-app.py` handles this automatically with the `process_response_with_mcp_approval()` function.

### Response Chaining

For follow-up messages with MCP agents, use `previous_response_id` instead of `conversation` to maintain the approval chain:

```python
# First message
response = openai_client.responses.create(
    conversation=conversation.id,
    input="First question",
)

# Follow-up message
response = openai_client.responses.create(
    previous_response_id=response.id,
    input="Follow-up question",
)
```

## Authentication

All scripts use `DefaultAzureCredential` which supports multiple authentication methods:

1. **Azure CLI** - Run `az login` before running the scripts
2. **Managed Identity** - Works automatically in Azure environments
3. **Environment Variables** - Set `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`
4. **Visual Studio Code** - Uses VS Code Azure account

## Project Structure

```
sample-1/
├── .env                      # Environment variables (not in git)
├── .gitignore
├── README.md
├── requirements.txt          # Python dependencies
├── foundry-client-app.py     # Direct model interaction
├── foundry-agent-app.py      # Agent with MCP support
└── ops/
    └── create-agent.py       # Programmatic agent creation
```

## Troubleshooting

### "MCP approval requests do not have an approval"

This error occurs when an agent tries to use MCP tools but the approval flow isn't handled. The `foundry-agent-app.py` handles this automatically. If you're building your own app, implement the MCP approval loop as shown in the code.

### "Cannot provide both 'previous_response_id' and 'conversation'"

You can only use one of these parameters per request:
- Use `conversation` for the first message
- Use `previous_response_id` for follow-ups (especially with MCP agents)

### Agent name validation errors

Ensure agent names:
- Use hyphens instead of underscores (`my-agent` not `my_agent`)
- Start and end with alphanumeric characters
- Are 63 characters or less

## License

MIT
