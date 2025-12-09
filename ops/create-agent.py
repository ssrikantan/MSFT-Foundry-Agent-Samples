"""
Create Agent - Azure AI Foundry Agent Creation
===============================================

This script creates a new agent (or new version) in Azure AI Foundry with 
optional Knowledge Base MCP tool support. The MCP approval setting is 
driven from the .env file for consistency across environments.

Usage:
    # Interactive mode (prompts for all values)
    python ops/create-agent.py

    # Non-interactive mode (uses defaults from .env)
    python ops/create-agent.py --non-interactive

Features:
    - Creates agents with or without Knowledge Base MCP tools
    - MCP require_approval setting driven from AZURE_AI_MCP_REQUIRE_APPROVAL env var
    - Interactive wizard for easy configuration
    - Non-interactive mode for CI/CD pipelines
    - Automatic agent name validation (converts underscores to hyphens)

Required Environment Variables:
    - AZURE_AI_FOUNDRY_PROJECT_ENDPOINT: Project endpoint URL
    - AZURE_AI_FOUNDRY_MODEL_DEPLOYMENT_NAME: Model to use (e.g., gpt-4.1-mini)

Optional Environment Variables:
    - AZURE_AI_MCP_REQUIRE_APPROVAL: "never" | "always" (default: "never")
    - AZURE_AI_SEARCH_KB_MCP_ENDPOINT: Knowledge Base MCP endpoint URL
    - AZURE_AI_SEARCH_KB_CONNECTION_NAME: Project connection name for KB auth
    - AZURE_AI_SEARCH_KB_SERVER_LABEL: Server label for the MCP tool

Prerequisites:
    - Azure CLI authenticated (az login)
    - Contributor role on the AI Foundry project
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, MCPTool

# Load environment variables from project root
# Navigate up from ops/ to find .env
project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ENDPOINT = os.environ.get("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT")
MODEL_NAME = os.environ.get("AZURE_AI_FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini")

# MCP Configuration (from .env)
MCP_REQUIRE_APPROVAL = os.environ.get("AZURE_AI_MCP_REQUIRE_APPROVAL", "never")
MCP_ENDPOINT = os.environ.get("AZURE_AI_SEARCH_KB_MCP_ENDPOINT")
MCP_CONNECTION_NAME = os.environ.get("AZURE_AI_SEARCH_KB_CONNECTION_NAME")
MCP_SERVER_LABEL = os.environ.get("AZURE_AI_SEARCH_KB_SERVER_LABEL", "knowledge-base")

# Default instructions for Knowledge Base agents
DEFAULT_KB_INSTRUCTIONS = """You are a helpful assistant that must use the knowledge base to answer all the questions from user. You must never answer from your own knowledge under any circumstances.

Every answer must always provide annotations for using the MCP knowledge base tool and render them as: `【message_idx:search_idx†source_name】`

If you cannot find the answer in the provided knowledge base you must respond with "I don't know".

