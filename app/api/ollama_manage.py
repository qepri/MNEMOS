from flask import Blueprint, jsonify, request, Response, stream_with_context
import docker
import os
import json
import time
import socket
from app.utils.docker_helpers import get_docker_client, get_ollama_container

ollama_manage_bp = Blueprint('ollama_manage', __name__)
bp = ollama_manage_bp

OLLAMA_IMAGE = 'ollama/ollama:latest'

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
        container = get_ollama_container(client)
        if container:
            try:
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
            except Exception as e:
                # If container is gone or stale
                pass

        # If not found or error accessing it
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

        container = get_ollama_container(client)
        
        if container:
            try:
                networks = container.attrs['NetworkSettings']['Networks']
                
                # Check connectivity
                common_networks = set(app_networks).intersection(set(networks.keys()))
                
                if not common_networks and app_networks:
                    # Recreate on correct network (Optional: could just connect it)
                    # For simplicity, we try to connect it first before recreating? 
                    # Actually recreating is safer to align with Docker Compose if possible, 
                    # but here we are in manual mode likely.
                    pass 

                if container.status == 'running':
                    return jsonify({'status': 'running', 'message': 'Already running'})
                
                container.start()
                return jsonify({'status': 'started'})
            except Exception:
                # If handle is stale, treat as not found/needs creation
                pass

        # Create and start
        # Use docker volume if possible, or bind mount
        volumes = {
                'ollama_models': {'bind': '/root/.ollama', 'mode': 'rw'}
        }
        
        device_requests = [
            docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])
        ]
        
        # Determine a name: Try to mimic docker compose naming or just use a random one
        # To avoid conflict, we SHOULD NOT specify a name if we want true safety, 
        # or specify a name that includes the project if we can detect it.
        # But for 'start' endpoint, we might just let Docker assign a random name 
        # IF we truly don't care, but we want to find it later.
        
           # Better strategy: Get project name from our own labels
        hostname = socket.gethostname()
        from config.settings import settings
        service_name = settings.OLLAMA_SERVICE_NAME
        
        try:
           self_c = client.containers.get(hostname)
           project = self_c.labels.get('com.docker.compose.project', 'mnemos')
           labels = {
               "com.docker.compose.service": service_name,
               "com.docker.compose.project": project
           }
        except:
           # Fallback
           project = "mnemos"
           labels = {"com.docker.compose.service": service_name, "com.docker.compose.project": project}

        try:
            container = client.containers.run(
                OLLAMA_IMAGE,
                # name=CONTAINER_NAME, # OMIT NAME TO AVOID CONFLICT
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
                network=target_network,
                labels=labels # Apply labels so we can find it later!
            )
            return jsonify({'status': 'started', 'id': container.short_id})
        except docker.errors.APIError as e:
                # If we still hit a snag
                raise e

    except Exception as e:
        return jsonify({'error': str(e)}), 500

