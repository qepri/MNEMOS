
<div align="center" style="position: relative; max-width: 700px; margin: 0 auto; border-radius: 16px; overflow: hidden;">
  <img src="frontend_spa/public/mnemosyne-awa-optimized.gif" alt="MNEMOS background" style="width: 100%; display: block;">
  <div align="center" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; background: rgba(0,0,0,0.3);">
    <img src="frontend_spa/public/favicon.svg" alt="MNEMOS icon" style="width: 64px; height: 64px; margin-bottom: 8px;">
    <h1 style="font-family: 'Georgia', 'Times New Roman', serif; font-size: clamp(2rem, 6vw, 4rem); font-weight: 700; color: white; text-shadow: 0 2px 12px rgba(0,0,0,0.6); margin: 0; letter-spacing: 0.05em;">MNEMOS</h1>
    <p style="font-family: sans-serif; font-size: clamp(0.9rem, 2vw, 1.2rem); color: rgba(255,255,255,0.85); margin: 4px 0 0 0; text-shadow: 0 1px 6px rgba(0,0,0,0.5);">Context Daemon</p>
  </div>
</div>

---

## ¿Qué es MNEMOS?

MNEMOS es un sistema **GraphRAG** + **Wiki** que convierte documentos (PDF, audio, video, YouTube, imágenes) en un **hipergrafo de conocimiento** interconectado. Va más allá de la búsqueda de texto tradicional al integrar un **Motor de Razonamiento** y **Extracción de Hipergrafos** para comprender y conectar relaciones complejas entre conceptos, proporcionando una interfaz conversacional inteligente para consultar y analizar profundamente la información utilizando modelos de lenguaje grandes (LLMs).

Funciona **en tu propio equipo** con modelos locales (llama.cpp) o usando APIs externas (OpenAI, Anthropic, Groq) si prefieres más potencia sin consumir recursos locales.

---

## Características Principales

### Experiencia de Usuario
| Qué hace | Cómo lo hace |
|---|---|
| **GraphRAG + Wiki** | Extrae conceptos y relaciones → wiki navegable con artículos, búsqueda semántica y grafo de conocimiento |
| **Chat inteligente** | Conversaciones con contexto de tus documentos, respuestas con citas a fuentes |
| **Citas Persistentes** | Referencias interactivas a fuentes que se mantienen al recargar la página |
| **Memoria persistente** | El sistema recuerda hechos sobre ti entre conversaciones |
| **Gestión de Modelos** | Descarga automática de modelos GGUF y gestión de modelos locales |

### Procesamiento Multimodal
| Qué hace | Cómo lo hace |
|---|---|
| **Documentos multimedia** | PDF, audio, video, YouTube, imágenes — todo se procesa y conecta en el mismo grafo |
| **Imágenes (Visión)** | Análisis inteligente de imágenes con modelos Llama 3.2 Vision y similares |
| **PDFs** | Extracción de texto y segmentación por páginas usando PyMuPDF |
| **Audio/Video** | Transcripción automática usando Whisper (OpenAI) con marcas de tiempo |
| **YouTube** | Descarga y transcripción automática con yt-dlp |
| **Procesamiento asíncrono** | Sistema de colas con Celery — subes documentos y sigues trabajando |

### Búsqueda Avanzada
| Qué hace | Cómo lo hace |
|---|---|
| **Búsqueda híbrida** | Combina búsqueda vectorial (sentido semántico) + texto completo (palabras exactas) con RRF |
| **Embeddings vectoriales** | pgvector con índices HNSW para búsquedas ultrarrápidas incluso con millones de fragmentos |
| **Re-ranking MMR** | Maximum Marginal Relevance para diversificar resultados y evitar redundancia |
| **Chunking inteligente** | Segmentación semántica con LangChain RecursiveCharacterTextSplitter |
| **Extracción profunda (Hypergraph)** | Análisis granular de eventos, definiciones y relaciones semánticas en dos pasadas LLM |
| **Motor de Razonamiento** | Navegación BFS del grafo para descubrir conexiones no obvias entre conceptos de diferentes documentos |

### Modelos de IA Flexibles
- **Local**: llama.cpp (GGUF con aceleración CUDA), LM Studio
- **Cloud**: OpenAI (GPT-4, GPT-4o), Anthropic (Claude Sonnet, Opus), Groq (inferencia ultrarrápida LPU)
- **Conexiones personalizadas**: cualquier proveedor compatible con API OpenAI (vLLM, DeepSeek, etc.)

### Interfaz y APIs
- **Frontend moderno**: Angular 21 SPA con TailwindCSS, diseño responsivo, gráficos de conocimiento en vivo (Cytoscape.js)
- **API REST completa**: Endpoints para documentos, chat, wiki, razonamiento, configuración
- **MCP Server**: Model Context Protocol para integración con Claude Desktop y OpenCode
- **Sistema de conversaciones**: Gestión de historial con contexto persistente

---

## Arquitectura del Sistema

```
┌──────────────────────────────────────────────────────────────┐
│               Frontend (Angular 21 SPA)                      │
│   Chat · Documents · Wiki · GraphViz · Settings              │
└─────────────────────────────┬────────────────────────────────┘
                              │ REST API (:5000)
┌─────────────────────────────▼────────────────────────────────┐
│                   Flask Application (API)                    │
│   Blueprints: documents, chat, settings, collections, wiki   │
└────────┬────────────────────┬────────────────────┬───────────┘
         │                    │                    │
┌────────▼────────┐  ┌────────▼─────────┐  ┌───────▼───────────┐
│  Celery Worker  │  │   Servicios      │  │ Ext. Providers    │
│                 │  │                  │  │                   │
│ - PDF Process   │  │ - Reasoning Eng  │  │ - OpenAI / Groq   │
│ - Summarization │  │ - Hypergraph Ext │  │ - Anthropic       │
│ - Transcribe    │  │ - Summary Svc    │  │ - llama.cpp/LM St.│
│ - Embedder      │  │ - Search (RAG)   │  │ - Tavily/DuckDuck │
└────────┬────────┘  └────────┬─────────┘  └───────┬───────────┘
         │                    │                    │
         │           ┌────────▼─────────┐          │
         └───────────►  PostgreSQL 16   ◄──────────┘
                     │  + pgvector      │
                     │  + HNSW indexes  │
                     │  + Hypergraph    │
                     │  + Memoria       │
                     └──────────────────┘
```

