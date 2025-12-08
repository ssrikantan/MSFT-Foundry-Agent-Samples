import os
from dotenv import load_dotenv

# Load environment variables before any tracing setup
load_dotenv()

# Setup tracing - Azure Monitor
from azure.core.settings import settings
settings.tracing_implementation = "opentelemetry"

from opentelemetry import trace
from azure.monitor.opentelemetry import configure_azure_monitor
from azure.ai.projects.telemetry import AIProjectInstrumentor

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

project_client = AIProjectClient(
    endpoint=os.environ["AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

# Configure Azure Monitor tracing
app_insights_conn_str = project_client.telemetry.get_application_insights_connection_string()
if app_insights_conn_str:
    configure_azure_monitor(connection_string=app_insights_conn_str)
    print("Azure Monitor tracing enabled")
else:
    print("Warning: Application Insights not configured for this project")

# Enable content tracing for agent operations
AIProjectInstrumentor().instrument()

# Get tracer for creating custom spans
tracer = trace.get_tracer(__name__)

agent_name = os.environ["AZURE_AI_FOUNDRY_AGENT_NAME"]
openai_client = project_client.get_openai_client()


def process_response_with_mcp_approval(response, conversation_id):
    """Process response and handle MCP approval requests if needed."""
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
        
        # Continue the response with approvals (use previous_response_id without conversation)
        response = openai_client.responses.create(
            extra_body={"agent": {"name": agent_name, "type": "agent_reference"}},
            input=approvals,
            previous_response_id=response.id
        )
    
    return response


# Optional Step: Create a conversation to use with the agent
conversation = openai_client.conversations.create()
print(f"Created conversation (id: {conversation.id})")

print(f"Using agent: {agent_name}")

# Wrap everything in a tracer span for proper trace grouping
scenario = os.path.basename(__file__)
with tracer.start_as_current_span(scenario) as span:
    # Add conversation ID as a custom attribute for correlation
    span.set_attribute("conversation.id", conversation.id)
    span.set_attribute("agent.name", agent_name)
    
    # Chat with the agent to answer questions
    response = openai_client.responses.create(
        conversation=conversation.id,  # Optional conversation context for multi-turn
        extra_body={"agent": {"name": agent_name, "type": "agent_reference"}},
        input="what are the insurance policies offered by Contoso?",
    )
    response = process_response_with_mcp_approval(response, conversation.id)
    print(f"Response output: {response.output_text}")

    # Optional Step: Ask a follow-up question in the same conversation
    # Use previous_response_id to maintain the conversation context and approval chain
    response = openai_client.responses.create(
        previous_response_id=response.id,
        extra_body={"agent": {"name": agent_name, "type": "agent_reference"}},
        input="how does this compare with the policies from Bajaj Allianz? Give me a detailed markdown document that explains the differences.",
    )
    response = process_response_with_mcp_approval(response, conversation.id)
    print(f"Response output: {response.output_text}")