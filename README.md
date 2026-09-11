
<div align="center" style="position: relative; max-width: 700px; margin: 0 auto; border-radius: 16px; overflow: hidden;">
  <img src="frontend_spa/public/mnemosyne-awa-optimized.gif" alt="MNEMOS background" style="width: 100%; display: block;">
  <div align="center" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; background: rgba(0,0,0,0.3);">
    <img src="frontend_spa/public/favicon.svg" alt="MNEMOS icon" style="width: 64px; height: 64px; margin-bottom: 8px;">
    <h1 style="font-family: 'Georgia', 'Times New Roman', serif; font-size: clamp(2rem, 6vw, 4rem); font-weight: 700; color: white; text-shadow: 0 2px 12px rgba(0,0,0,0.6); margin: 0; letter-spacing: 0.05em;">MNEMOS</h1>
    <p style="font-family: sans-serif; font-size: clamp(0.9rem, 2vw, 1.2rem); color: rgba(255,255,255,0.85); margin: 4px 0 0 0; text-shadow: 0 1px 6px rgba(0,0,0,0.5);">Context Daemon</p>
  </div>
</div>

---

<p align="center">
  <b>Your private knowledge hub.</b> Drop in PDFs, notes, audio, video and YouTube links — then ask questions across everything you've saved. Runs entirely on your own machine. Query it straight from your AI agent over MCP.
  <br/><br/>
  <i>Tu centro de conocimiento privado.</i> Reúne PDFs, notas, audio, vídeo y enlaces de YouTube — y pregúntale a toda tu biblioteca a la vez. Funciona 100% en tu equipo. Consúltalo desde tu agente de IA vía MCP.
</p>

<p align="center">
  <a href="#instalación"><img alt="Install: one command" src="https://img.shields.io/badge/install-one%20command-2ea44f?style=for-the-badge"></a>
  <img alt="100% local and self-hosted" src="https://img.shields.io/badge/100%25-local%20%26%20self--hosted-1f6feb?style=for-the-badge">
  <img alt="Works without an LLM" src="https://img.shields.io/badge/works-without%20an%20LLM-e8710a?style=for-the-badge">
  <img alt="MCP: any AI agent" src="https://img.shields.io/badge/MCP-any%20AI%20agent-8A2BE2?style=for-the-badge">
</p>

<p align="center">
  <a href="#what-is-mnemos">English</a> &nbsp;·&nbsp; <a href="#qué-es-mnemos">Español</a> &nbsp;·&nbsp; <a href="#instalación">Instalar / Install</a> &nbsp;·&nbsp; <a href="#mcp-server-model-context-protocol">MCP</a>
</p>

### See it in action

<!--
  ADD SCREENSHOTS HERE. Drop PNGs into docs/screenshots/ (see docs/screenshots/README.md),
  then uncomment the <img> tags below. Aim for real UI shots — they convert far better than
  any feature list. Suggested three: Search results, Chat with citations, the concept Graph.
-->
<!--
<p align="center">
  <img src="docs/screenshots/search.png"  alt="Search results across your library" width="32%">
  <img src="docs/screenshots/chat.png"    alt="Chat with source citations"          width="32%">
  <img src="docs/screenshots/graph.png"   alt="Interactive concept graph"           width="32%">
</p>
-->
> 📸 _Screenshots coming — drop them in `docs/screenshots/` and uncomment the block above. / Capturas en camino: colócalas en `docs/screenshots/`._

---

## ¿Qué es MNEMOS?

**MNEMOS es tu biblioteca de conocimiento personal, auto-alojada.** Sube PDFs, notas, audio, vídeo, imágenes o enlaces de YouTube a un solo lugar y hazle preguntas a todo tu material a la vez — con respuestas citadas a la fuente exacta. Cada persona ejecuta **su propia copia**: tus documentos, la base de datos y las búsquedas **nunca salen de tu equipo**.

Por debajo es un sistema **GraphRAG + Wiki**: no solo busca texto, sino que extrae conceptos y sus relaciones en un **hipergrafo de conocimiento** navegable, con un motor de razonamiento que descubre conexiones entre documentos distintos. Funciona con modelos **locales** (llama.cpp, LM Studio) o **APIs cloud** (OpenAI, Anthropic, Groq) — o **sin ningún LLM** para solo indexar y buscar.