### Servicios Docker

| Contenedor | Tecnología | Puerto | Rol |
|---|---|---|---|
| `frontend` | Nginx + Angular 21 | `:5200` | Sirve la SPA moderna |
| `app` | Flask + Gunicorn | `:5000` | API REST principal |
| `worker` | Celery + Redis | — | Procesamiento asíncrono (documentos, embeddings, hypergraph) |
| `llamacpp` | llama.cpp server | `:8082` | Inferencia local con GPU (CUDA) |
| `db` | PostgreSQL 16 + pgvector | `:5433` | Base de datos + búsqueda vectorial |
| `redis` | Redis 7 | `:6380` | Cola de tareas + caché + sesiones |
| `adminer` | Adminer | `:8080` | Gestión de BD desde el navegador |
| `mcp` | Python MCP | — | Servidor MCP para Claude Desktop / OpenCode |

---

## Modelos de Datos

### Document (Documento)
- `id`: UUID único · `filename`: Archivo almacenado · `original_filename`: Nombre original
- `file_type`: Tipo (pdf, audio, video, youtube, image)
- `status`: Estado (pending → processing → completed → error)
- `youtube_url`: URL de YouTube (si aplica) · `metadata_`: JSON con duración, páginas, etc.

### Chunk (Fragmento)
- `id`: UUID · `document_id`: Referencia al documento
- `content`: Texto del fragmento · `chunk_index`: Orden · `embedding`: Vector (1024d con bge-m3)
- `search_vector`: PostgreSQL TSVECTOR para búsqueda de texto completo
- `start_time/end_time`: Marcas de tiempo para audio/video · `page_number`: Página para PDFs
- `DocumentSection`: Secciones vectorizadas del documento para resúmenes estructurados

### Conversation & Message (Conversación)
- Sistema de conversaciones con mensajes de usuario y asistente
- Almacenamiento de fuentes utilizadas en cada respuesta con metadatos completos
- Gestión de historial con continuidad de contexto

### Knowledge Graph (Grafo de Conocimiento)
- **Concept**: Entidades y definiciones extraídas (ej. "Proteína X", "Algoritmo Y") con embeddings
- **HyperEdge**: Relaciones complejas multi-dirección que conectan conceptos en un contexto específico
- **HyperEdgeMember**: Miembros individuales de cada hyperarista con peso y rol

### Gestión y Preferencias
- **Collection**: Agrupación lógica de documentos (carpetas/temas)
- **UserMemory**: Hechos persistentes sobre el usuario (memoria a largo plazo)
- **SystemPrompt**: Plantillas de instrucciones para el asistente (prompt engineering)
- **UserPreferences**: Configuración centralizada (modelo activo, proveedores de voz/búsqueda, API keys)

---

## Servicios Principales

### RAGService (`app/services/rag.py`)
Motor principal de RAG que implementa:
- Búsqueda híbrida: vector coseno (1024d) + ranking de texto completo → RRF → MMR → expansión por vecinos
- Construcción de contexto con jerarquía documento/sección, historial, memorias y resultados web
- Generación de respuestas con citas a fuentes y timestamps para audio/video
- Token Budget Guard: verifica el contexto contra el límite del modelo y descarta chunks de menor ranking si excede

### LLMClient (`app/services/llm_client.py`)
Cliente unificado para múltiples proveedores:
- Abstracción de APIs de OpenAI, Anthropic, llama.cpp y LM Studio
- Soporte para modelos de visión (imágenes en conversación)
- Manejo consistente de mensajes, respuestas y logging detallado

### EmbedderService (`app/services/embedder.py`)
Generación de embeddings vectoriales:
- Local con sentence-transformers (all-MiniLM-L6-v2, bge-m3, etc.)
- Remoto con OpenAI / LM Studio
- Procesamiento por lotes con auto-batching según VRAM
- Cache LRU de modelos y soporte FP16 para mayor velocidad

### TranscriptionService (`app/services/transcription.py`)
Transcripción de audio/video con Whisper:
- Soporte para modelos tiny, base, small, medium, large-v3
- Segmentación con marcas de tiempo precisas
- Aceleración por GPU (CUDA) cuando está disponible

### ChunkerService (`app/services/chunker.py`)
Segmentación inteligente de texto:
- RecursiveCharacterTextSplitter de LangChain con tamaño y solapamiento configurables
- Merge de fragmentos de transcripción respetando límites de tiempo
- Preservación de límites semánticos (párrafos, oraciones)

### HypergraphExtractor (`app/services/hypergraph_extractor.py`)
Extracción profunda de conocimiento en dos pasadas:
- **Pasada 1 (paralela)**: cada lote de chunks va al LLM con schema JSON → extrae eventos, definiciones, relaciones
- **Pasada 2 (sincrónica)**: deduplica conceptos con fuzzy matching, genera embeddings, crea HyperEdges multi-concepto

### ReasoningEngine (`app/services/reasoning_engine.py`)
Motor de inferencia sobre el grafo:
- BFS traversal desde concepto origen a destino siguiendo HyperEdges
- Filtro por intensersección de documentos y salto semántico opcional por similitud vectorial
- Síntesis de explicación narrativa + generación de datos Cytoscape.js para visualización

