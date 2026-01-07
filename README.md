# MNEMOS: Context Daemon
 
MNEMOS es un sistema de indexación semántica con memoria persistente y capacidades agénticas multimodales. Permite procesar documentos PDF, archivos de audio, videos y contenido de YouTube, proporcionando una interfaz conversacional inteligente para consultar información de estos documentos utilizando modelos de lenguaje grandes (LLMs).


## Características Principales

### Experiencia de Usuario Mejorada
- **Citas Persistentes**: Referencias interactivas a fuentes que se mantienen al recargar
- **Gestión de Modelos**: Descarga automática de modelos GGUF y gestión de modelos locales
- **Lanzador Automático**: Script `launcher.py` para configuración "one-click" en Windows

### Procesamiento Multimodal
- **PDFs**: Extracción de texto y segmentación por páginas
- **Audio/Video**: Transcripción automática usando Whisper de OpenAI
- **YouTube**: Descarga y transcripción automática de videos
- **Procesamiento Asíncrono**: Sistema de colas con Celery para procesamiento en segundo plano

### Búsqueda Avanzada
- **Búsqueda Híbrida**: Combina búsqueda vectorial (70%) y búsqueda de texto completo (30%)
- **Embeddings Vectoriales**: Utiliza pgvector con índices HNSW para búsquedas rápidas
- **Búsqueda de Texto Completo**: Implementación con PostgreSQL FTS y configuración en español
- **Chunking Inteligente**: Segmentación semántica de documentos usando LangChain

### Modelos de IA Flexibles
Soporte para múltiples proveedores de LLM:
- **Groq** (Inferencia ultra-rápida LPU)
- **OpenAI** (GPT-4, GPT-3.5, etc.)
- **Anthropic** (Claude Sonnet, Claude Opus)
- **LM Studio** (modelos locales)
- **Ollama** (modelos locales dockerizados)

### Interfaz y APIs
- **Interfaz Web Moderna**: Single Page Application (SPA) construida con **Angular 19**.
- **Diseño Responsivo**: Experiencia de usuario fluida en escritorio y móviles.
- **Micro-interacciones**: Feedback visual inmediato y animaciones suaves.
- **API REST**: Endpoints completos para integración
- **MCP Server**: Servidor Model Context Protocol para integración con Claude Desktop
- **Sistema de Conversaciones**: Gestión de historial de chat con contexto

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Angular SPA)               │
│  - Puerto 5200 (Dev) / 80 (Prod)                        │
│  - Gestión de documentos & Chat                         │
│  - Visualización de fuentes                             │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              Flask Application (API)                    │
│  - Blueprints: documents, chat, conversations           │
│  - Endpoints REST                                       │
└──────┬──────────────────────────────────────┬──────────┘
       │                                      │
┌──────▼──────┐                     ┌────────▼──────────┐
│   Celery    │                     │   RAG Service     │
│   Worker    │                     │  - Búsqueda       │
│             │                     │  - Generación     │
│ - PDF Proc. │                     └─────────┬─────────┘
│ - Transcr.  │                               │
│ - Embedding │                     ┌─────────▼─────────┐
└──────┬──────┘                     │  PostgreSQL +     │
       │                            │  pgvector         │
       └────────────────────────────►                   │
                                    │  - Documentos     │
                                    │  - Chunks         │
                                    │  - Conversaciones │
                                    └───────────────────┘
