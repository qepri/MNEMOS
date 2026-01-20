import docker
import socket
import logging

logger = logging.getLogger(__name__)

def get_docker_client():
    try:
        return docker.from_env()
    except Exception as e:
        logger.error(f"Error connecting to Docker: {e}")
        return None

def get_ollama_container(client=None):
    """
    Dynamically find the Ollama container for this project.
    Uses the current container's 'com.docker.compose.project' label to find siblings.
    """
    if not client:
        client = get_docker_client()
        if not client:
            return None

    try:
        # 1. Try to get current container to find project name
        hostname = socket.gethostname()
        try:
            self_container = client.containers.get(hostname)
            project_name = self_container.labels.get('com.docker.compose.project')
        except docker.errors.NotFound:
            # Fallback if running outside docker or hostname mismatch
            project_name = None
            logger.warning(f"Could not find self-container with hostname {hostname}. Assuming not running in Docker or hostname mismatch.")

        # 2. Search for ollama container
        from config.settings import settings
        service_name = settings.OLLAMA_SERVICE_NAME
        filters = {"label": [f"com.docker.compose.service={service_name}"]}
        if project_name:
            filters["label"].append(f"com.docker.compose.project={project_name}")
        
        containers = client.containers.list(filters=filters)
        
        if containers:
            return containers[0]
            
        # Fallback: Try searching by name vaguely if not found by label (e.g. manual start)
        # This is risky if multiple exist, but better than fail
        all_containers = client.containers.list()
        for c in all_containers:
             if 'ollama' in c.name and 'mnemos' in c.name: # Heuristic fallback
                 return c
                 
        return None

    except Exception as e:
        logger.error(f"Error resolving Ollama container: {e}")
        return None
