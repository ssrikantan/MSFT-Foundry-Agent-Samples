"""
Foundry Agent App - Agent-Based Interaction with MCP Support (Interactive Mode)
================================================================================

This script demonstrates how to interact with a pre-configured agent in Azure AI Foundry
that uses MCP (Model Context Protocol) to access external tools and knowledge bases.

Use Case:
---------
- Chat with agents configured in the Azure AI Foundry portal
- Access knowledge bases (e.g., Azure AI Search, Bing grounding) through MCP
- Multi-turn conversations with context preservation via server-side conversation
- Automatic approval of MCP tool calls for seamless agent execution
- Interactive chat sessions with continuous user input

Key Concepts:
-------------
1. Agent Reference: Instead of specifying a model, we reference a named agent
   configured in AI Foundry using extra_body={"agent": {"name": ..., "type": "agent_reference"}}

2. MCP (Model Context Protocol): A protocol that allows agents to call external tools
   and knowledge bases. When an agent needs to use MCP tools, it returns an
   "mcp_approval_request" that must be approved before execution continues.

3. Conversations: Used for multi-turn interactions. The conversation ID maintains
   all context server-side across multiple exchanges.

4. Response Chaining: For follow-up questions, we add user messages to the
   conversation first, then request agent responses with conversation ID.
   This ensures all user queries link to the conversation in traces.

5. Tracing: Telemetry is sent to Azure Application Insights for observability.
   View traces in the "Tracing" tab of your Foundry project portal.
   Captures: duration, token usage, model info, and message content (if enabled).
   Note: MCP approval continuations use previous_response_id and may show "--"
   for Conversation ID in traces, which is expected behavior.

MCP Approval Flow:
------------------
1. Agent sends a response with status="incomplete" and mcp_approval_request items
2. Client approves/rejects each request by sending mcp_approval_response
3. Agent continues execution with approved tool calls
4. This repeats until the response is complete

Performance Optimizations:
--------------------------
- Clients are initialized once at startup and reused for all requests
- Conversation is created once and maintained throughout the session
- Agent name is cached to avoid repeated environment lookups

Required Environment Variables:
-------------------------------
- AZURE_AI_FOUNDRY_PROJECT_ENDPOINT: The endpoint URL for your AI Foundry project
- AZURE_AI_FOUNDRY_AGENT_NAME: The name of the agent configured in AI Foundry

Optional Environment Variables (Tracing):
-----------------------------------------
- OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT: Set to "true" to trace message content

Authentication:
---------------
Uses DefaultAzureCredential which supports multiple authentication methods.

Usage:
------
Run the script and type your questions. Press Ctrl+C to exit.
Type 'new' to start a new conversation.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from project root FIRST (before tracing setup)
# Navigate up from clients/project/ to find .env
project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(project_root / ".env")

# =============================================================================
# TRACING CONTENT RECORDING - Must be set BEFORE importing Azure SDK
# =============================================================================
# Enable content recording for traces (messages, tool calls, responses)
# This setting is required by azure-core-tracing-opentelemetry for Azure SDKs
# See: https://learn.microsoft.com/azure/ai-foundry/how-to/develop/trace-agents-sdk
os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

# Tracing imports for Azure Monitor / Application Insights
from azure.core.settings import settings
settings.tracing_implementation = "opentelemetry"  # Must be set before other tracing imports

from opentelemetry import trace
from azure.monitor.opentelemetry import configure_azure_monitor
from azure.ai.projects.telemetry import AIProjectInstrumentor

# =============================================================================
# INITIALIZATION (Done once at startup for optimal performance)
# =============================================================================

print("Initializing Azure AI Foundry connection...")
print(f"Endpoint: {os.environ['AZURE_AI_FOUNDRY_PROJECT_ENDPOINT']}")

# Initialize the AI Project Client with Azure credentials (one-time setup)
# This connection is reused for all subsequent requests
project_client = AIProjectClient(
    endpoint=os.environ["AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

# =============================================================================
# TRACING SETUP (Azure Monitor / Application Insights)
# =============================================================================
# Enable telemetry to capture: duration, token usage, cost, and message content
# Traces appear in the "Tracing" tab of your Foundry project portal
#
# The Application Insights connection string is automatically retrieved from
# your Foundry project configuration. Make sure Application Insights is enabled
# in your Foundry project settings.
#
# IMPORTANT: Instrumentation must be enabled BEFORE getting the OpenAI client
# =============================================================================

try:
    app_insights_conn_str = project_client.telemetry.get_application_insights_connection_string()
    if app_insights_conn_str:
        configure_azure_monitor(connection_string=app_insights_conn_str)
        # Enable AI Projects instrumentation BEFORE getting OpenAI client
        # This instruments the client to capture full request/response data
        AIProjectInstrumentor().instrument()
        print("Tracing enabled: Azure Application Insights + AI Projects instrumentation")
        print(f"Content capture: {os.environ.get('AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED', 'false')}")
    else:
        print("Tracing: Application Insights not configured in Foundry project")
except Exception as e:
    print(f"Tracing: Could not configure ({e})")

# Get a tracer for creating custom spans
tracer = trace.get_tracer(__name__)

# Get the agent name from environment and cache it
agent_name = os.environ["AZURE_AI_FOUNDRY_AGENT_NAME"]
print(f"Agent: {agent_name}")

# Get the OpenAI-compatible client AFTER instrumentation is enabled
# This ensures all API calls are traced properly
openai_client = project_client.get_openai_client()


def process_response_with_mcp_approval(response):
    """
    Process a response and automatically approve any pending MCP tool calls.
    
    When an agent uses MCP-enabled tools (like knowledge bases or external APIs),
    the response may contain approval requests that must be handled before the
    agent can continue execution.
    
    Args:
        response: The response object from openai_client.responses.create()
    
    Returns:
        The final response after all MCP approvals have been processed.
    
    MCP Approval Items:
        - mcp_approval_request: Sent by agent when it needs to call an MCP tool
        - mcp_approval_response: Sent by client to approve/reject the request
    
    Note:
        This implementation auto-approves all MCP requests. In production,
        you may want to add validation or user confirmation for sensitive operations.
    """
    # Check if there are pending MCP approval requests
    while response.status == "incomplete" or (hasattr(response, 'output') and any(
        item.type == "mcp_approval_request" for item in response.output if hasattr(item, 'type')
    )):
        # Find MCP approval requests in the output
        approval_requests = [
            item for item in response.output 
            if hasattr(item, 'type') and item.type == "mcp_approval_request"
        ]
        
        if not approval_requests:
            break
            
        # Approve all pending MCP requests
        approvals = []
        for req in approval_requests:
            print(f"Approving MCP request: {req.id}")
            approvals.append({
                "type": "mcp_approval_response",
                "approve": True,
                "approval_request_id": req.id
            })
        
        # Continue the response with approvals
        # Note: MCP approval continuations MUST use previous_response_id to link
        # the approval back to the specific response that requested it.
        # These will show as "--" for Conversation ID in traces, which is expected.
        response = openai_client.responses.create(
            extra_body={"agent": {"name": agent_name, "type": "agent_reference"}},
            input=approvals,
            previous_response_id=response.id
        )
    
    return response


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def create_conversation():
    """Create a new conversation and return the conversation object."""
    conversation = openai_client.conversations.create()
    print(f"Created conversation (id: {conversation.id})")
    return conversation


def main():
    """Main interactive loop for chatting with the agent."""
    
    # Create a conversation for multi-turn interactions
    # The conversation ID maintains all context server-side
    conversation = create_conversation()
    
    print("\n" + "=" * 60)
    print("Azure AI Foundry Agent - Interactive Mode")
    print("=" * 60)
    print(f"Connected to agent: {agent_name}")
    print("Type your questions and press Enter to get responses.")
    print("The agent has access to knowledge bases via MCP.")
    print("Type 'new' to start a new conversation.")
    print("Press Ctrl+C to exit.\n")
    
    # Track the last response for chaining follow-up questions (MCP approval chain)
    last_response = None
    
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            # Skip empty inputs
            if not user_input:
                continue
            
            # Handle special commands
            if user_input.lower() == 'new':
                conversation = create_conversation()
                last_response = None
                print("Started new conversation!\n")
                continue
            
            # Send message to the agent
            # - First message: use conversation.id to establish context
            # - Follow-ups: use previous_response_id to maintain MCP approval chain
            # Note: Follow-up traces may show "--" for Conversation ID in the portal,
            # but the conversation context is still maintained server-side.
            # Wrap in a tracer span to capture telemetry (duration, tokens, etc.)
            with tracer.start_as_current_span("agent_chat") as span:
                # Add custom attributes to the span for filtering/searching in traces
                span.set_attribute("conversation.id", conversation.id)
                span.set_attribute("agent.name", agent_name)
                span.set_attribute("user.input_length", len(user_input))
                
                if last_response is None:
                    # First message in the conversation
                    response = openai_client.responses.create(
                        conversation=conversation.id,
                        extra_body={"agent": {"name": agent_name, "type": "agent_reference"}},
                        input=user_input,
                    )
                else:
                    # Follow-up message: use previous_response_id to maintain MCP chain
                    # Note: Cannot include conversation param - API rejects it with previous_response_id
                    # Traces for follow-ups may not appear in portal's main trace list,
                    # but are visible when clicking on the first message's conversation detail
                    response = openai_client.responses.create(
                        previous_response_id=last_response.id,
                        extra_body={"agent": {"name": agent_name, "type": "agent_reference"}},
                        input=user_input,
                    )
                
                # Process any MCP approval requests (agent may need to query knowledge base)
                response = process_response_with_mcp_approval(response)
                
                # Add response info to the span
                span.set_attribute("response.id", response.id)
                if hasattr(response, 'usage') and response.usage:
                    span.set_attribute("usage.input_tokens", response.usage.input_tokens or 0)
                    span.set_attribute("usage.output_tokens", response.usage.output_tokens or 0)
                    span.set_attribute("usage.total_tokens", response.usage.total_tokens or 0)
            
            # Store the response for chaining the next message
            last_response = response
            
            print(f"\nAssistant: {response.output_text}\n")
            
        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            # Force flush traces before exiting
            from opentelemetry.sdk.trace import TracerProvider
            provider = trace.get_tracer_provider()
            if hasattr(provider, 'force_flush'):
                provider.force_flush()
            print("\n\nTraces flushed. Exiting... Goodbye!")
            sys.exit(0)
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()