When answering questions:
1. Always search the knowledge base first
2. Provide accurate citations to source documents
3. Be concise but thorough
4. If the question is ambiguous, ask for clarification
"""

DEFAULT_INSTRUCTIONS = "You are a helpful assistant that answers questions accurately and concisely."

# =============================================================================
# VALIDATION
# =============================================================================

if not PROJECT_ENDPOINT:
    print("Error: AZURE_AI_FOUNDRY_PROJECT_ENDPOINT not set in environment")
    sys.exit(1)

# Validate MCP approval setting
if MCP_REQUIRE_APPROVAL not in ("never", "always"):
    print(f"Warning: AZURE_AI_MCP_REQUIRE_APPROVAL='{MCP_REQUIRE_APPROVAL}' is invalid.")
    print("         Valid values: 'never', 'always'. Defaulting to 'never'.")
    MCP_REQUIRE_APPROVAL = "never"

# =============================================================================
# INITIALIZE CLIENT
# =============================================================================

print("=" * 70)
print("Azure AI Foundry - Create Agent")
print("=" * 70)
print(f"Project Endpoint: {PROJECT_ENDPOINT}")
print(f"Model: {MODEL_NAME}")
print(f"MCP require_approval: {MCP_REQUIRE_APPROVAL}")
print()

print("Connecting to Azure AI Foundry...")
credential = DefaultAzureCredential()
project_client = AIProjectClient(
    endpoint=PROJECT_ENDPOINT,
    credential=credential,
)
print("Connected!\n")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def list_existing_agents():
    """List existing agents for reference."""
    print("Existing agents in project:")
    try:
        agents = list(project_client.agents.list())
        if not agents:
            print("  (none)")
        for agent in agents:
            print(f"  - {agent.name}")
        print()
        return [a.name for a in agents]
    except Exception as e:
        print(f"  Could not list agents: {e}\n")
        return []


def list_connections():
    """List project connections to find Knowledge Base MCP endpoints."""
    print("Project connections:")
    try:
        connections = list(project_client.connections.list())
        mcp_connections = []
        
        for conn in connections:
            conn_type = getattr(conn, 'category', getattr(conn, 'type', 'unknown'))
            conn_name = getattr(conn, 'name', 'unknown')
            conn_target = getattr(conn, 'target', 'N/A')
            
            # Check if this is an MCP/RemoteTool connection
            if 'mcp' in str(conn_target).lower() or conn_type == 'RemoteTool':
                mcp_connections.append({
                    'name': conn_name,
                    'target': conn_target
                })
                print(f"  - {conn_name}")
                print(f"    Target: {conn_target}")
        
        if not mcp_connections:
            print("  (no MCP connections found)")
        print()
        return mcp_connections
    except Exception as e:
        print(f"  Could not list connections: {e}\n")
        return []


def validate_agent_name(name: str) -> str:
    """Validate and fix agent name (must use hyphens, not underscores)."""
    if '_' in name:
        fixed_name = name.replace('_', '-')
        print(f"⚠️  Agent name contains underscores. Converting to: {fixed_name}")
        return fixed_name
    return name


def create_agent(
    agent_name: str,
    instructions: str,
    description: str = None,
    with_kb: bool = False,
    mcp_endpoint: str = None,
    mcp_connection: str = None,
    mcp_server_label: str = None,
):
    """
    Create a new agent or agent version.
    
    Args:
        agent_name: Name for the agent
        instructions: Agent system instructions
        description: Agent description
        with_kb: Whether to add Knowledge Base MCP tool
        mcp_endpoint: Knowledge Base MCP endpoint URL
        mcp_connection: Project connection name for KB auth
        mcp_server_label: Server label for the MCP tool
    
    Returns:
        The created agent object, or None on failure
    """
    print("\n" + "=" * 70)
    print("Creating Agent")
    print("=" * 70)
    
    # Validate agent name
    agent_name = validate_agent_name(agent_name)
    
    # Build tools list
    tools = []
    
    if with_kb and mcp_endpoint:
        print(f"\nMCP Tool Configuration:")
        print(f"  Server Label: {mcp_server_label or 'knowledge-base'}")
        print(f"  Server URL: {mcp_endpoint}")
        print(f"  require_approval: {MCP_REQUIRE_APPROVAL}")
        print(f"  allowed_tools: ['knowledge_base_retrieve']")
        if mcp_connection:
            print(f"  project_connection_id: {mcp_connection}")
        
        mcp_tool = MCPTool(
            server_label=mcp_server_label or "knowledge-base",
            server_url=mcp_endpoint,
            require_approval=MCP_REQUIRE_APPROVAL,
            allowed_tools=["knowledge_base_retrieve"],
            project_connection_id=mcp_connection if mcp_connection else None,
        )
        tools.append(mcp_tool)
    
    print(f"\nAgent Configuration:")
    print(f"  Name: {agent_name}")
    print(f"  Model: {MODEL_NAME}")
    print(f"  Tools: {len(tools)} configured")
    print(f"  Description: {description or '(default)'}")
    instr_preview = instructions[:100] + "..." if len(instructions) > 100 else instructions
    print(f"  Instructions: {instr_preview}")
    
    # Create the agent
    print("\nCreating agent...")
    try:
        agent = project_client.agents.create_version(
            agent_name=agent_name,
            definition=PromptAgentDefinition(
                model=MODEL_NAME,
                instructions=instructions,
                tools=tools if tools else None,
            ),
            description=description or f"Agent: {agent_name}",
        )
        
        print(f"\n✅ SUCCESS!")
        print(f"   Agent Name: {agent.name}")
        print(f"   Agent Version: {agent.version}")
        print(f"   Agent ID: {agent.id}")
        
        print(f"\n📋 Next Steps:")
        print(f"   1. Test the agent in Foundry Portal > Agent Builder")
        print(f"   2. Publish the agent to create an Agent Application")
        print(f"   3. Update AZURE_AI_FOUNDRY_AGENT_NAME in .env to '{agent.name}'")
        
        return agent
        
    except Exception as e:
        print(f"\n❌ Error creating agent: {e}")
        print("\nTroubleshooting:")
        print("  - Ensure you have Azure AI Project Manager role")
        print("  - Check that agent name uses hyphens, not underscores")
        print("  - Verify model deployment exists in your project")
        return None


# =============================================================================
# INTERACTIVE MODE
# =============================================================================

def run_interactive():
    """Interactive wizard for creating an agent."""
    
    # Step 1: Show existing resources
    print("Step 1: Checking existing resources\n")
    existing_agents = list_existing_agents()
    mcp_connections = list_connections()
    
    # Step 2: Get agent name
    print("-" * 70)
    print("Step 2: Agent Name")
    print("-" * 70)
    
    default_name = os.environ.get("AZURE_AI_FOUNDRY_AGENT_NAME", "my-agent")
    agent_name = input(f"Enter agent name [{default_name}]: ").strip()
    if not agent_name:
        agent_name = default_name
    
    if agent_name in existing_agents:
        print(f"⚠️  Agent '{agent_name}' exists. A new version will be created.")
    
    # Step 3: Knowledge Base?
    print("\n" + "-" * 70)
    print("Step 3: Knowledge Base (MCP)")
    print("-" * 70)
    
    with_kb = input("Add Knowledge Base MCP tool? (y/n) [n]: ").strip().lower() == 'y'
    
    mcp_endpoint = None
    mcp_connection = None
    mcp_server_label = None
    
    if with_kb:
        # Get MCP endpoint
        print("\nKnowledge Base MCP endpoint format:")
        print("  https://<search>.search.windows.net/knowledgebases/<kb>/mcp?api-version=2025-11-01-Preview")
        
        default_endpoint = MCP_ENDPOINT or ""
        if default_endpoint:
            mcp_endpoint = input(f"MCP endpoint URL [{default_endpoint}]: ").strip()
            if not mcp_endpoint:
                mcp_endpoint = default_endpoint
        else:
            mcp_endpoint = input("MCP endpoint URL: ").strip()
        
        if not mcp_endpoint:
            print("No endpoint provided. Skipping KB configuration.")
            with_kb = False
        else:
            # Get connection name
            default_conn = MCP_CONNECTION_NAME or ""
            if default_conn:
                mcp_connection = input(f"Project connection name [{default_conn}]: ").strip()
                if not mcp_connection:
                    mcp_connection = default_conn
            else:
                mcp_connection = input("Project connection name (optional): ").strip()
            
            # Get server label
            default_label = MCP_SERVER_LABEL or "knowledge-base"
            mcp_server_label = input(f"Server label [{default_label}]: ").strip()
            if not mcp_server_label:
                mcp_server_label = default_label
    
    # Step 4: Instructions
    print("\n" + "-" * 70)
    print("Step 4: Agent Instructions")
    print("-" * 70)
    
    if with_kb:
        print("Default instructions are optimized for Knowledge Base retrieval.")
        default_instructions = DEFAULT_KB_INSTRUCTIONS
    else:
        default_instructions = DEFAULT_INSTRUCTIONS
    
    print("Press Enter to use defaults, or type custom instructions.")
    custom_instructions = input("\nCustom instructions (or Enter for default): ").strip()
    instructions = custom_instructions if custom_instructions else default_instructions
    
    # Step 5: Description
    print("\n" + "-" * 70)
    print("Step 5: Agent Description")
    print("-" * 70)
    
    description = input("Enter description (or Enter for default): ").strip()
    if not description:
        description = f"Agent: {agent_name}" + (" with Knowledge Base" if with_kb else "")
    
    # Step 6: Confirm
    print("\n" + "=" * 70)
    print("Step 6: Review and Create")
    print("=" * 70)
    
    print(f"\nAgent Configuration Summary:")
    print(f"  Name: {agent_name}")
    print(f"  Model: {MODEL_NAME}")
    print(f"  Knowledge Base: {'Yes' if with_kb else 'No'}")
    if with_kb:
        print(f"  MCP Endpoint: {mcp_endpoint}")
        print(f"  MCP Connection: {mcp_connection or '(none)'}")
        print(f"  require_approval: {MCP_REQUIRE_APPROVAL}")
    print(f"  Description: {description}")
    
    confirm = input("\nCreate this agent? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return
    
    # Create the agent
    create_agent(
        agent_name=agent_name,
        instructions=instructions,
        description=description,
        with_kb=with_kb,
        mcp_endpoint=mcp_endpoint,
        mcp_connection=mcp_connection,
        mcp_server_label=mcp_server_label,
    )


# =============================================================================
# NON-INTERACTIVE MODE
# =============================================================================

def run_non_interactive(args):
    """Non-interactive mode for CI/CD pipelines."""
    
    agent_name = args.name or os.environ.get("AZURE_AI_FOUNDRY_AGENT_NAME")
    if not agent_name:
        print("Error: Agent name required. Use --name or set AZURE_AI_FOUNDRY_AGENT_NAME")
        sys.exit(1)
    
    # Determine if using Knowledge Base
    with_kb = args.with_kb or bool(MCP_ENDPOINT)
    
    # Select instructions
    if args.instructions:
        instructions = args.instructions
    elif with_kb:
        instructions = DEFAULT_KB_INSTRUCTIONS
    else:
        instructions = DEFAULT_INSTRUCTIONS
    
    # Create the agent
    agent = create_agent(
        agent_name=agent_name,
        instructions=instructions,
        description=args.description or f"Agent: {agent_name}",
        with_kb=with_kb,
        mcp_endpoint=MCP_ENDPOINT,
        mcp_connection=MCP_CONNECTION_NAME,
        mcp_server_label=MCP_SERVER_LABEL,
    )
    
    if not agent:
        sys.exit(1)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Create an Azure AI Foundry Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Interactive mode
    python ops/create-agent.py

    # Non-interactive with env defaults
    python ops/create-agent.py --non-interactive --name my-agent

    # Non-interactive with Knowledge Base
    python ops/create-agent.py --non-interactive --name my-kb-agent --with-kb
        """
    )
    parser.add_argument(
        "--non-interactive", "-n",
        action="store_true",
        help="Run in non-interactive mode (uses env vars and defaults)"
    )
    parser.add_argument(
        "--name",
        help="Agent name (default: AZURE_AI_FOUNDRY_AGENT_NAME env var)"
    )
    parser.add_argument(
        "--with-kb",
        action="store_true",
        help="Include Knowledge Base MCP tool (uses env vars for config)"
    )
    parser.add_argument(
        "--description",
        help="Agent description"
    )
    parser.add_argument(
        "--instructions",
        help="Agent instructions (system prompt)"
    )
    
    args = parser.parse_args()
    
    if args.non_interactive:
        run_non_interactive(args)
    else:
        run_interactive()


if __name__ == "__main__":
    main()