### SummaryService (`app/services/summary_service.py`)
Resúmenes estructurados con patrón Map-Reduce:
- **Map (paralelo)**: lotes de 5 chunks → LLM extrae título, resumen y conceptos clave con relevancia
- **Reduce**: fusión de secciones consecutivas, agregación de conceptos (top 20), resumen ejecutivo final

---

## Tecnología Usada

### Backend
| Tecnología | Por qué |
|---|---|
| **Flask** (Python) | Ligero, flexible, fácil de extender |
| **Celery + Redis** | Tareas asíncronas en segundo plano sin bloquear al usuario |
| **SQLAlchemy + Alembic** | ORM maduro con migraciones |
| **llama.cpp** | Ejecuta modelos locales GGUF con aceleración GPU (NVIDIA CUDA) |
| **OpenAI / Anthropic / Groq** | APIs cloud cuando no quieres usar recursos locales |

### Frontend
| Tecnología | Por qué |
|---|---|
| **Angular 21** | Framework moderno, componentes reutilizables, tipado fuerte |
| **TailwindCSS** | Estilos consistentes y rápidos sin CSS custom |
| **RxJS** | Datos reactivos en tiempo real |
| **Cytoscape.js** | Visualización interactiva del grafo de conocimiento |

### Base de Datos
| Tecnología | Por qué |
|---|---|
| **PostgreSQL 16 + pgvector** | Búsqueda vectorial de alto rendimiento + búsqueda de texto completo en una sola BD |
| **Índices HNSW** | Búsquedas vectoriales ultrarrápidas incluso con millones de fragmentos |
| **Índices GIN** | Búsqueda de texto completo con stemming por idioma |

### IA y ML
| Tecnología | Por qué |
|---|---|
| **OpenAI Whisper** | Transcripción de audio/video con múltiples tamaños de modelo |
| **sentence-transformers** | Embeddings locales sin dependencia externa |
| **LangChain** | Segmentación de texto y cadenas de procesamiento |
| **Groq LPU** | Inferencia de LLM ultrarrápida cuando se necesita velocidad |

---

## Recomendaciones de Hardware

| Escenario | CPU | RAM | GPU | Disco |
|---|---|---|---|---|
| **Mínimo** (solo CPU) | 4 núcleos | 8 GB | No necesaria | 10 GB |
| **Recomendado** (local LLM) | 8+ núcleos | 16-32 GB | NVIDIA 8GB+ VRAM | 50 GB SSD |
| **Pro / Heavy** (70B+) | 16+ núcleos | 64 GB | NVIDIA 24GB+ VRAM | 100+ GB NVMe |
| **Cloud LLM** (API) | 4 núcleos | 8 GB | No necesaria | 5 GB |

- Sin GPU: `EMBEDDING_DEVICE=cpu`, `WHISPER_DEVICE=cpu`, sin llama.cpp
- GPU NVIDIA: aceleración CUDA automática en embeddings, whisper e inferencia
- Apple Silicon: soporte MPS para embeddings

---

## Instalación

### Requisitos
- **Windows 10/11**
- **Docker Desktop** instalado y funcionando
- Hardware según la tabla de recomendaciones arriba

### Pasos

1. **Clona el repositorio**
   ```
   git clone https://github.com/qepri/MNEMOS.git
   cd mnemos/dev
   ```

2. **Configura las variables de entorno**
   - Copia `.env.example` a `.env`
   - Edita `.env` según tus preferencias (LLM provider, API keys, etc.)

3. **Ejecuta `start.bat`**
   - Dale doble clic a `start.bat`
   - El script construye las imágenes Docker (si hay cambios) y levanta todos los servicios
   - Se abre automáticamente http://localhost:5200

4. **¡Listo!** La interfaz web está funcionando.

### Notas importantes
- **Primera ejecución**: tarda unos minutos en descargar dependencias y construir imágenes.
- **Modelos GGUF**: coloca tus modelos `.gguf` en la carpeta `models/`. Si hay al menos uno, `start.bat` activa el servidor llama.cpp automáticamente.
- **Sin GPU**: si no tienes NVIDIA CUDA, usa `docker-compose up -d` (el servicio llama.cpp fallará pero el resto funciona) o edita `docker-compose.yml` para deshabilitar `llamacpp`.

---

## Variables de Entorno Clave

| Variable | Valores | Propósito |
|---|---|---|
| `LLM_PROVIDER` | `openai`, `anthropic`, `lm_studio`, `llamacpp`, `custom` | Selecciona el motor de LLM |
| `OPENAI_API_KEY` | `sk-...` | API key de OpenAI |
| `OPENAI_MODEL` | `gpt-4o-mini`, `gpt-4o`, etc. | Modelo de OpenAI |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | API key de Anthropic |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514`, etc. | Modelo de Anthropic |
| `LOCAL_LLM_BASE_URL` | `http://host.docker.internal:1234/v1` | URL del servidor local compatible con OpenAI |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2`, `BAAI/bge-m3` | Modelo de embeddings |
| `EMBEDDING_DIMENSION` | `384`, `1024` | Dimensión del vector, debe coincidir con el modelo |
| `EMBEDDING_DEVICE` | `auto`, `cpu`, `cuda`, `mps` | Dispositivo para generar embeddings |
| `EMBEDDING_BATCH_SIZE` | `0` (auto), `32`, `64`, `128` | Tamaño de lote (0 = auto según VRAM) |
| `EMBEDDING_USE_FP16` | `true`, `false` | Precisión mixta en GPU (2x más rápido) |
| `WHISPER_MODEL` | `base`, `small`, `medium`, `large` | Modelo de transcripción de audio |
| `WHISPER_DEVICE` | `cpu`, `cuda` | Dispositivo para Whisper |
| `LLAMACPP_NUM_CTX` | `16384` (default) | Ventana de contexto para llama.cpp |
| `LLAMACPP_GPU_LAYERS` | `-1` (auto), `0` (CPU), `999` (todas) | Capas del modelo en GPU |
| `SECRET_KEY` | string | Llave secreta para Flask |
| `WEB_SEARCH_PROVIDER` | `duckduckgo`, `tavily`, `brave` | Proveedor de búsqueda web |
| `MEMORY_ENABLED` | `true`, `false` | Activar memoria a largo plazo |