```

## Modelos de Datos

### Document (Documento)
- **id**: UUID único
- **filename**: Nombre del archivo almacenado
- **original_filename**: Nombre original del archivo
- **file_type**: Tipo (pdf, audio, video, youtube)
- **file_path**: Ruta en el sistema de archivos
- **youtube_url**: URL de YouTube (si aplica)
- **status**: Estado (pending, processing, completed, error)
- **metadata_**: Metadatos JSON (duración, páginas, etc.)

### Chunk (Fragmento)
- **id**: UUID único
- **document_id**: Referencia al documento
- **content**: Texto del fragmento
- **chunk_index**: Orden del fragmento
- **start_time/end_time**: Marcas de tiempo para audio/video
- **page_number**: Número de página para PDFs
- **embedding**: Vector de embeddings (384 dimensiones por defecto)
- **search_vector**: Vector de búsqueda de texto completo (PostgreSQL TSVECTOR)

### Conversation & Message (Conversación y Mensajes)
- Sistema de conversaciones con mensajes de usuario y asistente
- Almacenamiento de fuentes utilizadas en cada respuesta
- Gestión de historial completo

## Servicios Principales

### RAGService ([app/services/rag.py](app/services/rag.py))
Motor principal de RAG que implementa:
- Búsqueda híbrida combinando similitud coseno y ranking de texto completo
- Construcción de contexto con información de fuentes
- Generación de respuestas usando LLMs
- Formato de tiempo para referencias de audio/video

### LLMClient ([app/services/llm_client.py](app/services/llm_client.py))
Cliente unificado para múltiples proveedores de LLM:
- Abstracción de APIs de OpenAI, Anthropic, LM Studio y Ollama
- Manejo consistente de mensajes y respuestas
- Logging detallado para debugging

### EmbedderService ([app/services/embedder.py](app/services/embedder.py))
Generación de embeddings vectoriales:
- Soporte local con sentence-transformers
- Soporte remoto con OpenAI/LM Studio/Ollama
- Procesamiento por lotes con reintentos automáticos
- Cache de modelos para eficiencia

### TranscriptionService ([app/services/transcription.py](app/services/transcription.py))
Transcripción de audio/video usando Whisper:
- Soporte para múltiples modelos (tiny, base, small, medium, large-v3)
- Segmentación con marcas de tiempo
- Soporte CPU y GPU

### ChunkerService ([app/services/chunker.py](app/services/chunker.py))
Segmentación inteligente de texto:
- Utiliza RecursiveCharacterTextSplitter de LangChain
- Configuración de tamaño y solapamiento personalizables
- Respeta límites semánticos (párrafos, líneas, palabras)

### PDFProcessor ([app/services/pdf_processor.py](app/services/pdf_processor.py))
Procesamiento de documentos PDF:
- Extracción de texto usando PyMuPDF
- Mantenimiento de información de páginas
- Filtrado de páginas vacías

### YouTubeService ([app/services/youtube.py](app/services/youtube.py))
Descarga y procesamiento de videos de YouTube:
- Descarga de audio usando yt-dlp
- Conversión a formato WAV
- Extracción de metadatos (título, duración)

## Instalación y Configuración

### Requisitos Previos
- **Sistema Operativo**: Windows 10/11
- **Hardware**:
    - CPU: Compatible con versiones modernas de AVX
    - GPU (Opcional): NVIDIA con soporte CUDA para aceleración
    - RAM: 8GB mínimo (16GB recomendado)
- **Software**:
    - Ninguno pre-instalado (el instalador gestionará Podman/Docker)
    - Opcional: Docker Desktop ya instalado

### Instalación Rápida "One-Click"
Hemos simplificado el proceso al máximo. Simplemente:

1. Ejecuta el archivo `installer.bat` (doble clic).
2. El script detectará si tienes Docker o Podman. **Si no tienes ninguno, instalará Podman automáticamente.**
3. Detectará automáticamente tu tarjeta gráfica y te preguntará si quieres usarla.
4. Listo. La aplicación se iniciará.

El instalador se encarga de todo:
- Descarga e instalación de Podman (si es necesario)
- Configuración de WSL2 (si es necesario)
- Detección de hardware (CPU vs GPU)
- Despliegue de contenedores

### Configuración Manual (Docker Compose)

1. Clonar el repositorio:
```bash
git clone <repository-url>
cd mnemos
```

2. Copiar y configurar variables de entorno:
```bash
cp .env.example .env
```

3. Editar el archivo `.env` con tus configuraciones:

```env
# Proveedor de LLM (openai, anthropic, lm_studio, ollama)
LLM_PROVIDER=lm_studio

