from flask import Blueprint, jsonify, request, Response, stream_with_context
import docker
import os
import json
import time

ollama_manage_bp = Blueprint('ollama_manage', __name__)
bp = ollama_manage_bp

DOCKER_SOCKET = '/var/run/docker.sock'
OLLAMA_IMAGE = 'ollama/ollama:latest'
CONTAINER_NAME = 'mnemos-ollama'

def get_docker_client():
    try:
        # Use from_env to support DOCKER_HOST env var (useful for Podman)
        # Fallback is usually the socket anyway.
        return docker.from_env()
    except Exception as e:
        print(f"Error connecting to Docker: {e}")
        return None

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
            networks = container.attrs['NetworkSettings']['Networks']
            if 'dev_default' not in networks:
                # Active container on wrong network -> report as stopped so user triggers start (which fixes it)
                return jsonify({'status': 'stopped', 'id': container.short_id, 'message': 'Network mismatch - Restart required'})

            if container.status == 'running':
                return jsonify({'status': 'running', 'id': container.short_id})
            else:
                return jsonify({'status': 'stopped', 'id': container.short_id})
        except docker.errors.NotFound:
            # Check if image exists
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
            # Create dummy progress for UX if real pull is too fast or silent
            yield json.dumps({'status': 'starting', 'progress': 0}) + '\n'
            
            # Pull image
            for line in client.api.pull(OLLAMA_IMAGE, stream=True, decode=True):
                # Docker pull lines usually have 'status', 'progress', 'id'
                # We want to normalize this for the frontend
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
        # Check if running or exists
        try:
            container = client.containers.get(CONTAINER_NAME)
            
            # --- Network Check Fix ---
            # Ensure it is on the correct network (dev_default)
            # If not, we must recreate it, otherwise worker can't reach it.
            networks = container.attrs['NetworkSettings']['Networks']
            if 'dev_default' not in networks:
                print(f"Container '{CONTAINER_NAME}' found but on wrong network(s): {list(networks.keys())}. Recreating on 'dev_default'...")
                container.remove(force=True)
                raise docker.errors.NotFound("Force recreation due to network mismatch")
            # -------------------------

            if container.status == 'running':
                return jsonify({'status': 'running', 'message': 'Already running'})
            
            # Found but stopped: try to start
            try:
                container.start()
                return jsonify({'status': 'started'})
            except docker.errors.APIError as e:
                # If start fails (e.g. network not found 404), remove and recreate
                print(f"Failed to start existing container: {e}. Recreating...")
                container.remove(force=True)
                raise docker.errors.NotFound("Force recreation") # Trigger creation block below

        except docker.errors.NotFound:
            # Create and start
            host_project_path = os.environ.get('HOST_PROJECT_PATH', '.')
            volumes = {
                f"{host_project_path}/ollama_models": {'bind': '/root/.ollama', 'mode': 'rw'}
            }
            
            device_requests = [
                docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])
            ]
            
            # Attempt creation, handling race conditions
            try:
                container = client.containers.run(
                    OLLAMA_IMAGE,
                    name=CONTAINER_NAME,
                    ports={'11434/tcp': 11435},
                    volumes=volumes,
                    device_requests=device_requests,
                    detach=True,
                    environment={
                        'OLLAMA_FLASH_ATTENTION': '0',
                        'OLLAMA_GPU_LAYERS': '-1',
                        'OLLAMA_MAX_LOADED_MODELS': '1'
                    },
                    restart_policy={"Name": "always"},
                    network='dev_default'
                )
                return jsonify({'status': 'started', 'id': container.short_id})
            except docker.errors.APIError as e:
                 # Race condition: someone else created it just now?
                 if e.status_code == 409:
                     # Just try to get it again
                     container = client.containers.get(CONTAINER_NAME)
                     return jsonify({'status': 'started', 'id': container.short_id})
                 raise e

    except Exception as e:
        print(f"Start error: {e}")
        return jsonify({'error': str(e)}), 500
