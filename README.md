# Azure AI Foundry Sample Applications

This repository contains sample Python applications demonstrating how to interact with Azure AI Foundry using the Python SDK.

## Which Client Should I Use?

| Scenario | Recommended Client | Why |
|----------|-------------------|-----|
| **Development & Testing** | `clients/project/foundry-agent-app.py` | Full features, server-side conversations, MCP approval flow |
| **Production Applications** | `clients/project/foundry-agent-app.py` | Best capabilities, tracing, conversation management |
| **Simple LLM Queries** | `clients/project/foundry-client-app.py` | Direct model access without agent overhead |
| **External Sharing (Limited)** | `clients/published/foundry-app-client.py` | Isolated endpoint, no project access needed |

### ⚠️ Project Clients vs Published App Clients

**Project Clients are generally preferred** for most use cases:

| Feature | Project Client | Published App Client |
|---------|---------------|---------------------|
| Conversation Management | ✅ Server-side (`conversation.id`) | ❌ Client-side only |
| MCP Approval Flow | ✅ Full support | ❌ Must use `require_approval="never"` |
| File Uploads | ✅ Supported | ❌ Not available |
| Vector Stores | ✅ Supported | ❌ Not available |
| Tracing & Telemetry | ✅ Built-in | ⚠️ Limited |
| SDK Features | ✅ Full access | ⚠️ Responses API only |

**When to use Published App Clients:**
- Sharing a specific agent externally without exposing your project
- Need isolated endpoint URL for a single agent
- Separate rate limiting/quota management

## Overview

### Project Clients (`clients/project/`) — **Recommended**
For interacting with agents and models directly in your AI Foundry project. Provides full SDK capabilities including server-side conversation management, MCP approval workflows, and integrated tracing.

| File | Description |
|------|-------------|
| `foundry-client-app.py` | Direct model interaction using the Responses API |
| `foundry-agent-app.py` | **Recommended** - Agent with MCP support, conversation management, tracing |

### Published App Clients (`clients/published/`) — Limited Use Cases
For interacting with published Agent Applications. These are simplified wrappers with reduced capabilities - use only when you need an isolated external endpoint.

| File | Description |
|------|-------------|
| `foundry-app-client.py` | Client for published Agent Applications (stateless) |
| `foundry-app-client-streaming.py` | Streaming client with real-time token output (stateless) |
| `structured-output-client.py` | Test client for agents with JSON schema structured output |

### Ops Scripts (`ops/`)
For programmatic agent management.

| File | Description |
|------|-------------|
| `create-agent.py` | Create agents (interactive wizard or CI/CD mode) |
| `create-structured-output-agent.py` | Create an agent with JSON schema structured output |
| `update-agent.py` | Update existing agents (MCP settings, instructions, etc.) |

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

# Required for foundry-app-client.py (Published Agent Application)
# Format: https://<resource>.services.ai.azure.com/api/projects/<project>/applications/<app-name>/protocols/openai
AZURE_AI_FOUNDRY_APP_ENDPOINT=https://your-resource.services.ai.azure.com/api/projects/your-project/applications/your-app-name/protocols/openai

# Required for structured-output-client.py (Structured Output Test Agent)
AZURE_AI_FOUNDRY_STRUCTURED_OUTPUT_APP_ENDPOINT=https://your-resource.services.ai.azure.com/api/projects/your-project/applications/structured-output-test-agent/protocols/openai

# Knowledge Base MCP Configuration (for agents with KB tools)
AZURE_AI_SEARCH_KB_MCP_ENDPOINT=https://<search>.search.windows.net/knowledgebases/<kb>/mcp?api-version=2025-11-01-Preview
AZURE_AI_SEARCH_KB_CONNECTION_NAME=your-connection-name
AZURE_AI_SEARCH_KB_SERVER_LABEL=knowledge-base

# MCP Tool Approval Setting
# "never" = auto-approve (required for published apps)
# "always" = require manual approval
AZURE_AI_MCP_REQUIRE_APPROVAL=never
```

## Usage

### Project Clients — Recommended

#### Foundry Client App (Direct Model Interaction)

This script interacts directly with a deployed model without using an agent. Best for simple LLM interactions without tools or knowledge bases.

```powershell
python clients/project/foundry-client-app.py
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

#### Foundry Agent App (Agent with MCP Support) — **Best Choice**

This is the **recommended client** for most use cases. It interacts with a pre-configured agent that has access to knowledge bases and tools via MCP (Model Context Protocol).

```powershell
python clients/project/foundry-agent-app.py
```

**Features:**
- ✅ Connects to a named agent configured in Azure AI Foundry portal
- ✅ Server-side conversation management (no client-side history needed)
- ✅ Full MCP approval workflow support
- ✅ Built-in tracing to Azure Application Insights
- ✅ Multi-turn conversations with context preservation
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

### Published App Clients — Limited Use Cases

> ⚠️ **Note:** Published App Clients have significant limitations compared to Project Clients. 
> Use these only when you need to share an agent externally without exposing your project.

#### Foundry App Client (Published Agent Application)

This script interacts with a **published** Agent Application using the OpenAI SDK directly. Published applications expose a dedicated endpoint but with reduced capabilities.

```powershell
python clients/published/foundry-app-client.py
```

**Features:**
- Connects to a published Agent Application endpoint
- Uses OpenAI SDK with Azure AD authentication
- Client-side conversation history management (not server-side)
- Type `new` to start a fresh conversation
- Press `Ctrl+C` to exit

