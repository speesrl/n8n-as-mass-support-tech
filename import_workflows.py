#!/usr/bin/env python3
"""
Script to import all workflows from the workflows directory into N8N.
Uses the N8N REST API with either API key or username/password authentication.
"""

import json
import logging
import os
import re
import requests
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuration
SCRIPT_DIR = Path(__file__).parent
WORKFLOWS_DIR = SCRIPT_DIR / "volumes" / "workflows"
CONFIG_DIR = SCRIPT_DIR / "volumes" / "config"
API_KEY_FILE = CONFIG_DIR / "n8n_api_key.txt"
SECRET_FILE = SCRIPT_DIR / ".secret"
N8N_URL = os.getenv("N8N_URL", "http://localhost:5678")
N8N_API_ENDPOINT = f"{N8N_URL}/api/v1/workflows"
N8N_REST_ENDPOINT = f"{N8N_URL}/rest/workflows"
N8N_LOGIN_ENDPOINT = f"{N8N_URL}/rest/login"


def load_credentials() -> Tuple[Optional[str], Optional[str]]:
    """
    Load N8N credentials from .secret file.
    
    Returns:
        Tuple of (email, password) or (None, None) if not found
    """
    if not SECRET_FILE.exists():
        return None, None
    
    try:
        with open(SECRET_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse email and password from .secret file
        email_match = re.search(r'N8N_ADMIN_EMAIL=([^\s]+)', content)
        password_match = re.search(r'N8N_ADMIN_PASSWORD=([^\s]+)', content)
        
        email = email_match.group(1) if email_match else None
        password = password_match.group(1) if password_match else None
        
        if email and password:
            logging.info("Credentials loaded from .secret file")
            return email, password
        else:
            logging.warning("Could not parse credentials from .secret file")
            return None, None
    except Exception as e:
        logging.warning(f"Error reading .secret file: {str(e)}")
        return None, None


def load_api_key() -> Optional[str]:
    """
    Load N8N API key from persistent volume file.
    
    Returns:
        API key string or None if not found
    """
    if not API_KEY_FILE.exists():
        return None
    
    try:
        with open(API_KEY_FILE, 'r', encoding='utf-8') as f:
            api_key = f.read().strip()
            if api_key:
                logging.info("API key loaded successfully")
                return api_key
            else:
                return None
    except Exception as e:
        logging.warning(f"Error reading API key file: {str(e)}")
        return None


def login_with_credentials(email: str, password: str) -> Optional[requests.Session]:
    """
    Login to N8N using username/password and return a session with cookies.
    
    Args:
        email: User email
        password: User password
        
    Returns:
        requests.Session object with authentication cookies, or None on failure
    """
    session = requests.Session()
    
    try:
        login_data = {
            "emailOrLdapLoginId": email,
            "password": password
        }
        
        response = session.post(
            N8N_LOGIN_ENDPOINT,
            json=login_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            logging.info(f"Successfully logged in as {email}")
            return session
        else:
            logging.error(f"Login failed: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Error during login: {str(e)}")
        return None


def get_existing_workflows(session: Optional[requests.Session] = None, 
                          api_key: Optional[str] = None) -> Dict[str, Dict]:
    """
    Get list of existing workflows from N8N to avoid duplicates.
    
    Args:
        session: requests.Session with authentication cookies (for username/password auth)
        api_key: N8N API key (for API key auth)
        
    Returns:
        Dictionary mapping workflow names to workflow data
    """
    try:
        headers = {}
        # Use REST endpoint with session, API endpoint with API key
        if session:
            # Use REST endpoint which supports cookie-based auth
            endpoint = N8N_REST_ENDPOINT
            response = session.get(endpoint, headers=headers, timeout=30)
        else:
            # Use API endpoint with API key
            if api_key:
                headers["X-N8N-API-KEY"] = api_key
            endpoint = N8N_API_ENDPOINT
            response = requests.get(endpoint, headers=headers, timeout=30)
        
        if response.status_code == 200:
            workflows_data = response.json()
            # REST endpoint might return data in a different format
            if isinstance(workflows_data, dict):
                # If it's a dict, try to get the workflows array
                workflows = workflows_data.get("data", workflows_data.get("workflows", []))
            elif isinstance(workflows_data, list):
                workflows = workflows_data
            else:
                logging.warning(f"Unexpected response format: {type(workflows_data)}")
                return {}
            
            # Convert list to dict by name for easy lookup
            return {wf.get("name", ""): wf for wf in workflows if isinstance(wf, dict)}
        else:
            logging.warning(f"Could not fetch existing workflows: {response.status_code}")
            return {}
    except Exception as e:
        logging.warning(f"Error fetching existing workflows: {str(e)}")
        return {}


def load_workflow_files() -> List[Path]:
    """
    Load all JSON workflow files from the workflows directory.
    
    Returns:
        List of Path objects for workflow JSON files
    """
    if not WORKFLOWS_DIR.exists():
        logging.error(f"Workflows directory does not exist: {WORKFLOWS_DIR}")
        return []
    
    workflow_files = list(WORKFLOWS_DIR.glob("*.json"))
    
    if not workflow_files:
        logging.warning(f"No JSON files found in {WORKFLOWS_DIR}")
        return []
    
    logging.info(f"Found {len(workflow_files)} workflow file(s)")
    return sorted(workflow_files)


def get_redis_credential_id(session: Optional[requests.Session] = None,
                            api_key: Optional[str] = None) -> Optional[str]:
    """
    Get the ID of the 'Redis Local' credential if it exists.
    
    Args:
        session: requests.Session with authentication cookies (for username/password auth)
        api_key: N8N API key (for API key auth)
    
    Returns:
        Credential ID or None if not found
    """
    try:
        headers = {}
        if api_key and not session:
            headers["X-N8N-API-KEY"] = api_key
        
        if session:
            response = session.get(f"{N8N_URL}/rest/credentials", headers=headers, timeout=10)
        else:
            response = requests.get(f"{N8N_URL}/rest/credentials", headers=headers, timeout=10)
        
        if response.status_code == 200:
            credentials = response.json()
            # REST endpoint might return data in a different format
            if isinstance(credentials, dict):
                creds_list = credentials.get("data", [])
            elif isinstance(credentials, list):
                creds_list = credentials
            else:
                return None
            
            for cred in creds_list:
                if isinstance(cred, dict) and cred.get("name") == "Redis Local":
                    return cred.get("id")
        
        return None
    except Exception as e:
        logging.debug(f"Could not fetch credentials: {str(e)}")
        return None


def assign_redis_credentials(workflow_data: Dict, redis_credential_id: str) -> bool:
    """
    Assign Redis credentials to all Redis nodes in the workflow.
    
    Args:
        workflow_data: Workflow JSON data as dictionary
        redis_credential_id: ID of the Redis credential to assign
    
    Returns:
        True if any nodes were updated, False otherwise
    """
    updated = False
    for node in workflow_data.get("nodes", []):
        node_type = node.get("type", "")
        if node_type in ["n8n-nodes-base.redis", "n8n-nodes-base.redisTrigger"]:
            # Check if credentials are already set
            node_creds = node.get("credentials", {})
            if not node_creds.get("redis"):
                if "credentials" not in node:
                    node["credentials"] = {}
                node["credentials"]["redis"] = {
                    "id": redis_credential_id,
                    "name": "Redis Local"
                }
                updated = True
    return updated


def check_credentials_needed(workflow_data: Dict) -> List[str]:
    """
    Check which nodes in the workflow need credentials to be configured.
    
    Args:
        workflow_data: Workflow JSON data as dictionary
        
    Returns:
        List of node types that need credentials
    """
    nodes_needing_creds = []
    credential_nodes = {
        "n8n-nodes-base.redis": "Redis",
        "n8n-nodes-base.postgres": "PostgreSQL",
        "n8n-nodes-base.mysql": "MySQL",
        "n8n-nodes-base.httpRequest": "HTTP Request (potentially)",
    }
    
    for node in workflow_data.get("nodes", []):
        node_type = node.get("type", "")
        if node_type in credential_nodes:
            # Check if credentials are set
            credentials = node.get("credentials", {})
            if not credentials or not any(credentials.values()):
                nodes_needing_creds.append(credential_nodes[node_type])
    
    return nodes_needing_creds


def import_workflow(workflow_data: Dict, filename: str, 
                   existing_workflows: Dict[str, Dict], 
                   session: Optional[requests.Session] = None,
                   api_key: Optional[str] = None,
                   update_existing: bool = False) -> bool:
    """
    Import a single workflow into N8N.
    
    Args:
        workflow_data: Workflow JSON data as dictionary
        filename: Name of the source file (for logging)
        existing_workflows: Dictionary of existing workflows by name
        session: requests.Session with authentication cookies (for username/password auth)
        api_key: N8N API key (for API key auth)
        update_existing: Whether to update existing workflows (default: False)
        
    Returns:
        True if successful, False otherwise
    """
    workflow_name = workflow_data.get("name", "Unknown")
    
    # Remove read-only fields that cannot be set during import
    # These fields are managed by N8N and will cause import errors if present
    read_only_fields = ["active", "id", "createdAt", "updatedAt", "versionId", "tags"]
    for field in read_only_fields:
        workflow_data.pop(field, None)
    
    # Try to assign Redis credentials automatically if available
    redis_cred_id = get_redis_credential_id(session=session, api_key=api_key)
    if redis_cred_id:
        if assign_redis_credentials(workflow_data, redis_cred_id):
            logging.info(f"  → Assigned 'Redis Local' credentials to Redis nodes")
    
    # Prepare headers
    headers = {"Content-Type": "application/json"}
    # Only use API key if we don't have a session (cookie-based auth)
    if api_key and not session:
        headers["X-N8N-API-KEY"] = api_key
    
    # Check if workflow already exists
    if workflow_name in existing_workflows:
        if not update_existing:
            logging.warning(f"Workflow '{workflow_name}' already exists. Skipping. (Use --update to overwrite)")
            return False
        else:
            # Update existing workflow
            workflow_id = existing_workflows[workflow_name].get("id")
            logging.info(f"Updating existing workflow '{workflow_name}' (ID: {workflow_id})")
            
            # Remove read-only fields before update
            # (already removed above, but ensure id is removed for update)
            workflow_data.pop("id", None)
            
            try:
                if session:
                    # Use REST endpoint which supports cookie-based auth
                    response = session.put(
                        f"{N8N_REST_ENDPOINT}/{workflow_id}",
                        json=workflow_data,
                        headers=headers,
                        timeout=30
                    )
                else:
                    # Use API endpoint with API key
                    response = requests.put(
                        f"{N8N_API_ENDPOINT}/{workflow_id}",
                        json=workflow_data,
                        headers=headers,
                        timeout=30
                    )
                
                if response.status_code in [200, 201]:
                    result = response.json()
                    logging.info(f"✓ Workflow '{workflow_name}' updated successfully (ID: {result.get('id')})")
                    return True
                else:
                    logging.error(f"✗ Error updating workflow '{workflow_name}': {response.status_code} - {response.text}")
                    return False
            except requests.exceptions.RequestException as e:
                logging.error(f"✗ Connection error updating workflow '{workflow_name}': {str(e)}")
                return False
    
    # Import new workflow
    # Read-only fields already removed above, but ensure id is removed
    workflow_data.pop("id", None)
    
    try:
        if session:
            # Use REST endpoint which supports cookie-based auth
            response = session.post(
                N8N_REST_ENDPOINT,
                json=workflow_data,
                headers=headers,
                timeout=30
            )
        else:
            # Use API endpoint with API key
            response = requests.post(
                N8N_API_ENDPOINT,
                json=workflow_data,
                headers=headers,
                timeout=30
            )
        
        if response.status_code in [200, 201]:
            result = response.json()
            workflow_id = result.get("id", "unknown")
            logging.info(f"✓ Workflow '{workflow_name}' imported successfully (ID: {workflow_id})")
            
            # Check if credentials need to be configured
            creds_needed = check_credentials_needed(workflow_data)
            if creds_needed:
                logging.warning(f"⚠ Note: The following credentials need to be configured manually:")
                for cred_type in creds_needed:
                    logging.warning(f"   - {cred_type}")
                logging.warning(f"   Open the workflow in N8N UI and configure credentials for these nodes.")
            
            return True
        else:
            logging.error(f"✗ Error importing workflow '{workflow_name}': {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logging.error(f"✗ Connection error importing workflow '{workflow_name}': {str(e)}")
        return False
    except Exception as e:
        logging.error(f"✗ Unexpected error importing workflow '{workflow_name}': {str(e)}")
        return False


def main():
    """Main function to import all workflows."""
    import argparse
    
    global N8N_API_ENDPOINT, N8N_REST_ENDPOINT, N8N_LOGIN_ENDPOINT, N8N_URL
    
    parser = argparse.ArgumentParser(
        description="Import all workflows from the workflows directory into N8N"
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update existing workflows instead of skipping them"
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help=f"N8N URL (default: {N8N_URL})"
    )
    
    args = parser.parse_args()
    
    # Override N8N URL if provided
    if args.url:
        N8N_URL = args.url
        N8N_API_ENDPOINT = f"{args.url}/api/v1/workflows"
        N8N_REST_ENDPOINT = f"{args.url}/rest/workflows"
        N8N_LOGIN_ENDPOINT = f"{args.url}/rest/login"
        logging.info(f"Using N8N URL: {args.url}")
    
    # Try to authenticate: first with username/password, then with API key as fallback
    session = None
    api_key = None
    
    # Try username/password first
    email, password = load_credentials()
    if email and password:
        logging.info("Using username/password authentication")
        session = login_with_credentials(email, password)
        if not session:
            logging.warning("Failed to login with username/password, trying API key...")
            session = None
        else:
            logging.info("Successfully authenticated with username/password")
    
    # Fall back to API key if username/password failed or not available
    if not session:
        api_key = load_api_key()
        if api_key:
            logging.info("Using API key authentication")
        else:
            logging.error("No authentication method available!")
            logging.error("Please either:")
            logging.error("  1. Ensure .secret file contains N8N_ADMIN_EMAIL and N8N_ADMIN_PASSWORD")
            logging.error("  2. Or generate an API key in N8N Settings > API and save it to volumes/config/n8n_api_key.txt")
            sys.exit(1)
    
    # Check N8N connection
    logging.info(f"Connecting to N8N at {N8N_URL}...")
    try:
        headers = {}
        # Use REST endpoint with session, API endpoint with API key
        if session:
            # Use REST endpoint which supports cookie-based auth
            endpoint = N8N_REST_ENDPOINT
            response = session.get(endpoint, headers=headers, timeout=10)
        else:
            # Use API endpoint with API key
            if api_key:
                headers["X-N8N-API-KEY"] = api_key
            endpoint = N8N_API_ENDPOINT
            response = requests.get(endpoint, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logging.error(f"Cannot connect to N8N: {response.status_code} - {response.text}")
            sys.exit(1)
    except requests.exceptions.RequestException as e:
        logging.error(f"Cannot connect to N8N: {str(e)}")
        logging.error(f"Make sure N8N is running at {N8N_URL}")
        sys.exit(1)
    
    logging.info("Connected to N8N successfully")
    
    # Get existing workflows
    existing_workflows = get_existing_workflows(session=session, api_key=api_key)
    if existing_workflows:
        logging.info(f"Found {len(existing_workflows)} existing workflow(s) in N8N")
    
    # Load workflow files
    workflow_files = load_workflow_files()
    if not workflow_files:
        logging.warning("No workflow files to import")
        sys.exit(0)
    
    # Import each workflow
    logging.info(f"\nStarting import of {len(workflow_files)} workflow(s)...\n")
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for workflow_file in workflow_files:
        logging.info(f"Processing: {workflow_file.name}")
        
        try:
            with open(workflow_file, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f)
            
            if import_workflow(workflow_data, workflow_file.name, 
                             existing_workflows, session=session, 
                             api_key=api_key, update_existing=args.update):
                success_count += 1
            else:
                if workflow_data.get("name") in existing_workflows and not args.update:
                    skip_count += 1
                else:
                    error_count += 1
                    
        except json.JSONDecodeError as e:
            logging.error(f"✗ Invalid JSON in {workflow_file.name}: {str(e)}")
            error_count += 1
        except Exception as e:
            logging.error(f"✗ Error reading {workflow_file.name}: {str(e)}")
            error_count += 1
    
    # Summary
    logging.info(f"\n{'='*60}")
    logging.info(f"Import Summary:")
    logging.info(f"  ✓ Successfully imported: {success_count}")
    logging.info(f"  ⊘ Skipped (already exists): {skip_count}")
    logging.info(f"  ✗ Errors: {error_count}")
    logging.info(f"{'='*60}\n")
    
    # Reminder about credentials
    if success_count > 0:
        logging.info("⚠ IMPORTANT: Configure credentials for imported workflows")
        logging.info("   Some nodes (like Redis, PostgreSQL, etc.) require credentials to be set.")
        logging.info("   Open each workflow in N8N UI and configure the credentials manually.")
        logging.info("   For Redis, use:")
        logging.info("     - Host: redis (NOT n8n-redis! Use the hostname from docker-compose)")
        logging.info("     - Port: 6379 (internal container port, NOT 6389!)")
        logging.info("     - Password: (leave empty if Redis has no password)")
        logging.info("     Note: Port 6389 is only for host access, containers use 6379")
        logging.info("")
    
    if error_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
