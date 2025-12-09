"""
Update Agent - Azure AI Foundry Agent Updates
==============================================

This script updates an existing agent in Azure AI Foundry. It can modify
the agent's instructions, model, description, and MCP tool configuration.
The MCP approval setting is driven from the .env file.

Usage:
    # Interactive mode (prompts for values)
    python ops/update-agent.py

    # Non-interactive - update MCP approval setting
    python ops/update-agent.py --non-interactive --update-mcp

    # Non-interactive - update instructions
    python ops/update-agent.py --non-interactive --instructions "New instructions..."

Features:
    - Updates existing agents while preserving configuration
    - Can update MCP require_approval setting from environment
    - Interactive wizard for easy updates
    - Non-interactive mode for CI/CD pipelines
    - Shows current agent configuration before changes

Required Environment Variables:
    - AZURE_AI_FOUNDRY_PROJECT_ENDPOINT: Project endpoint URL
    - AZURE_AI_FOUNDRY_AGENT_NAME: Name of agent to update

Optional Environment Variables:
    - AZURE_AI_MCP_REQUIRE_APPROVAL: "never" | "always" (default: "never")
    - AZURE_AI_FOUNDRY_MODEL_DEPLOYMENT_NAME: Model to use
    - AZURE_AI_SEARCH_KB_MCP_ENDPOINT: Knowledge Base MCP endpoint URL
    - AZURE_AI_SEARCH_KB_CONNECTION_NAME: Project connection name for KB auth
    - AZURE_AI_SEARCH_KB_SERVER_LABEL: Server label for the MCP tool

Prerequisites:
    - Azure CLI authenticated (az login)
    - Contributor role on the AI Foundry project
    - Agent must already exist
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
AGENT_NAME = os.environ.get("AZURE_AI_FOUNDRY_AGENT_NAME")
MODEL_NAME = os.environ.get("AZURE_AI_FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini")

# MCP Configuration (from .env)
MCP_REQUIRE_APPROVAL = os.environ.get("AZURE_AI_MCP_REQUIRE_APPROVAL", "never")
MCP_ENDPOINT = os.environ.get("AZURE_AI_SEARCH_KB_MCP_ENDPOINT")
MCP_CONNECTION_NAME = os.environ.get("AZURE_AI_SEARCH_KB_CONNECTION_NAME")
MCP_SERVER_LABEL = os.environ.get("AZURE_AI_SEARCH_KB_SERVER_LABEL", "knowledge-base")

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
print("Azure AI Foundry - Update Agent")
print("=" * 70)
print(f"Project Endpoint: {PROJECT_ENDPOINT}")
print(f"Default Agent: {AGENT_NAME or '(not set)'}")
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

def list_agents():
    """List all agents in the project."""
    print("Available agents:")
    try:
        agents = list(project_client.agents.list())
        if not agents:
            print("  (none)")
            return []
        for agent in agents:
            print(f"  - {agent.name}")
        print()
        return [a.name for a in agents]
    except Exception as e:
        print(f"  Could not list agents: {e}\n")
        return []


def get_agent_details(agent_name: str):
    """Get the current agent configuration."""
    print(f"Fetching agent: {agent_name}")
    try:
        versions = list(project_client.agents.list_versions(agent_name=agent_name))
        if not versions:
            print(f"  No versions found for agent '{agent_name}'")
            return None
        
        latest = versions[-1]
        version = getattr(latest, 'version', 'N/A')
        print(f"  Found {len(versions)} version(s), latest: {version}")
        
        # Extract definition
        definition = getattr(latest, 'definition', {})
        if isinstance(definition, dict):
            model = definition.get('model', MODEL_NAME)
            instructions = definition.get('instructions', '')
            tools = definition.get('tools', [])
        else:
            model = getattr(definition, 'model', MODEL_NAME)
            instructions = getattr(definition, 'instructions', '')
            tools = getattr(definition, 'tools', [])
        
        return {
            'name': agent_name,
            'version': version,
            'model': model,
            'instructions': instructions,
            'description': getattr(latest, 'description', ''),
            'tools': tools,
            'raw': latest,
        }
    except Exception as e:
        print(f"  Error getting agent: {e}")
        return None


def display_agent_config(agent_info: dict):
    """Display current agent configuration."""
    print("\n" + "-" * 70)
    print("Current Agent Configuration")
    print("-" * 70)
    print(f"  Name: {agent_info['name']}")
    print(f"  Version: {agent_info['version']}")
    print(f"  Model: {agent_info.get('model', 'N/A')}")
    print(f"  Description: {agent_info.get('description', 'N/A')}")
    
    # Display instructions (truncated)
    instructions = agent_info.get('instructions', '')
    if len(instructions) > 150:
        print(f"  Instructions: {instructions[:150]}...")
    else:
        print(f"  Instructions: {instructions}")
    
    # Display tools
    tools = agent_info.get('tools', [])
    if tools:
        print(f"  Tools: {len(tools)}")
        for i, tool in enumerate(tools):
            if hasattr(tool, 'server_label'):
                print(f"    [{i+1}] MCP: {tool.server_label}")
                if hasattr(tool, 'require_approval'):
                    print(f"        require_approval: {tool.require_approval}")
            elif isinstance(tool, dict):
                if 'server_label' in tool:
                    print(f"    [{i+1}] MCP: {tool.get('server_label')}")
                    print(f"        require_approval: {tool.get('require_approval', 'N/A')}")
                else:
                    print(f"    [{i+1}] {tool.get('type', 'unknown')}")
    else:
        print("  Tools: (none)")
    print()


def update_agent(
    agent_info: dict,
    new_instructions: str = None,
    new_description: str = None,
    new_model: str = None,
    update_mcp: bool = False,
    mcp_endpoint: str = None,
    mcp_connection: str = None,
    mcp_server_label: str = None,
):
    """
    Create a new agent version with updated configuration.
    
    Args:
        agent_info: Current agent information
        new_instructions: New instructions (None to keep current)
        new_description: New description (None to keep current)
        new_model: New model (None to keep current)
        update_mcp: Whether to update MCP configuration
        mcp_endpoint: MCP endpoint URL
        mcp_connection: MCP connection name
        mcp_server_label: MCP server label
    
    Returns:
        The updated agent object, or None on failure
    """
    print("\n" + "=" * 70)
    print("Updating Agent")
    print("=" * 70)
    
    # Determine final values
    agent_name = agent_info['name']
    model = new_model or agent_info.get('model', MODEL_NAME)
    instructions = new_instructions or agent_info.get('instructions', '')
    description = new_description or agent_info.get('description', '')
    
    # Build tools list
    tools = []
    
    if update_mcp and mcp_endpoint:
        print(f"\nUpdating MCP Tool Configuration:")
        print(f"  Server Label: {mcp_server_label or MCP_SERVER_LABEL}")
        print(f"  Server URL: {mcp_endpoint}")
        print(f"  require_approval: {MCP_REQUIRE_APPROVAL}")
        if mcp_connection:
            print(f"  project_connection_id: {mcp_connection}")
        
        mcp_tool = MCPTool(
            server_label=mcp_server_label or MCP_SERVER_LABEL,
            server_url=mcp_endpoint,
            require_approval=MCP_REQUIRE_APPROVAL,
            allowed_tools=["knowledge_base_retrieve"],
            project_connection_id=mcp_connection if mcp_connection else None,
        )
        tools.append(mcp_tool)
    elif agent_info.get('tools'):
        # Keep existing tools (but we can't modify them without recreating)
        print("\nNote: Keeping existing tool configuration.")
        print("      Use --update-mcp to update MCP settings.")
    
    print(f"\nNew Agent Configuration:")
    print(f"  Name: {agent_name}")
    print(f"  Model: {model}")
    print(f"  Tools: {len(tools) if tools else 'unchanged'}")
    
    # Create new version
    print("\nCreating new agent version...")
    try:
        agent = project_client.agents.create_version(
            agent_name=agent_name,
            definition=PromptAgentDefinition(
                model=model,
                instructions=instructions,
                tools=tools if tools else None,
            ),
            description=description,
        )
        
        print(f"\n✅ SUCCESS!")
        print(f"   Agent Name: {agent.name}")
        print(f"   New Version: {agent.version}")
        print(f"   Agent ID: {agent.id}")
        
        print(f"\n📋 Next Steps:")
        print(f"   1. Test the agent in Foundry Portal > Agent Builder")
        print(f"   2. If published, click 'Publish Updates' to update the application")
        
        return agent
        
    except Exception as e:
        print(f"\n❌ Error updating agent: {e}")
        return None


# =============================================================================
# INTERACTIVE MODE
# =============================================================================

def run_interactive():
    """Interactive wizard for updating an agent."""
    
    # Step 1: Select agent
    print("Step 1: Select Agent\n")
    available_agents = list_agents()
    
    if not available_agents:
        print("No agents found in project. Use create-agent.py first.")
        return
    
    default_agent = AGENT_NAME if AGENT_NAME in available_agents else available_agents[0]
    agent_name = input(f"Enter agent name [{default_agent}]: ").strip()
    if not agent_name:
        agent_name = default_agent
    
    if agent_name not in available_agents:
        print(f"Agent '{agent_name}' not found.")
        return
    
    # Step 2: Get current configuration
    print("\nStep 2: Fetching Current Configuration\n")
    agent_info = get_agent_details(agent_name)
    
    if not agent_info:
        print(f"Could not get agent '{agent_name}' details.")
        return
    
    display_agent_config(agent_info)
    
    # Step 3: What to update?
    print("-" * 70)
    print("Step 3: Select What to Update")
    print("-" * 70)
    print("\nOptions:")
    print("  [1] Update MCP require_approval setting")
    print("  [2] Update instructions")
    print("  [3] Update description")
    print("  [4] Update all (MCP, instructions, description)")
    print("  [0] Cancel")
    
    choice = input("\nSelect option [1]: ").strip() or "1"
    
    if choice == "0":
        print("Cancelled.")
        return
    
    update_mcp = choice in ("1", "4")
    update_instructions = choice in ("2", "4")
    update_description = choice in ("3", "4")
    
    # Collect updates
    new_instructions = None
    new_description = None
    mcp_endpoint = None
    mcp_connection = None
    mcp_server_label = None
    
    if update_mcp:
        print("\n" + "-" * 70)
        print("MCP Configuration")
        print("-" * 70)
        print(f"Current require_approval setting from .env: {MCP_REQUIRE_APPROVAL}")
        
        # Get MCP endpoint
        default_endpoint = MCP_ENDPOINT or ""
        if default_endpoint:
            mcp_endpoint = input(f"MCP endpoint URL [{default_endpoint}]: ").strip()
            if not mcp_endpoint:
                mcp_endpoint = default_endpoint
        else:
            mcp_endpoint = input("MCP endpoint URL: ").strip()
        
        if not mcp_endpoint:
            print("No endpoint provided. MCP will not be updated.")
            update_mcp = False
        else:
            # Get connection
            default_conn = MCP_CONNECTION_NAME or ""
            if default_conn:
                mcp_connection = input(f"Connection name [{default_conn}]: ").strip()
                if not mcp_connection:
                    mcp_connection = default_conn
            else:
                mcp_connection = input("Connection name (optional): ").strip()
            
            # Get server label
            default_label = MCP_SERVER_LABEL or "knowledge-base"
            mcp_server_label = input(f"Server label [{default_label}]: ").strip()
            if not mcp_server_label:
                mcp_server_label = default_label
    
    if update_instructions:
        print("\n" + "-" * 70)
        print("Instructions Update")
        print("-" * 70)
        print("Current instructions:")
        current = agent_info.get('instructions', '')
        print(f"  {current[:200]}..." if len(current) > 200 else f"  {current}")
        print("\nEnter new instructions (or press Enter to keep current):")
        new_instructions = input().strip()
        if not new_instructions:
            new_instructions = None
    
    if update_description:
        print("\n" + "-" * 70)
        print("Description Update")
        print("-" * 70)
        current_desc = agent_info.get('description', '')
        print(f"Current description: {current_desc}")
        new_description = input("New description (or Enter to keep current): ").strip()
        if not new_description:
            new_description = None
    
    # Step 4: Confirm
    print("\n" + "=" * 70)
    print("Step 4: Review and Update")
    print("=" * 70)
    
    print(f"\nChanges to apply:")
    if update_mcp:
        print(f"  ✓ MCP: {mcp_endpoint}")
        print(f"         require_approval: {MCP_REQUIRE_APPROVAL}")
    if new_instructions:
        print(f"  ✓ Instructions: {new_instructions[:50]}...")
    if new_description:
        print(f"  ✓ Description: {new_description}")
    
    if not (update_mcp or new_instructions or new_description):
        print("  (no changes selected)")
        return
    
    confirm = input("\nApply these changes? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return
    
    # Apply update
    update_agent(
        agent_info=agent_info,
        new_instructions=new_instructions,
        new_description=new_description,
        update_mcp=update_mcp,
        mcp_endpoint=mcp_endpoint,
        mcp_connection=mcp_connection,
        mcp_server_label=mcp_server_label,
    )


# =============================================================================
# NON-INTERACTIVE MODE
# =============================================================================

def run_non_interactive(args):
    """Non-interactive mode for CI/CD pipelines."""
    
    agent_name = args.name or AGENT_NAME
    if not agent_name:
        print("Error: Agent name required. Use --name or set AZURE_AI_FOUNDRY_AGENT_NAME")
        sys.exit(1)
    
    # Get current agent info
    agent_info = get_agent_details(agent_name)
    if not agent_info:
        print(f"Error: Agent '{agent_name}' not found.")
        sys.exit(1)
    
    display_agent_config(agent_info)
    
    # Determine what to update
    new_instructions = args.instructions if args.instructions else None
    new_description = args.description if args.description else None
    
    update_mcp = args.update_mcp or bool(MCP_ENDPOINT)
    
    if not (update_mcp or new_instructions or new_description):
        print("No updates specified. Use --update-mcp, --instructions, or --description")
        sys.exit(1)
    
    # Apply update
    agent = update_agent(
        agent_info=agent_info,
        new_instructions=new_instructions,
        new_description=new_description,
        update_mcp=update_mcp,
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
        description="Update an Azure AI Foundry Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Interactive mode
    python ops/update-agent.py

    # Update MCP require_approval (uses env vars)
    python ops/update-agent.py --non-interactive --update-mcp

    # Update instructions
    python ops/update-agent.py --non-interactive --instructions "New system prompt..."

    # Update specific agent
    python ops/update-agent.py --non-interactive --name my-agent --update-mcp
        """
    )
    parser.add_argument(
        "--non-interactive", "-n",
        action="store_true",
        help="Run in non-interactive mode"
    )
    parser.add_argument(
        "--name",
        help="Agent name (default: AZURE_AI_FOUNDRY_AGENT_NAME env var)"
    )
    parser.add_argument(
        "--update-mcp",
        action="store_true",
        help="Update MCP tool configuration (uses env vars)"
    )
    parser.add_argument(
        "--instructions",
        help="New agent instructions (system prompt)"
    )
    parser.add_argument(
        "--description",
        help="New agent description"
    )
    
    args = parser.parse_args()
    
    if args.non_interactive:
        run_non_interactive(args)
    else:
        run_interactive()


if __name__ == "__main__":
    main()