**Limitations vs Project Client:**

| Aspect | Project Client ✅ | Published App Client ⚠️ |
|--------|------------------|-------------------------|
| Conversation | Server-side (automatic) | Client-side (manual) |
| MCP Approval | Full workflow support | Must be `require_approval="never"` |
| File/Vector Stores | ✅ Available | ❌ Not available |
| Tracing | ✅ Built-in | ⚠️ Limited |
| Use Case | All applications | External sharing only |

**Example:**
```
Connected to Published Agent Application!
Type 'new' to start a fresh conversation, Ctrl+C to exit.

You: What's the weather in Seattle?
Assistant: The current weather in Seattle is...
```

#### Foundry App Client Streaming (Real-time Token Output)

This script provides streaming responses from published Agent Applications, displaying tokens as they're generated.

```powershell
python clients/published/foundry-app-client-streaming.py
```

**Features:**
- Real-time token streaming (see responses as they're generated)
- Same limitations as non-streaming published app client
- Type `new` to start a fresh conversation
- Press `Ctrl+C` to exit

#### Structured Output Client (JSON Schema Responses)

This script tests agents configured with structured JSON output. The agent always responds with a predefined JSON schema.

```powershell
# Run automated tests
python clients/published/structured-output-client.py

# Interactive mode for custom questions
python clients/published/structured-output-client.py --interactive
```

**Expected Response Format:**
```json
{
  "question": "<user's original question>",
  "response": "<assistant's answer>"
}
```

**Features:**
- Tests structured output configured at agent creation time
- Validates JSON schema adherence
- Automated test suite with 3 sample questions
- Interactive mode for custom testing

**Note:** Structured output must be configured when creating the agent (see `ops/create-structured-output-agent.py`). It cannot be overridden at runtime for published agents.

### Ops Scripts (Agent Management)

The `ops/` folder contains scripts for programmatic agent management.

#### Create Agent

Create new agents with optional Knowledge Base MCP tools:

```powershell
# Interactive mode (wizard)
python ops/create-agent.py

# Non-interactive mode (CI/CD)
python ops/create-agent.py --non-interactive --name my-agent

# With Knowledge Base MCP tool
python ops/create-agent.py --non-interactive --name my-kb-agent --with-kb
```

#### Create Structured Output Agent

Create an agent that always responds with structured JSON output:

```powershell
python ops/create-structured-output-agent.py
```

This creates an agent with a JSON schema that enforces responses in this format:
```json
{
  "question": "<user's original question>",
  "response": "<assistant's answer>"
}
```

**Key Points:**
- Uses `ResponseTextFormatConfigurationJsonSchema` with `strict=True`
- No tools or knowledge base - focused on testing structured output
- Must publish the agent in Azure AI Foundry portal after creation
- Test with `clients/published/structured-output-client.py`

**Important:** Structured output is configured at agent creation time and cannot be overridden at runtime when calling published agents. This is different from direct model calls where you can specify `text.format` per request.

#### Update Agent

Update existing agents (MCP settings, instructions, description):

```powershell
# Interactive mode
python ops/update-agent.py

# Update MCP require_approval setting (uses AZURE_AI_MCP_REQUIRE_APPROVAL from .env)
python ops/update-agent.py --non-interactive --update-mcp

# Update instructions
python ops/update-agent.py --non-interactive --instructions "New system prompt..."
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

## Tracing & Telemetry

The `foundry-agent-app.py` includes built-in tracing to Azure Application Insights, capturing:

- **Duration**: How long each request takes
- **Token Usage**: Input/output tokens per request
- **Custom Attributes**: Conversation ID, agent name, response IDs
- **Child Spans**: MCP tool calls, model invocations

### Setup

1. **Enable Application Insights** in your Azure AI Foundry project settings
2. **Install tracing packages** (included in requirements.txt):
   ```powershell
   pip install opentelemetry-sdk azure-core-tracing-opentelemetry azure-monitor-opentelemetry
   ```
3. Run the app - tracing is automatically configured

### View Traces

Open your Azure AI Foundry project in the portal and navigate to the **Tracing** tab to see:
- Request durations
- Token consumption
- Error traces
- MCP tool call details

### Environment Variables (Optional)

```env
# Include message content in traces (may contain sensitive data)
OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true

# Disable automatic tracing (not recommended)
AZURE_TRACING_GEN_AI_INSTRUMENT_RESPONSES_API=false
```

### Azure Container Apps

When deploying to Azure Container Apps, tracing works automatically if:
1. Your Foundry project has Application Insights enabled
2. The container has network access to Application Insights
3. `DefaultAzureCredential` can authenticate (via Managed Identity)

## Project Structure

```
sample-1/
├── .env                          # Environment variables (not in git)
├── .env.example                  # Template for .env
├── .gitignore
├── README.md
├── requirements.txt              # Python dependencies
├── clients/
│   ├── project/                  # Project-level clients (dev/test)
│   │   ├── foundry-client-app.py     # Direct model interaction
│   │   └── foundry-agent-app.py      # Agent with MCP support
│   └── published/                # Published app clients (production)
│       ├── foundry-app-client.py     # Non-streaming client
│       └── foundry-app-client-streaming.py  # Streaming client
└── ops/
    ├── create-agent.py           # Create agents (interactive/non-interactive)
    └── update-agent.py           # Update agents (MCP, instructions, etc.)
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