# Groq (Inferencia Rápida)
GROQ_API_KEY=tu-clave-api
GROQ_MODEL=llama-3.3-70b-versatile

# OpenAI (si se usa)
OPENAI_API_KEY=tu-clave-api
OPENAI_MODEL=gpt-4o-mini

# Anthropic (si se usa)
ANTHROPIC_API_KEY=tu-clave-api
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# LM Studio / Local
LOCAL_LLM_BASE_URL=http://host.docker.internal:1234/v1
LOCAL_LLM_MODEL: local-model

# Configuración de Embeddings
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIMENSION=1024
EMBEDDING_DEVICE=cuda
EMBEDDING_BATCH_SIZE=0 # Auto

# Configuración de Whisper
WHISPER_MODEL=base
WHISPER_DEVICE=cpu

# Clave secreta (cambiar en producción)
SECRET_KEY=tu-clave-secreta-segura
```

### Despliegue con Docker
 **Opción A: Estándar (Recomendado si tienes GPU NVIDIA)**
```bash
# Construir e iniciar todos los servicios
docker-compose up -d --build
```

**Opción B: CPU / Sin GPU NVIDIA**
Si tu equipo no tiene una tarjeta gráfica NVIDIA compatible con CUDA, usa esta configuración para evitar errores al iniciar:
```bash
# Usar el archivo de configuración adicional para CPU
docker-compose -f docker-compose.yml -f docker-compose.cpu.yml up -d --build
```

### Comandos Comunes
```bash
# Ver logs
docker-compose logs -f app

# Detener servicios
docker-compose down

# Detener y eliminar volúmenes (CUIDADO: elimina datos)
docker-compose down -v
```

### Servicios Docker

El sistema despliega los siguientes contenedores:

- **app** (puerto 5000): Aplicación Flask principal
- **worker**: Worker de Celery para procesamiento en segundo plano
- **db** (puerto 5432): PostgreSQL 16 con extensión pgvector
- **redis** (puerto 6379): Cola de mensajes para Celery
- **ollama** (puerto 11435): Servidor Ollama para LLMs locales (opcional)
- **mcp** (puerto 3000): Servidor MCP para integración con Claude Desktop

## Uso de la Aplicación

### Interfaz Web

Acceder a [http://localhost:5200](http://localhost:5200) (o el puerto configurado).

#### Subir Documentos
1. Ir a la sección "Documents"
2. Elegir archivo PDF, audio, video, o pegar URL de YouTube
3. El documento se procesará automáticamente
4. El estado se actualiza en tiempo real (pending → processing → completed)

#### Realizar Consultas
1. Ir a la sección "Chat"
2. Escribir pregunta en el cuadro de texto
3. Opcionalmente seleccionar documentos específicos
4. El sistema buscará información relevante y generará una respuesta
5. Las fuentes se muestran con referencias a documentos y ubicaciones

#### Gestionar Conversaciones
- Ver historial de conversaciones
- Continuar conversaciones previas
- Eliminar conversaciones

### API REST

#### Subir Documento
```bash
# Subir archivo
curl -X POST http://localhost:5000/api/documents/upload \
  -F "file=@documento.pdf"

# Procesar YouTube
curl -X POST http://localhost:5000/api/documents/upload \
  -F "youtube_url=https://www.youtube.com/watch?v=VIDEO_ID"
```

#### Listar Documentos
```bash
curl http://localhost:5000/api/documents/
```

#### Realizar Consulta
```bash
curl -X POST http://localhost:5000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "question": "¿Cuál es el tema principal del documento?",
    "document_ids": ["uuid-del-documento"],
    "top_k": 5
  }'
```

#### Eliminar Documento
```bash
curl -X DELETE http://localhost:5000/api/documents/{document_id}
```

### Servidor MCP (Model Context Protocol)

El servidor MCP permite integrar el sistema RAG con Claude Desktop.

#### Configurar Claude Desktop

Editar el archivo de configuración de Claude Desktop:

**MacOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "mnemos-daemon": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "rag_app-mcp-1",
        "python",
        "-m",
        "app.mcp_server.server"
      ]
    }
  }
}
```