**¿Por qué MNEMOS?**
- 🔒 **Solo tuyo** — instalas tu propia copia; tus datos nunca salen de tu máquina y, una vez instalado, funciona sin conexión.
- 🧩 **Un lugar para todo** — PDFs, notas, audio, vídeo, YouTube e imágenes, todo buscable en conjunto.
- 🤖 **Con o sin modelo** — indexar y buscar no necesitan LLM; añade uno para chat, resúmenes y la wiki de conceptos.
- 🔌 **Pregúntale desde tu agente de IA** — expón tu biblioteca como herramientas MCP para cualquier cliente compatible (Claude Desktop, OpenCode y otros; ver [Servidor MCP](#servidor-mcp-model-context-protocol)).

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
| **Búsqueda sin LLM** | Página **Search** dedicada: escribe y ves los pasajes que coinciden, con botón "View in PDF" que resalta el texto — sin necesidad de modelo de lenguaje |
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
- **MCP Server**: Model Context Protocol — integra MNEMOS con cualquier agente compatible (Claude Desktop, OpenCode, Cursor, etc.)
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
| `frontend` | Nginx + Angular 21 | `:5200` (LAN) | Sirve la SPA moderna — accesible desde móvil, sin autenticación |
| `app` | Flask + Gunicorn | `:5000` (LAN) | API REST principal (no root; usuario `mnemos`) |
| `worker` | Celery + Redis | — | Procesamiento asíncrono (documentos, embeddings, hypergraph); `--pool=solo` por defecto |
| `llamacpp` | llama.cpp server | `:8082` | Inferencia local con GPU (CUDA) |
| `db` | PostgreSQL 16 + pgvector | `127.0.0.1:5433` | Base de datos + búsqueda vectorial |
| `redis` | Redis 7 | `127.0.0.1:6380` | Cola de tareas + caché + sesiones |
| `adminer` | Adminer | `127.0.0.1:8080` (opt-in) | `docker-compose --profile tools up -d adminer` |
| `mcp` | Python MCP | — | Servidor MCP para cualquier agente compatible (Claude Desktop, OpenCode…) |

Solo `frontend` y `app` son accesibles desde la red local a propósito (uso desde móvil); el resto está limitado a `127.0.0.1`. No hay autenticación todavía — no exponer este stack a internet.

El arranque de los contenedores no requiere red: los modelos de Whisper vienen incluidos en la imagen y las migraciones de base de datos se aplican con Alembic (`flask db upgrade`, controlado por `RUN_MIGRATIONS=true`), no con `db.create_all()`.

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

### Un solo comando (recomendado)

Pega esto en PowerShell:

```powershell
irm https://raw.githubusercontent.com/qepri/MNEMOS/main/install.ps1 | iex
```

Comprueba WSL2, instala Podman **solo si no tienes ningún runtime de
contenedores**, descarga la última versión publicada de MNEMOS (no necesitas
git) y la arranca **descargando imágenes ya construidas** — en tu máquina no se
compila nada. Unos minutos en una conexión normal.

> **Privacidad**: el registro de imágenes aloja el *software*, no tus datos —
> la misma relación que tiene una descarga de instalador con la app que
> instala. Tus documentos, la base de datos y las búsquedas nunca salen de tu
> máquina, y una vez instalado MNEMOS funciona sin conexión.
>
> ¿Desarrollas o quieres embeddings por GPU? La compilación desde código sigue
> siendo el camino: clona el repo y usa `start.bat` — sin `MNEMOS_VERSION` en
> tu `.env`, nada de la maquinaria de releases se activa.

No necesitas Docker Desktop. No necesitas GPU. No necesitas modelo de lenguaje
para subir y buscar documentos.

Al terminar, el instalador deja el comando `mnemos` disponible en tu PATH:

```powershell
mnemos           # arrancar (abre http://localhost:5200)
mnemos stop      # parar
mnemos logs      # ver el log de la app
mnemos backup    # copia de seguridad de la base de datos
mnemos update    # actualizar a la última versión publicada
```

Funciona desde cualquier carpeta y en la misma ventana que ya tienes abierta —
no hace falta reiniciar la terminal. Es un único archivo
(`%LOCALAPPDATA%\Microsoft\WindowsApps\mnemos.cmd`); borrarlo quita el comando y
nada más.

### Requisitos
- **Windows 10/11** con WSL2 (el instalador lo comprueba y lo activa si falta)
- **Un runtime de contenedores**: Podman (`winget install RedHat.Podman`) o
  Docker Desktop. Cualquiera de los dos; MNEMOS se comporta igual.
- Hardware según la tabla de recomendaciones arriba

> Si ya tienes Docker Desktop, MNEMOS lo usará. Los volúmenes de Docker y Podman
> son independientes: si cambias de runtime, tu biblioteca indexada no se pierde,
> pero deja de verse hasta que migres la base de datos (ver más abajo).

### Instalación manual

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
- **Sin GPU**: no hace falta hacer nada — `docker compose up -d` ya no arranca `llamacpp`. Ver la sección siguiente.

### Funciona sin ningún LLM

No necesitas modelo de lenguaje para empezar. Ejecuta `start-lite.bat`, sube un PDF y búscalo — sin Ollama, sin GPU, sin clave de API.

| Funciona sin LLM | Necesita un LLM |
|---|---|
| Subida e indexado (PDF, EPUB, audio, vídeo, YouTube) | Chat con citas |
| Búsqueda semántica (pgvector) | Resúmenes de documentos |
| Búsqueda por palabras clave (FTS) | Grafo de conceptos y wiki |
| Fusión RRF, reordenado MMR | |

Los documentos indexados sin LLM quedan como `completed`, nunca como error: sus fragmentos y embeddings están intactos y son buscables. Las funciones que sí lo necesitan muestran una explicación con un botón **"Connect a model"** en lugar de una pantalla vacía; el botón lleva directo a Ajustes → Chat Settings con el formulario de conexión ya abierto, no solo a la página de Ajustes en general.

Si eliges llama.cpp local y todavía no tienes ningún modelo instalado, el mismo panel ofrece un botón **"Install a local model"** que te lleva a Discover Models — donde puedes buscar en Hugging Face y descargar un GGUF — en vez de dejarte solo con un "No models found".

Cuando conectes un proveedor, Ajustes → Chat ofrece generar los resúmenes y conceptos que falten para los documentos ya indexados. No vuelve a extraer ni a recalcular embeddings, y nunca arranca solo.

### Usa tu propio servidor LLM (modo slim)

MNEMOS incluye un contenedor llama.cpp, pero probablemente ya tengas Ollama o LM Studio corriendo. El modo slim omite el servidor incluido: sin segunda descarga de modelo y sin GPU.

**Requisitos**: Docker. Un servidor compatible con OpenAI es opcional — sin él tendrás indexado y búsqueda:
- **Ollama** → `http://localhost:11434/v1`
- **LM Studio** → `http://localhost:1234/v1` (arranca el servidor desde la pestaña Developer)

```bash
git clone https://github.com/qepri/MNEMOS.git
cd mnemos/dev

# Crea .env desde el preset slim
powershell -ExecutionPolicy Bypass -File presets/apply.ps1 -Preset slim

# Arranca todo excepto el servidor LLM incluido
docker compose up -d
```

Abre <http://localhost:5200>.

El preset apunta a Ollama por defecto. Para LM Studio u otro puerto, edita `.env`:

```env
LLM_PROVIDER=lm_studio
LOCAL_LLM_BASE_URL=http://host.docker.internal:1234/v1
```

Usa `host.docker.internal`, no `localhost`: dentro de un contenedor `localhost` es el contenedor mismo.

> `LLM_PROVIDER=lm_studio` funciona con **cualquier** servidor compatible con OpenAI (Ollama, vLLM, llama-server). El nombre es histórico. No uses `custom`: esa ruta requiere una conexión guardada en la base de datos y falla en una instalación nueva.

**Verifica**: `curl http://localhost:5000/api/ready` debe devolver `200` y `"status": "ready"`. En modo slim la respuesta no incluye el campo `llamacpp` — es correcto, no hay servidor incluido que reportar.

**¿Prefieres el servidor incluido?** `docker compose --profile local-llm up -d` (requiere GPU NVIDIA; pon `LLM_PROVIDER=llamacpp` en `.env`).

Notas:
- Los **embeddings corren en CPU** en modo slim, dejando la GPU libre para tu propio servidor.
- **Cambiar de modo es seguro**: el preset slim no toca `EMBEDDING_MODEL` ni `EMBEDDING_DIMENSION`, así que tus documentos y vectores siguen siendo válidos.
- Los presets solo escriben `.env` si no existe. Para migrar una instalación existente, edita esas tres claves a mano.

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
| `POST` | `/api/documents/search` | Búsqueda de pasajes sin LLM (vector + FTS, sin generación) |
| `GET` | `/api/documents/{id}/chunks` | Ventana de fragmentos alrededor de un índice (leer en contexto, EPUB/texto) |
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
| `GET` | `/api/health` | Liveness (db + redis alcanzables) |
| `GET` | `/api/ready` | Readiness (migraciones al día + sonda de llama.cpp) |
| `GET` | `/api/settings/llm-availability` | Estado del LLM (`unconfigured` / `unreachable` / `available`) |

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

MNEMOS expone tu biblioteca como herramientas MCP, así que **cualquier agente compatible con MCP** puede buscarla y consultarla — Claude Desktop, OpenCode, Cursor o tu propio cliente. Todos apuntan al mismo comando de servidor:

```
docker exec -i dev-mcp-1 python -m app.mcp_server.server
```

### Ejemplo: Claude Desktop

Es solo un cliente concreto — cualquier cliente MCP se configura igual, usando el comando de arriba en su propio formato. Para Claude Desktop, edita `claude_desktop_config.json`:
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

Los ~29 tools están organizados por dominio (módulos `tools_*.py`). Los principales:

- **Búsqueda**: `search_documents`, `search_documents_advanced`, `search_passages` (recuperación sin LLM: devuelve pasajes, no una respuesta generada)
- **Documentos**: `list_documents`, `get_document_details`, `get_document_sections`, `get_document_summary`, `get_document_chunks` (leer texto en contexto), `upload_document`, `add_youtube_video`, `delete_document`
- **Grafo / Wiki**: `search_concepts`, `list_concepts`, `get_concept_article`, `traverse_concepts`
- **Colecciones**: `list_collections`, `create_collection`, `get_collection_documents`, `add_document_to_collection`, `remove_document_from_collection`
- **Conversaciones y memoria**: `list_conversations`, `get_conversation`, `search_conversations`, `create_conversation`, `get_user_memories`, `delete_memory`
- **Ajustes**: `get_system_prompts`, `get_active_settings`, `reprocess_document_hypergraph`
- **Reportes**: `generate_pdf_report`

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
| Chat "dormido" con el servidor LLM encendido | Puede ser red del contenedor, no falta de modelo | `docker-compose exec app python -c "import requests;print(requests.get('http://host.docker.internal:11434',timeout=3).status_code)"` — si falla, es red |
| La biblioteca aparece vacía tras cambiar de runtime | Los volúmenes son por runtime | Tus datos siguen en el otro runtime — ver "Cambiar de Docker a Podman" |
| Dice que no hay runtime pero existe `podman-machine-default` en WSL | Instalación antigua sin CLI | `winget install RedHat.Podman`, o `wsl --unregister podman-machine-default` |

---

## Cambiar de Docker a Podman (o al revés)

Los archivos subidos (`./data/uploads`) se conservan solos — son carpetas del
host. Lo único que hay que mover es la base de datos, porque los volúmenes con
nombre pertenecen a cada runtime:

```bat
:: 1. Con Docker todavía activo - vuelca la base de datos
docker-compose exec -T db pg_dump -U mnemos_user mnemos_db > backups\migrate.sql

:: 2. Para el stack y arranca con Podman
docker-compose down
set MNEMOS_RUNTIME=podman
start-lite.bat

:: 3. Restaura dentro de la base de datos de Podman
type backups\migrate.sql | docker-compose exec -T db psql -U mnemos_user mnemos_db
```

Los embeddings viajan dentro del volcado: **no hay que reindexar ni volver a
subir nada**. Deja `MNEMOS_RUNTIME=podman` puesto (o desinstala Docker Desktop)
para que los siguientes arranques no vuelvan al runtime anterior.

## Actualizaciones

**Las actualizaciones son manuales.** MNEMOS no comprueba si hay versiones
nuevas al arrancar, no actualiza en segundo plano y no te avisa. Se queda en la
versión que tengas hasta que pidas cambiarla:

```powershell
mnemos update
```

Qué hace, en este orden:

1. Lee `MNEMOS_VERSION` de tu `.env` y pregunta a GitHub cuál es la última
   release. Si coinciden, no hace nada y termina.
2. Te pide confirmación mostrando de qué versión a cuál.
3. **Hace copia de seguridad de la base de datos** en
   `backups/mnemos_db_<version>_<fecha>.sql` y te dice la ruta. Si la copia
   falla o sale vacía, se detiene sin haber tocado nada.
4. Descarga los archivos de la nueva versión y los **superpone** a los que ya
   tienes. No borra directorios: tu `.env` (con tus API keys y ajustes),
   `uploads/`, `backups/` y `models/` no están en el paquete y quedan intactos.
5. Reescribe únicamente la línea `MNEMOS_VERSION=` de tu `.env`.
6. Descarga las imágenes nuevas y reinicia.

La copia de seguridad va **primero** porque las migraciones de esquema se
aplican solas cuando arranca el contenedor: para cuando la app responde, la
base de datos ya ha cambiado.

**No hay rollback automático**, a propósito: sería el camino menos probado del
programa y solo se ejecutaría cuando algo ya ha ido mal. Si la actualización
falla, el script imprime la ruta del backup y el comando para restaurarlo:

```powershell
cd $env:USERPROFILE\mnemos
docker-compose up -d --wait db
cmd /c 'docker-compose exec -T db psql -U mnemos_user mnemos_db < "backups\<tu-backup>.sql"'
```

Comillas simples fuera, dobles dentro: PowerShell pasa la línea entera a cmd,
que es quien hace la redirección `<`. Si las inviertes, no funciona.

Para hacer una copia cuando quieras, sin actualizar nada:

```powershell
mnemos backup
```

Guarda el volcado en `backups/mnemos_db_<fecha>.sql`, comprueba que no ha
salido vacío y te imprime el comando de restauración. Cubre la base de datos —
documentos, fragmentos, grafo, conversaciones y ajustes. Los archivos subidos
viven en `uploads/` y se copian aparte, con copiar la carpeta.

> Si instalaste clonando el repositorio, tu `.env` no tiene `MNEMOS_VERSION` y
> `mnemos update` te lo dirá en vez de actuar. Ahí la actualización es
> `git pull` y `start.bat`.

Las reglas que siguen estos scripts están escritas en
[`INSTALLER-CONSTITUTION.md`](INSTALLER-CONSTITUTION.md).

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

**MNEMOS is your own self-hosted knowledge library.** Drop PDFs, notes, audio, video, images or YouTube links into one place and ask questions across all of it at once — with answers cited back to the exact source. Everyone runs **their own copy**: your documents, database and searches **never leave your machine**.

Under the hood it's a **GraphRAG + Wiki** system: it doesn't just search text, it extracts concepts and their relationships into a browsable **knowledge hypergraph**, with a reasoning engine that surfaces connections across different documents. It works with **local** models (llama.cpp, LM Studio), **cloud** APIs (OpenAI, Anthropic, Groq), or **no LLM at all** for indexing and search.

**Why MNEMOS?**
- 🔒 **Yours alone** — self-host your own copy; your data never leaves your machine and, once installed, it works offline.
- 🧩 **One place for everything** — PDFs, notes, audio, video, YouTube and images, all searchable together.
- 🤖 **With or without a model** — indexing and search need no LLM; add one for chat, summaries and the concept wiki.
- 🔌 **Ask it from your AI agent** — expose your library as MCP tools for any compatible client (Claude Desktop, OpenCode, and others; see [MCP Server](#mcp-server-model-context-protocol)).

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
| **LLM-free Search** | Dedicated **Search** page: type a query and see the matching passages, with a "View in PDF" button that highlights the text — no language model required |
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
- **MCP Server**: Model Context Protocol — integrate MNEMOS with any compatible agent (Claude Desktop, OpenCode, Cursor, etc.)
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
| `frontend` | Nginx + Angular 21 | `:5200` (LAN) | Serves the SPA — reachable from mobile, no authentication |
| `app` | Flask + Gunicorn | `:5000` (LAN) | Main REST API (non-root, `mnemos` user) |
| `worker` | Celery + Redis | — | Async processing (documents, embeddings, hypergraph); `--pool=solo` by default |
| `llamacpp` | llama.cpp server | `:8082` | Local GPU-accelerated inference (CUDA) |
| `db` | PostgreSQL 16 + pgvector | `127.0.0.1:5433` | Database + vector search |
| `redis` | Redis 7 | `127.0.0.1:6380` | Task queue + cache + sessions |
| `adminer` | Adminer | `127.0.0.1:8080` (opt-in) | `docker-compose --profile tools up -d adminer` |
| `mcp` | Python MCP | — | MCP server for any compatible agent (Claude Desktop, OpenCode…) |

Only `frontend` and `app` are deliberately reachable from the LAN (mobile access); everything else is bound to `127.0.0.1`. There is no authentication yet — do not expose this stack to the internet.

Container start requires no network: the Whisper model ships baked into the image, and schema changes are applied via Alembic (`flask db upgrade`, gated by `RUN_MIGRATIONS=true`), not `db.create_all()`.

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

### One command (recommended)

Paste this into PowerShell:

```powershell
irm https://raw.githubusercontent.com/qepri/MNEMOS/main/install.ps1 | iex
```

It checks WSL2, installs Podman **only if you have no container runtime**,
downloads the latest MNEMOS release (no git required), and starts it by
**pulling prebuilt images** — nothing compiles on your machine. A few minutes
on a normal connection.

> **Privacy**: the image registry hosts the *software*, not your data — the
> same relationship an installer download has to the app it installs. Your
> documents, database and searches never leave your machine, and MNEMOS runs
> offline once installed.
>
> Developing, or want GPU embeddings? Building from source remains the path:
> clone the repo and use `start.bat` — without `MNEMOS_VERSION` in your
> `.env`, none of the release machinery activates.

No Docker Desktop required. No GPU required. No language model required to
upload and search documents.

When it finishes, the installer leaves a `mnemos` command on your PATH:

```powershell
mnemos           # start (opens http://localhost:5200)
mnemos stop      # stop
mnemos logs      # tail the app log
mnemos backup    # back up the database
mnemos update    # move to the latest published release
```

It works from any folder and in the window you already have open — no terminal
restart needed. It is a single file
(`%LOCALAPPDATA%\Microsoft\WindowsApps\mnemos.cmd`); deleting it removes the
command and nothing else.

### Requirements
- **Windows 10/11** with WSL2 (the installer checks, and enables it if missing)
- **A container runtime**: Podman (`winget install RedHat.Podman`) or Docker
  Desktop. Either works; MNEMOS behaves identically on both.
- Hardware per the recommendations table above

> If you already have Docker Desktop, MNEMOS uses it. Docker and Podman keep
> separate volume stores: switching runtimes doesn't lose your indexed library,
> but it stops being visible until you migrate the database (see below).

### Manual installation

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
- **No GPU**: nothing to do — `docker compose up -d` no longer starts `llamacpp`. See the next section.

### Works with no LLM at all

You don't need a language model to get started. Run `start-lite.bat`, upload a PDF, and search it — no Ollama, no GPU, no API key.

| Works without an LLM | Needs an LLM |
|---|---|
| Upload and indexing (PDF, EPUB, audio, video, YouTube) | Chat with citations |
| Semantic search (pgvector) | Document summaries |
| Keyword search (Postgres FTS) | Concept graph and wiki |
| RRF fusion, MMR re-ranking | |

Documents indexed without an LLM finish as `completed`, never as errors — their chunks and embeddings are intact and searchable. The features that do need one show an explanation and a **"Connect a model"** button instead of an empty screen; the button opens Settings directly on Chat Settings with the connection form already expanded, not just the Settings page in general.

If you pick local llama.cpp and don't have a model installed yet, the same panel offers an **"Install a local model"** button that takes you to Discover Models — where you can search Hugging Face and pull a GGUF — instead of leaving you at a bare "No models found."

Once you connect a provider, Settings → Chat offers to generate the missing summaries and concepts for documents you already indexed. It reuses the existing index — nothing is re-uploaded or re-embedded — and it never starts on its own.

### Bring your own LLM server (slim mode)

MNEMOS ships with a bundled llama.cpp container, but you probably already run Ollama or LM Studio. Slim mode skips the bundled server entirely — no second model download, no GPU required.

**Requirements**: Docker. An OpenAI-compatible server is optional — without one you get indexing and search:
- **Ollama** → `http://localhost:11434/v1`
- **LM Studio** → `http://localhost:1234/v1` (start the server from the Developer tab)

```bash
git clone https://github.com/qepri/MNEMOS.git
cd mnemos/dev

# Create .env from the slim preset
powershell -ExecutionPolicy Bypass -File presets/apply.ps1 -Preset slim

# Start everything except the bundled LLM server
docker compose up -d
```

Open <http://localhost:5200>.

The preset targets Ollama by default. For LM Studio or a different port, edit `.env`:

```env
LLM_PROVIDER=lm_studio
LOCAL_LLM_BASE_URL=http://host.docker.internal:1234/v1
```

Use `host.docker.internal`, not `localhost` — inside a container `localhost` is the container itself.

> `LLM_PROVIDER=lm_studio` works with **any** OpenAI-compatible server (Ollama, vLLM, llama-server). The name is historical. Don't use `custom`: that path requires a stored connection in the database and fails on a fresh install.

**Verify**: `curl http://localhost:5000/api/ready` should return `200` and `"status": "ready"`. In slim mode the response has no `llamacpp` field — that's correct, there's no bundled server to report on.

**Want the bundled server instead?** `docker compose --profile local-llm up -d` (needs an NVIDIA GPU; set `LLM_PROVIDER=llamacpp` in `.env`).

Notes:
- **Embeddings run on CPU** in slim mode, leaving your GPU entirely to your own LLM server.
- **Switching modes is safe**: the slim preset doesn't touch `EMBEDDING_MODEL` or `EMBEDDING_DIMENSION`, so your existing documents and vectors stay valid.
- Presets only write `.env` when one doesn't exist. To convert an existing install, edit those three keys by hand.

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
| `POST` | `/api/documents/search` | LLM-free passage search (vector + FTS, no generation) |
| `GET` | `/api/documents/{id}/chunks` | Window of chunks around an index (read in context, EPUB/text) |
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
| `GET` | `/api/health` | Liveness (db + redis reachable) |
| `GET` | `/api/ready` | Readiness (migrations current + llama.cpp probe) |
| `GET` | `/api/settings/llm-availability` | LLM state (`unconfigured` / `unreachable` / `available`) |

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

MNEMOS exposes your library as MCP tools, so **any MCP-compatible agent** can search and query it — Claude Desktop, OpenCode, Cursor, or your own client. Every client points at the same server command:

```
docker exec -i dev-mcp-1 python -m app.mcp_server.server
```

### Example: Claude Desktop

This is just one concrete client — any MCP client is configured the same way, using the command above in its own config format. For Claude Desktop, edit `claude_desktop_config.json`:
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

~29 tools organized by domain (`tools_*.py` modules). The main ones:

- **Search**: `search_documents`, `search_documents_advanced`, `search_passages` (LLM-free retrieval: returns passages, not a generated answer)
- **Documents**: `list_documents`, `get_document_details`, `get_document_sections`, `get_document_summary`, `get_document_chunks` (read text in context), `upload_document`, `add_youtube_video`, `delete_document`
- **Graph / Wiki**: `search_concepts`, `list_concepts`, `get_concept_article`, `traverse_concepts`
- **Collections**: `list_collections`, `create_collection`, `get_collection_documents`, `add_document_to_collection`, `remove_document_from_collection`
- **Conversations & memory**: `list_conversations`, `get_conversation`, `search_conversations`, `create_conversation`, `get_user_memories`, `delete_memory`
- **Settings**: `get_system_prompts`, `get_active_settings`, `reprocess_document_hypergraph`
- **Reports**: `generate_pdf_report`

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
| Chat dormant although the LLM server is running | May be container networking, not a missing model | `docker-compose exec app python -c "import requests;print(requests.get('http://host.docker.internal:11434',timeout=3).status_code)"` — a failure here means networking |
| Library looks empty after switching runtime | Volumes are per-runtime | Your data is still in the other runtime — see "Switching between Docker and Podman" |
| Says no runtime found but `podman-machine-default` exists in WSL | Old install, CLI removed | `winget install RedHat.Podman`, or `wsl --unregister podman-machine-default` |

---

## Switching between Docker and Podman

Your uploaded files (`./data/uploads`) carry over automatically — they're plain
host folders. Only the database needs moving, because named volumes belong to
whichever runtime created them:

```bat
:: 1. With Docker still running - dump the database
docker-compose exec -T db pg_dump -U mnemos_user mnemos_db > backups\migrate.sql

:: 2. Stop the stack and start under Podman
docker-compose down
set MNEMOS_RUNTIME=podman
start-lite.bat

:: 3. Restore into Podman's database
type backups\migrate.sql | docker-compose exec -T db psql -U mnemos_user mnemos_db
```

Embeddings travel inside the dump — **nothing is re-embedded or re-uploaded**.
Keep `MNEMOS_RUNTIME=podman` set (or uninstall Docker Desktop) so later launches
don't flip back.

### GPU note under Podman

The bundled llama.cpp (`--profile local-llm`) needs NVIDIA CDI setup under
Podman/WSL2, which is manual. Slim mode — Ollama or LM Studio on the host — is
the recommended path under Podman and needs none of it.

## Updates

**Updates are manual.** MNEMOS does not check for new versions at startup, does
not update in the background, and does not notify you. It stays on the version
you have until you ask it to move:

```powershell
mnemos update
```

What it does, in this order:

1. Reads `MNEMOS_VERSION` from your `.env` and asks GitHub for the latest
   release. If they match, it does nothing and exits.
2. Asks you to confirm, showing which version to which.
3. **Backs up the database** to `backups/mnemos_db_<version>_<timestamp>.sql`
   and prints the path. If the backup fails or comes out empty, it stops
   without having changed anything.
4. Downloads the new version's files and **overlays** them onto what you have.
   It deletes no directories: your `.env` (with your API keys and settings),
   `uploads/`, `backups/` and `models/` are not in the archive and survive
   untouched.
5. Rewrites exactly the `MNEMOS_VERSION=` line of your `.env`.
6. Pulls the new images and restarts.

The backup goes **first** because schema migrations apply themselves when the
container starts — by the time the app answers, the database has already
changed.

**There is no automatic rollback**, deliberately: it would be the
least-tested path in the program and would only ever run when something had
already gone wrong. If the update fails, the script prints the backup path and
the command to restore it:

```powershell
cd $env:USERPROFILE\mnemos
docker-compose up -d --wait db
cmd /c 'docker-compose exec -T db psql -U mnemos_user mnemos_db < "backups\<your-backup>.sql"'
```

Single quotes outside, double inside: PowerShell hands the whole line to cmd,
which is what performs the `<` redirect. Swapping them does not work.

To take a backup any time, without updating anything:

```powershell
mnemos backup
```

It writes the dump to `backups/mnemos_db_<timestamp>.sql`, checks it did not
come out empty, and prints the restore command. It covers the database —
documents, chunks, graph, conversations and settings. Uploaded files live in
`uploads/` and are backed up separately, by copying the folder.

> If you installed by cloning the repo, your `.env` has no `MNEMOS_VERSION` and
> `mnemos update` will tell you so instead of acting. There, updating is
> `git pull` and `start.bat`.

The rules these scripts follow are written down in
[`INSTALLER-CONSTITUTION.md`](INSTALLER-CONSTITUTION.md).

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