---

## API — Endpoints Principales

| Método | Ruta | Propósito |
|---|---|---|
| `POST` | `/api/documents/upload` | Subir documento (PDF, audio, video, YouTube, imagen) |
| `GET` | `/api/documents` | Listar documentos con estado |
| `GET` | `/api/documents/{id}` | Detalle de un documento |
| `DELETE` | `/api/documents/{id}` | Eliminar documento y sus datos |
| `POST` | `/api/documents/{id}/reprocess` | Reprocesar desde cero |
| `POST` | `/api/chat` | Enviar mensaje con contexto de documentos |
| `GET` | `/api/chat/conversations` | Historial de conversaciones |
| `GET` | `/api/chat/conversations/{id}` | Mensajes de una conversación |
| `GET` | `/api/wiki/article/{name}` | Artículo de wiki para un concepto |
| `GET` | `/api/wiki/search?q=...` | Búsqueda de conceptos (prefix + vector) |
| `POST` | `/api/reasoning/traverse` | Navegación BFS entre conceptos |
| `GET` | `/api/health` | Health check del sistema |

Documentación interactiva completa en [`landing-page/api-docs.html`](../landing-page/api-docs.html).

---

## Uso de la Aplicación

### Subir Documentos
1. Ve a "Documents" → arrastra PDF, audio, video o pega URL de YouTube
2. El documento se procesa automáticamente en segundo plano
3. El estado se actualiza en tiempo real: `pending → processing → completed`

### Chatear con tus Documentos
1. Ve a "Chat" → escribe tu pregunta
2. Opcionalmente selecciona documentos específicos
3. El sistema busca información relevante (híbrido + graph-RAG) y genera una respuesta con citas a fuentes

### Explorar el Wiki
1. Ve a "Wiki" → los conceptos extraídos aparecen como artículos con descripciones y relaciones
2. Búsqueda por prefijo + similitud vectorial
3. Cada concepto muestra sus conexiones y fragmentos de documento fuente

### Visualizar el Grafo
1. Ve a "Graph" → explora conexiones entre conceptos en el visor interactivo Cytoscape.js
2. Navegación BFS entre conceptos para descubrir rutas de conocimiento

---

## Configuración Avanzada

### Ajustar Chunking (en `config/settings.py`)
```python
CHUNK_SIZE: int = 512        # Tamaño de fragmento en caracteres
CHUNK_OVERLAP: int = 50      # Solapamiento entre fragmentos
```

### Cambiar Modelo de Whisper
```env
WHISPER_MODEL=medium         # tiny, base, small, medium, large-v3
WHISPER_DEVICE=cuda          # cpu, cuda
```

### Ponderación de Búsqueda Híbrida (en `app/services/rag.py`)
```python
# Por defecto: 70% vectorial + 30% texto completo
hybrid_score = (similarity * 0.7) + (rank * 0.3)
```

### Búsqueda Web
```env
WEB_SEARCH_PROVIDER=tavily    # duckduckgo, tavily, brave
TAVILY_API_KEY=tvly-...
```
El LLM genera consultas de búsqueda automáticamente y los resultados se integran en el contexto.

### Voz (TTS / STT)
- **TTS**: Browser (gratis), OpenAI (HD), Deepgram
- **STT**: Browser, OpenAI Whisper, Deepgram Nova

### Memoria a Largo Plazo
```env
MEMORY_ENABLED=true
MEMORY_PROVIDER=llamacpp      # o openai
```
El sistema extrae hechos sobre el usuario y los recuerda entre conversaciones.

---

## Servidor MCP (Model Context Protocol)

El servidor MCP permite integrar MNEMOS con Claude Desktop y OpenCode.

### Configurar Claude Desktop

Editar `claude_desktop_config.json`:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "mnemos": {
      "command": "docker",
      "args": ["exec", "-i", "dev-mcp-1", "python", "-m", "app.mcp_server.server"]
    }
  }
}
```

### Herramientas MCP Disponibles
1. **`search_documents`**: buscar información en documentos (query + document_ids + top_k)
2. **`list_documents`**: listar todos los documentos disponibles

---

## Solución de Problemas

| Problema | Causa probable | Solución |
|---|---|---|
| `docker: command not found` | Docker Desktop no instalado | Instalar [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) |
| Puerto en uso | Otro servicio ocupando el puerto | `docker-compose down` y detener otros servicios |
| `llamacpp` no inicia | Modelo GGUF no encontrado | Colocar un `.gguf` en `models/` |
| Worker se reinicia | Error en código Python | `docker-compose logs -f worker` |
| Embedding falla / CUDA out of memory | VRAM insuficiente | Reducir `EMBEDDING_BATCH_SIZE` o usar `EMBEDDING_DEVICE=cpu` |
| Sin respuesta del LLM | LLM no configurado | Verificar `LLM_PROVIDER` y credenciales en `.env` |
| Whisper sin memoria | Modelo muy grande | Usar `WHISPER_MODEL=base` o `tiny` |
| LM Studio no conecta | CORS o URL incorrecta | Verificar `http://host.docker.internal:1234/v1` y CORS habilitado |

---

## Mantenimiento