#### Herramientas Disponibles

1. **search_documents**: Buscar información en documentos
   - `query`: Pregunta a realizar
   - `document_ids`: IDs de documentos específicos (opcional)
   - `top_k`: Número de chunks a usar (default: 5)

2. **list_documents**: Listar todos los documentos disponibles con sus IDs

## Configuración Avanzada

### Ajustar Parámetros de Chunking

Editar [config/settings.py](config/settings.py):

```python
CHUNK_SIZE: int = 512        # Tamaño de fragmento
CHUNK_OVERLAP: int = 50      # Solapamiento entre fragmentos
```

### Cambiar Modelo de Whisper

Opciones disponibles: `tiny`, `base`, `small`, `medium`, `large-v3`

```env
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda  # Usar GPU si está disponible
```

### Optimización de Embeddings

El sistema ajusta automáticamente el tamaño del lote según la VRAM disponible. Configurable en [config/settings.py](config/settings.py):

```python
EMBEDDING_BATCH_SIZE: int = 0  # 0 = auto-detectar
EMBEDDING_USE_FP16: bool = True # Usar precisión media (más rápido)
```

### Configurar Búsqueda Híbrida

Ajustar pesos en [app/services/rag.py](app/services/rag.py:41):

```python
# Cambiar proporción vector/keyword
hybrid_score = (similarity * 0.8) + (rank * 0.2)  # Más peso a vectores
```

### Usar Ollama con GPU

El archivo `docker-compose.yml` ya incluye configuración GPU:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [ gpu ]
```

Asegurarse de tener nvidia-docker instalado.

## Estructura del Proyecto

```
rag_app/
├── app/
│   ├── __init__.py              # Factory de aplicación Flask
│   ├── web.py                   # Rutas web
│   ├── extensions.py            # Inicialización de extensiones
│   ├── api/
│   │   ├── documents.py         # API de documentos
│   │   ├── chat.py              # API de chat
│   │   ├── conversations.py     # API de conversaciones
│   │   └── settings.py          # API de configuración
│   ├── models/
│   │   ├── document.py          # Modelo de documento
│   │   ├── chunk.py             # Modelo de fragmento
│   │   └── conversation.py      # Modelos de conversación
│   ├── services/
│   │   ├── rag.py               # Servicio RAG principal
│   │   ├── llm_client.py        # Cliente LLM
│   │   ├── embedder.py          # Generación de embeddings
│   │   ├── chunker.py           # Segmentación de texto
│   │   ├── pdf_processor.py     # Procesamiento PDF
│   │   ├── transcription.py     # Transcripción de audio
│   │   └── youtube.py           # Descarga de YouTube
│   ├── tasks/
│   │   └── processing.py        # Tareas Celery
│   ├── mcp_server/
│   │   └── server.py            # Servidor MCP
│   └── static/                  # Archivos estáticos API
├── frontend_spa/            # Código fuente Angular
│   ├── src/
│   │   ├── app/             # Componentes y Lógica
│   │   └── assets/          # Imágenes y recursos
│   ├── angular.json
│   └── package.json
├── config/
├── config/
│   └── settings.py              # Configuración centralizada
├── media/                       # Archivos multimedia de ejemplo
├── ollama_models/               # Modelos Ollama
├── docker-compose.yml           # Orquestación Docker
├── Dockerfile                   # Imagen Docker
├── requirements.txt             # Dependencias Python
└── .env.example                 # Plantilla de variables de entorno
```

## Tecnologías Utilizadas

### Backend
- **Flask**: Framework web
- **SQLAlchemy**: ORM para base de datos
- **Celery**: Procesamiento asíncrono de tareas
- **Redis**: Cola de mensajes

### Base de Datos
- **PostgreSQL 16**: Base de datos principal
- **pgvector**: Extensión para búsqueda vectorial
- **HNSW Index**: Índice vectorial de alto rendimiento
- **GIN Index**: Índice para búsqueda de texto completo

### IA y ML
- **OpenAI Whisper**: Transcripción de audio
- **sentence-transformers**: Embeddings locales
- **LangChain**: Segmentación de texto
- **OpenAI / Anthropic**: LLMs en la nube
- **Ollama / LM Studio**: LLMs locales

### Procesamiento
- **PyMuPDF**: Extracción de PDF
- **yt-dlp**: Descarga de YouTube
- **pydub**: Manipulación de audio
- **tiktoken**: Tokenización

### Frontend
- **Angular 19**: Framework SPA moderno y robusto.
- **TailwindCSS**: Diseño utilitario para estilos rápidos y consistentes.
- **RxJS**: Gestión reactiva de datos y eventos.
- **Markdown-to-HTML**: Renderizado seguro de respuestas del chat.

## Troubleshooting

### El worker no procesa documentos

Verificar logs del worker:
```bash
docker-compose logs -f worker
```

Verificar conexión a Redis:
```bash
docker-compose exec worker redis-cli -h redis ping
```

### Errores de embeddings

Si usas proveedor local y el modelo no descarga:
```bash
docker-compose exec worker python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Base de datos no inicializa

