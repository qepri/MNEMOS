from flask import Blueprint, jsonify, request, Response, stream_with_context
import docker
import os
import json
import time
import socket

ollama_manage_bp = Blueprint('ollama_manage', __name__)
bp = ollama_manage_bp

DOCKER_SOCKET = '/var/run/docker.sock'
OLLAMA_IMAGE = 'ollama/ollama:latest'
CONTAINER_NAME = 'mnemos-ollama'

def get_docker_client():
    try:
        return docker.from_env()
    except Exception as e:
        print(f"Error connecting to Docker: {e}")
        return None

def get_app_networks(client):
    """Get the list of networks the current app container is connected to."""
    try:
        hostname = socket.gethostname()
        container = client.containers.get(hostname)
        return list(container.attrs['NetworkSettings']['Networks'].keys())
    except Exception as e:
        print(f"Could not determine app networks: {e}")
        return []

@ollama_manage_bp.route('/status', methods=['GET'])
def get_status():
    client = get_docker_client()
    if not client:
        return jsonify({'status': 'docker_error', 'message': 'Could not connect to Docker daemon'}), 500

    try:
        # Check if container exists and is running
        try:
            container = client.containers.get(CONTAINER_NAME)
            
            # Check network correctness
            # We want to ensure Ollama is on the SAME network as the app
            app_networks = get_app_networks(client)
            container_networks = container.attrs['NetworkSettings']['Networks']
            
            # Intersection of networks
            common_networks = set(app_networks).intersection(set(container_networks.keys()))
            
            if not common_networks and app_networks:
                # Active container on wrong network
                 return jsonify({'status': 'stopped', 'id': container.short_id, 'message': 'Network mismatch - Restart required'})

            if container.status == 'running':
                return jsonify({'status': 'running', 'id': container.short_id})
            else:
                return jsonify({'status': 'stopped', 'id': container.short_id})
        except docker.errors.NotFound:
            try:
                client.images.get(OLLAMA_IMAGE)
                return jsonify({'status': 'installed_but_not_created'})
            except docker.errors.ImageNotFound:
                return jsonify({'status': 'not_installed'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@ollama_manage_bp.route('/install', methods=['POST'])
def install_ollama():
    """Pulls the Ollama image. Streaming response."""
    client = get_docker_client()
    if not client:
        return jsonify({'error': 'Docker connection failed'}), 500

    def generate():
        try:
            yield json.dumps({'status': 'starting', 'progress': 0}) + '\n'
            for line in client.api.pull(OLLAMA_IMAGE, stream=True, decode=True):
                yield json.dumps(line) + '\n'
            yield json.dumps({'status': 'complete'}) + '\n'
        except Exception as e:
            yield json.dumps({'error': str(e)}) + '\n'

    return Response(stream_with_context(generate()), mimetype='application/x-ndjson')

@ollama_manage_bp.route('/start', methods=['POST'])
def start_ollama():
    """Starts the Ollama container. Creates it if missing."""
    client = get_docker_client()
    if not client:
        return jsonify({'error': 'Docker connection failed'}), 500

    try:
        app_networks = get_app_networks(client)
        # Default to the first found network or 'bridge'
        target_network = app_networks[0] if app_networks else 'bridge'

        try:
            container = client.containers.get(CONTAINER_NAME)
            networks = container.attrs['NetworkSettings']['Networks']
            
            # Check connectivity
            common_networks = set(app_networks).intersection(set(networks.keys()))
            
            if not common_networks and app_networks:
                # Recreate on correct network
                try:
                    container.stop()
                    container.remove()
                    raise docker.errors.NotFound("Recreate") # Jump to creation block
                except Exception as e:
                    if not isinstance(e, docker.errors.NotFound):
                        return jsonify({'error': f"Failed to recreate: {e}"}), 500

            if container.status == 'running':
                return jsonify({'status': 'running', 'message': 'Already running'})
            
            container.start()
            return jsonify({'status': 'started'})

        except docker.errors.NotFound:
            # Create and start
            # Use docker volume if possible, or bind mount
            # In docker-compose, we use 'ollama_models' volume usually. 
            # But here we are creating it manually via code?
            # Ideally we match docker-compose.yml structure.
            
            # Getting volume config from environment or defaults
            # Assuming standard layout
            
            volumes = {
                 'ollama_models': {'bind': '/root/.ollama', 'mode': 'rw'}
            }
            
            # Fix: If we wanted to use bind mount from host:
            # host_project_path = os.environ.get('HOST_PROJECT_PATH', '.')
            # volumes = {f"{host_project_path}/ollama_models": ...}
            # But let's stick to the named volume 'ollama_models' if we can, 
            # or rely on the volume created by compose. 
            # Actually, naming it 'ollama_models' in `volumes` dict as a key treats it as a named volume.
            
            device_requests = [
                docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])
            ]
            
            try:
                container = client.containers.run(
                    OLLAMA_IMAGE,
                    name=CONTAINER_NAME,
                    ports={'11434/tcp': 11434}, 
                    volumes=volumes,
                    device_requests=device_requests,
                    detach=True,
                    environment={
                        'OLLAMA_FLASH_ATTENTION': '1',
                        'OLLAMA_KV_CACHE_TYPE': 'q8_0',
                        'OLLAMA_GPU_LAYERS': '-1',
                        'OLLAMA_MAX_LOADED_MODELS': '1',
                        'OLLAMA_KEEP_ALIVE': '5m'
                    },
                    restart_policy={"Name": "always"},
                    network=target_network # Attach to the app's network!
                )
                return jsonify({'status': 'started', 'id': container.short_id})
            except docker.errors.APIError as e:
                 if e.status_code == 409:
                     container = client.containers.get(CONTAINER_NAME)
                     if container.status != 'running':
                         container.start()
                     return jsonify({'status': 'started', 'id': container.short_id})
                 raise e

    except Exception as e:
        return jsonify({'error': str(e)}), 500