```bash
# Backup de base de datos
docker-compose exec db pg_dump -U mnemos_user mnemos_db > backup.sql

# Restaurar backup
cat backup.sql | docker-compose exec -T db psql -U mnemos_user mnemos_db

# Reconstruir imágenes desde cero
docker-compose up -d --build

# Ver logs de un servicio específico
docker-compose logs -f app
docker-compose logs -f worker

# Detener todo
docker-compose down

# Detener y eliminar volúmenes (CUIDADO: borra datos)
docker-compose down -v
```

---

## Seguridad

- **Cambiar SECRET_KEY** en producción: `python -c "import secrets; print(secrets.token_hex(32))"`
- No commitees `.env` al repositorio (contiene API keys)
- Implementa HTTPS con nginx o traefik como reverse proxy
- Ajusta `MAX_CONTENT_LENGTH` según el tamaño máximo de subida deseado

---

## Desarrollo

```bash
# Clonar
git clone https://github.com/qepri/MNEMOS.git
cd mnemos/dev

# Entorno virtual
python -m venv venv
.\venv\Scripts\activate     # Windows
# source venv/bin/activate  # Linux/macOS

# Dependencias
pip install -r requirements.txt

# BD local (solo PostgreSQL + Redis)
docker-compose up -d db redis

# Flask en modo desarrollo
flask run --debug
```

- Los cambios en `app/` se reflejan automáticamente por el volumen Docker montado
- Para contribuir: haz fork del repo, crea una rama, envía un Pull Request

---

## Roadmap

- [x] PDF, audio, video, YouTube, imágenes
- [x] GraphRAG + Wiki hypergraph
- [x] Búsqueda híbrida (vector + FTS)
- [x] Resúmenes Map-Reduce
- [x] Extracción de hipergrafo en dos pasadas
- [x] Motor de razonamiento BFS
- [x] MCP Server
- [x] EPUB (incluyendo metadatos)
- [ ] Soporte para Word, Excel, PowerPoint
- [ ] Exportación de conversaciones
- [ ] Autenticación de usuarios
- [ ] Interfaz de administración web

---

## Licencia

**GNU Affero General Public License v3.0 (AGPLv3)** — ver archivo `LICENSE`.

---

<br>
<br>

<div align="center" style="position: relative; max-width: 700px; margin: 0 auto; border-radius: 16px; overflow: hidden;">
  <img src="frontend_spa/public/mnemosyne-awa-optimized.gif" alt="MNEMOS background" style="width: 100%; display: block;">
  <div align="center" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; background: rgba(0,0,0,0.3);">
    <img src="frontend_spa/public/favicon.svg" alt="MNEMOS icon" style="width: 64px; height: 64px; margin-bottom: 8px;">
    <h1 style="font-family: 'Georgia', 'Times New Roman', serif; font-size: clamp(2rem, 6vw, 4rem); font-weight: 700; color: white; text-shadow: 0 2px 12px rgba(0,0,0,0.6); margin: 0; letter-spacing: 0.05em;">MNEMOS</h1>
    <p style="font-family: sans-serif; font-size: clamp(0.9rem, 2vw, 1.2rem); color: rgba(255,255,255,0.85); margin: 4px 0 0 0; text-shadow: 0 1px 6px rgba(0,0,0,0.5);">Context Daemon</p>
  </div>
</div>

---

## What is MNEMOS?

MNEMOS is a **GraphRAG** + **Wiki** system that turns documents (PDF, audio, video, YouTube, images) into an interconnected **knowledge hypergraph**. It goes beyond traditional text search by integrating a **Reasoning Engine** and **Hypergraph Extraction** to understand and connect complex relationships between concepts, providing an intelligent conversational interface to query and deeply analyze information using Large Language Models (LLMs).

It runs **on your own hardware** with local models (llama.cpp) or connects to external APIs (OpenAI, Anthropic, Groq) when you want more power without using local resources.

---

## Key Features

### User Experience
| What | How |
|---|---|
| **GraphRAG + Wiki** | Extracts concepts & relationships → browsable wiki with articles, semantic search, and knowledge graph |
| **Smart Chat** | Conversational AI grounded in your documents, with source citations |
| **Persistent Citations** | Interactive source references that survive page reloads |
| **Persistent Memory** | Remembers facts about you across conversations |
| **Model Management** | Auto-download GGUF models and manage local models |

### Multimodal Processing
| What | How |
|---|---|
| **Multimedia documents** | PDF, audio, video, YouTube, images — all processed and linked in the same graph |
| **Images (Vision)** | Intelligent image analysis with Llama 3.2 Vision and similar models |
| **PDFs** | Text extraction and page segmentation using PyMuPDF |
| **Audio/Video** | Automatic transcription using Whisper (OpenAI) with timestamps |
| **YouTube** | Auto-download and transcription with yt-dlp |
| **Async processing** | Celery task queue — upload documents and keep working |

### Advanced Search
| What | How |
|---|---|
| **Hybrid Search** | Vector search (meaning) + full-text search (keywords) combined with RRF |
| **Vector Embeddings** | pgvector with HNSW indexes for fast similarity search |
| **MMR Re-ranking** | Maximum Marginal Relevance for diverse results |
| **Smart Chunking** | Semantic text segmentation with LangChain RecursiveCharacterTextSplitter |
| **Hypergraph Extraction** | Two-pass LLM analysis of events, definitions, and semantic relationships |
| **Reasoning Engine** | BFS graph traversal to discover non-obvious connections across documents |

### Flexible AI Models
- **Local**: llama.cpp (GGUF with CUDA), LM Studio
- **Cloud**: OpenAI (GPT-4, GPT-4o), Anthropic (Claude), Groq (ultra-fast LPU)
- **Custom endpoints**: Any OpenAI-compatible provider (vLLM, DeepSeek, etc.)