Verificar extensión pgvector:
```bash
docker-compose exec db psql -U raguser -d ragdb -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Problemas con Whisper

Si hay errores de memoria con Whisper:
1. Usar modelo más pequeño: `WHISPER_MODEL=tiny` o `base`
2. Aumentar memoria del contenedor en docker-compose.yml

### LM Studio no conecta

Asegurar que LM Studio está:
1. Ejecutándose en el host
2. Escuchando en puerto 1234
3. Con CORS habilitado
4. URL correcta en .env: `http://host.docker.internal:1234/v1`

## Mantenimiento

### Backup de Base de Datos

```bash
docker-compose exec db pg_dump -U raguser ragdb > backup.sql
```

### Restaurar Base de Datos

```bash
cat backup.sql | docker-compose exec -T db psql -U raguser ragdb
```

### Limpiar Archivos Huérfanos

Los archivos se eliminan automáticamente al borrar documentos, pero para limpiar manualmente:

```bash
docker-compose exec app python -c "
from app import create_app
from app.models.document import Document
from app.extensions import db
import os

app = create_app()
with app.app_context():
    docs = Document.query.all()
    doc_files = {d.file_path for d in docs if d.file_path}

    upload_dir = '/app/uploads'
    for f in os.listdir(upload_dir):
        if f not in doc_files:
            print(f'Deleting orphan: {f}')
            os.remove(os.path.join(upload_dir, f))
"
```

### Actualizar Dependencias

```bash
# Reconstruir imágenes
docker-compose build --no-cache

# Reiniciar servicios
docker-compose up -d
```

## Seguridad

### Recomendaciones para Producción

1. **Cambiar SECRET_KEY**: Generar clave segura
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

2. **Configurar HTTPS**: Usar nginx o traefik como reverse proxy

3. **Límites de tamaño**: Ajustar `MAX_CONTENT_LENGTH` según necesidades

4. **Autenticación**: Implementar autenticación de usuarios (no incluida por defecto)

5. **Variables de entorno**: No commitear `.env` al repositorio

6. **Actualizaciones**: Mantener dependencias actualizadas

## Licencia

Este proyecto es de código abierto y está disponible bajo la licencia **GNU Affero General Public License v3.0 (AGPLv3)**. Consulte el archivo `LICENSE` para más detalles.

## Contribuciones

Las contribuciones son bienvenidas. Por favor:
1. Fork del repositorio
2. Crear rama de feature (`git checkout -b feature/AmazingFeature`)
3. Commit de cambios (`git commit -m 'Add AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abrir Pull Request


## Roadmap

Funcionalidades planeadas:
- [x] Soporte para EPUB (Incluyendo metadatos)
- [ ] Soporte para más formatos de documentos (Word, Excel, PowerPoint)
- [ ] Procesamiento de imágenes con modelos multimodales
- [ ] Exportación de conversaciones


---