### Interface & APIs
- **Modern frontend**: Angular 21 SPA with TailwindCSS, responsive design, live Cytoscape.js graphs
- **Full REST API**: Endpoints for documents, chat, wiki, reasoning, settings
- **MCP Server**: Model Context Protocol for Claude Desktop and OpenCode integration
- **Conversation system**: History management with persistent context

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│               Frontend (Angular 21 SPA)                      │
│   Chat · Documents · Wiki · GraphViz · Settings              │
└─────────────────────────────┬────────────────────────────────┘
                              │ REST API (:5000)
┌─────────────────────────────▼────────────────────────────────┐
│                   Flask Application (API)                    │
│   Blueprints: documents, chat, settings, collections, wiki   │
└────────┬────────────────────┬────────────────────┬───────────┘
         │                    │                    │
┌────────▼────────┐  ┌────────▼─────────┐  ┌───────▼───────────┐
│  Celery Worker  │  │   Services       │  │ Ext. Providers    │
│                 │  │                  │  │                   │
│ - PDF Process   │  │ - Reasoning Eng  │  │ - OpenAI / Groq   │
│ - Summarization │  │ - Hypergraph Ext │  │ - Anthropic       │
│ - Transcribe    │  │ - Summary Svc    │  │ - llama.cpp/LM St.│
│ - Embedder      │  │ - Search (RAG)   │  │ - Tavily/DuckDuck │
└────────┬────────┘  └────────┬─────────┘  └───────┬───────────┘
         │                    │                    │
         │           ┌────────▼─────────┐          │
         └───────────►  PostgreSQL 16   ◄──────────┘
                     │  + pgvector      │
                     │  + HNSW indexes  │
                     │  + Hypergraph    │
                     │  + Memory        │
                     └──────────────────┘
```

### Docker Services

| Container | Technology | Port | Role |
|---|---|---|---|
| `frontend` | Nginx + Angular 21 | `:5200` | Serves the modern SPA |
| `app` | Flask + Gunicorn | `:5000` | Main REST API |
| `worker` | Celery + Redis | — | Async processing (documents, embeddings, hypergraph) |
| `llamacpp` | llama.cpp server | `:8082` | Local GPU-accelerated inference (CUDA) |
| `db` | PostgreSQL 16 + pgvector | `:5433` | Database + vector search |
| `redis` | Redis 7 | `:6380` | Task queue + cache + sessions |
| `adminer` | Adminer | `:8080` | Web database management |
| `mcp` | Python MCP | — | MCP server for Claude Desktop / OpenCode |

---

## Data Models

### Document
- `id`: UUID · `filename`: Stored file · `original_filename`: Original name
- `file_type`: Type (pdf, audio, video, youtube, image)
- `status`: State (pending → processing → completed → error)
- `youtube_url`: YouTube URL (if applicable) · `metadata_`: JSON (duration, pages, etc.)

### Chunk
- `id`: UUID · `document_id`: Document reference
- `content`: Text content · `chunk_index`: Order · `embedding`: Vector (1024d with bge-m3)
- `search_vector`: PostgreSQL TSVECTOR for full-text search
- `start_time/end_time`: Timestamps for audio/video · `page_number`: Page for PDFs
- `DocumentSection`: Vectorized sections for structured summaries

### Conversation & Message
- Conversation system with user and assistant messages
- Source citations stored per response with full metadata
- History management with context continuity

### Knowledge Graph
- **Concept**: Extracted entities and definitions with embeddings
- **HyperEdge**: Complex multi-way relationships connecting concepts
- **HyperEdgeMember**: Individual members of each hyperedge with weight and role

### Management & Preferences
- **Collection**: Logical document grouping (folders/topics)
- **UserMemory**: Persistent facts about the user (long-term memory)
- **SystemPrompt**: Instruction templates for the assistant
- **UserPreferences**: Central config (active model, voice/search providers, API keys)

---

## Core Services

### RAGService (`app/services/rag.py`)
Main RAG engine implementing:
- Hybrid search: cosine vector (1024d) + full-text ranking → RRF → MMR → neighbor window expansion
- Context building with document/section hierarchy, history, memories, and web results
- Response generation with source citations and timestamps for audio/video
- Token Budget Guard: checks context against model limit, drops lowest-ranked chunks if exceeded

### LLMClient (`app/services/llm_client.py`)
Unified client for multiple providers:
- API abstraction for OpenAI, Anthropic, llama.cpp, LM Studio
- Vision model support (images in conversation)
- Consistent message/response handling with detailed logging

### EmbedderService (`app/services/embedder.py`)
Vector embedding generation:
- Local with sentence-transformers (all-MiniLM-L6-v2, bge-m3, etc.)
- Remote with OpenAI / LM Studio
- Batch processing with auto-batching by VRAM
- LRU model cache and FP16 support for speed

### TranscriptionService (`app/services/transcription.py`)
Audio/video transcription with Whisper:
- Supports tiny, base, small, medium, large-v3 models
- Timestamp-accurate segmentation
- GPU acceleration (CUDA) when available

### ChunkerService (`app/services/chunker.py`)
Smart text segmentation:
- RecursiveCharacterTextSplitter from LangChain with configurable size/overlap
- Transcript merge respecting time boundaries
- Semantic boundary preservation (paragraphs, sentences)

### HypergraphExtractor (`app/services/hypergraph_extractor.py`)
Two-pass deep knowledge extraction:
- **Pass 1 (parallel)**: each chunk batch → LLM with JSON schema → events, definitions, relationships
- **Pass 2 (sync)**: fuzzy dedup, embedding generation, multi-concept HyperEdge creation

### ReasoningEngine (`app/services/reasoning_engine.py`)
Graph inference engine:
- BFS traversal from source to target concept following HyperEdges
- Document intersection filter + optional semantic leap via vector similarity
- Narrative explanation synthesis + Cytoscape.js graph data

### SummaryService (`app/services/summary_service.py`)
Map-Reduce structured summaries:
- **Map (parallel)**: batches of 5 chunks → LLM extracts title, summary, key concepts with relevance
- **Reduce**: merge consecutive sections, aggregate concepts (top 20), final executive summary

---

## Tech Stack

### Backend
| Technology | Why |
|---|---|
| **Flask** (Python) | Lightweight, flexible, easy to extend |
| **Celery + Redis** | Async background tasks — uploads never block the UI |
| **SQLAlchemy + Alembic** | Mature ORM with migrations |
| **llama.cpp** | Runs local GGUF models with GPU acceleration (NVIDIA CUDA) |
| **OpenAI / Anthropic / Groq** | Plug in cloud APIs when you don't want to use local resources |

### Frontend
| Technology | Why |
|---|---|
| **Angular 21** | Modern framework, reusable components, strong typing |
| **TailwindCSS** | Fast, consistent styling without custom CSS |
| **RxJS** | Reactive, real-time data flow |
| **Cytoscape.js** | Interactive knowledge graph visualization |

### Database
| Technology | Why |
|---|---|
| **PostgreSQL 16 + pgvector** | High-performance vector search + full-text search in one DB |
| **HNSW indexes** | Blazing fast vector similarity even with millions of chunks |
| **GIN indexes** | Full-text search with per-language stemming |

### AI & ML
| Technology | Why |
|---|---|
| **OpenAI Whisper** | Audio/video transcription with multiple model sizes |
| **sentence-transformers** | Local embeddings with no external dependency |
| **LangChain** | Text chunking and processing chains |
| **Groq LPU** | Ultra-fast LLM inference when speed matters |

---

## Hardware Recommendations

| Tier | CPU | RAM | GPU | Storage |
|---|---|---|---|---|
| **Minimum** (CPU only) | 4 cores | 8 GB | None | 10 GB |
| **Recommended** (local LLM) | 8+ cores | 16-32 GB | NVIDIA 8GB+ VRAM | 50 GB SSD |
| **Pro / Heavy** (70B+) | 16+ cores | 64 GB | NVIDIA 24GB+ VRAM | 100+ GB NVMe |
| **Cloud LLM** (API only) | 4 cores | 8 GB | None | 5 GB |

- No GPU: set `EMBEDDING_DEVICE=cpu`, `WHISPER_DEVICE=cpu`, skip llama.cpp
- NVIDIA GPU: automatic CUDA acceleration for embeddings, whisper, inference
- Apple Silicon: MPS support for embeddings

---

## Installation

### Requirements
- **Windows 10/11**
- **Docker Desktop** installed and running
- Hardware per the recommendations table above

### Steps

1. **Clone the repo**
   ```
   git clone https://github.com/qepri/MNEMOS.git
   cd mnemos/dev
   ```

2. **Configure environment**
   - Copy `.env.example` to `.env`
   - Edit `.env` with your preferences (LLM provider, API keys, etc.)

3. **Run `start.bat`**
   - Double-click `start.bat`
   - Builds Docker images (if needed) and starts all services
   - Opens http://localhost:5200 automatically

4. **Done!** The web UI is ready.

### Important notes
- **First run**: takes a few minutes to download dependencies and build images.
- **GGUF models**: put your `.gguf` models in `models/`. If at least one is present, `start.bat` auto-enables the llama.cpp server.
- **No GPU**: run `docker-compose up -d` (llamacpp will fail but everything else works), or edit `docker-compose.yml` to disable `llamacpp`.

---

## Key Environment Variables

| Variable | Values | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `openai`, `anthropic`, `lm_studio`, `llamacpp`, `custom` | Selects the LLM engine |
| `OPENAI_API_KEY` | `sk-...` | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini`, `gpt-4o`, etc. | OpenAI model |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Anthropic API key |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514`, etc. | Anthropic model |
| `LOCAL_LLM_BASE_URL` | `http://host.docker.internal:1234/v1` | Local OpenAI-compatible server URL |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2`, `BAAI/bge-m3` | Embedding model |
| `EMBEDDING_DIMENSION` | `384`, `1024` | Vector dimension, must match model |
| `EMBEDDING_DEVICE` | `auto`, `cpu`, `cuda`, `mps` | Device for embeddings |
| `EMBEDDING_BATCH_SIZE` | `0` (auto), `32`, `64`, `128` | Batch size (0 = auto by VRAM) |
| `EMBEDDING_USE_FP16` | `true`, `false` | Mixed precision on GPU (2x faster) |
| `WHISPER_MODEL` | `base`, `small`, `medium`, `large` | Audio transcription model |
| `WHISPER_DEVICE` | `cpu`, `cuda` | Device for Whisper |
| `LLAMACPP_NUM_CTX` | `16384` (default) | Context window for llama.cpp |
| `LLAMACPP_GPU_LAYERS` | `-1` (auto), `0` (CPU), `999` (all) | Model layers offloaded to GPU |
| `SECRET_KEY` | string | Flask secret key |
| `WEB_SEARCH_PROVIDER` | `duckduckgo`, `tavily`, `brave` | Web search provider |
| `MEMORY_ENABLED` | `true`, `false` | Enable long-term memory |

---

## API — Main Endpoints

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/documents/upload` | Upload a document (PDF, audio, video, YouTube, image) |
| `GET` | `/api/documents` | List all documents with status |
| `GET` | `/api/documents/{id}` | Document detail |
| `DELETE` | `/api/documents/{id}` | Delete document and its data |
| `POST` | `/api/documents/{id}/reprocess` | Reprocess from scratch |
| `POST` | `/api/chat` | Send a message grounded in your documents |
| `GET` | `/api/chat/conversations` | Conversation history |
| `GET` | `/api/chat/conversations/{id}` | Messages in a conversation |
| `GET` | `/api/wiki/article/{name}` | Wiki article for a concept |
| `GET` | `/api/wiki/search?q=...` | Concept search (prefix + vector) |
| `POST` | `/api/reasoning/traverse` | BFS traversal between concepts |
| `GET` | `/api/health` | System health check |

Full interactive API docs at [`landing-page/api-docs.html`](../landing-page/api-docs.html).

---

## Usage

### Upload Documents
1. Go to "Documents" → drag & drop PDF, audio, video, or paste a YouTube URL
2. The document processes automatically in the background
3. Status updates in real-time: `pending → processing → completed`

### Chat with Your Documents
1. Go to "Chat" → type your question
2. Optionally select specific documents
3. The system retrieves relevant info (hybrid + graph-RAG) and generates a cited response

### Explore the Wiki
1. Go to "Wiki" → extracted concepts appear as articles with descriptions and relationships
2. Search by prefix + vector similarity
3. Each concept shows its connections and source document chunks

### Visualize the Graph
1. Go to "Graph" → explore concept connections in the interactive Cytoscape.js viewer
2. BFS traversal between concepts to discover knowledge paths

---

## Advanced Configuration

### Chunking (in `config/settings.py`)
```python
CHUNK_SIZE: int = 512        # Chunk size in characters
CHUNK_OVERLAP: int = 50      # Overlap between chunks
```

### Whisper Model
```env
WHISPER_MODEL=medium         # tiny, base, small, medium, large-v3
WHISPER_DEVICE=cuda          # cpu, cuda
```

### Hybrid Search Weights (in `app/services/rag.py`)
```python
# Default: 70% vector + 30% full-text
hybrid_score = (similarity * 0.7) + (rank * 0.3)
```

### Web Search
```env
WEB_SEARCH_PROVIDER=tavily    # duckduckgo, tavily, brave
TAVILY_API_KEY=tvly-...
```
The LLM auto-generates search queries and results are integrated into context.

### Voice (TTS / STT)
- **TTS**: Browser (free), OpenAI (HD), Deepgram
- **STT**: Browser, OpenAI Whisper, Deepgram Nova

### Long-Term Memory
```env
MEMORY_ENABLED=true
MEMORY_PROVIDER=llamacpp      # or openai
```
The system extracts facts about the user and remembers them across conversations.

---

## MCP Server (Model Context Protocol)

The MCP server integrates MNEMOS with Claude Desktop and OpenCode.

### Claude Desktop Setup

Edit `claude_desktop_config.json`:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "mnemos": {
      "command": "docker",
      "args": ["exec", "-i", "dev-mcp-1", "python", "-m", "app.mcp_server.server"]
    }
  }
}
```

### Available MCP Tools
1. **`search_documents`**: search documents (query + document_ids + top_k)
2. **`list_documents`**: list all available documents

---

## Troubleshooting

| Issue | Likely cause | Solution |
|---|---|---|
| `docker: command not found` | Docker Desktop not installed | Install [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) |
| Port already allocated | Another service using the port | `docker-compose down` and stop other services |
| `llamacpp` won't start | GGUF model not found | Place a `.gguf` file in `models/` |
| Worker keeps restarting | Python code error | `docker-compose logs -f worker` |
| Embedding fails / CUDA OOM | Insufficient VRAM | Lower `EMBEDDING_BATCH_SIZE` or use `EMBEDDING_DEVICE=cpu` |
| No LLM response | LLM not configured | Check `LLM_PROVIDER` and credentials in `.env` |
| Whisper out of memory | Model too large | Use `WHISPER_MODEL=base` or `tiny` |
| LM Studio won't connect | CORS or wrong URL | Check `http://host.docker.internal:1234/v1` and CORS enabled |

---

## Maintenance

```bash
# Database backup
docker-compose exec db pg_dump -U mnemos_user mnemos_db > backup.sql

# Restore backup
cat backup.sql | docker-compose exec -T db psql -U mnemos_user mnemos_db

# Rebuild from scratch
docker-compose up -d --build

# View logs for a specific service
docker-compose logs -f app
docker-compose logs -f worker

# Stop everything
docker-compose down

# Stop and delete volumes (WARNING: destroys data)
docker-compose down -v
```

---

## Security

- **Change SECRET_KEY** in production: `python -c "import secrets; print(secrets.token_hex(32))"`
- Never commit `.env` to the repository (contains API keys)
- Use HTTPS with nginx or traefik as a reverse proxy
- Adjust `MAX_CONTENT_LENGTH` for desired max upload size

---

## Development

```bash
# Clone
git clone https://github.com/qepri/MNEMOS.git
cd mnemos/dev

# Virtual environment
python -m venv venv
.\venv\Scripts\activate     # Windows
# source venv/bin/activate  # Linux/macOS

# Dependencies
pip install -r requirements.txt

# Local DB (PostgreSQL + Redis only)
docker-compose up -d db redis

# Flask development mode
flask run --debug
```

- Changes in `app/` auto-reflect via Docker mounted volumes
- To contribute: fork the repo, create a branch, submit a Pull Request

---

## Roadmap

- [x] PDF, audio, video, YouTube, images
- [x] GraphRAG + Wiki hypergraph
- [x] Hybrid search (vector + FTS)
- [x] Map-Reduce summaries
- [x] Two-pass hypergraph extraction
- [x] BFS reasoning engine
- [x] MCP Server
- [x] EPUB (including metadata)
- [ ] Word, Excel, PowerPoint support
- [ ] Conversation export
- [ ] User authentication
- [ ] Web admin interface

---

## License

**GNU Affero General Public License v3.0 (AGPLv3)** — see `LICENSE` file.
