# Eraser.io Technical Design Prompt

## Project: Breaking News Chatbot MVP

Create a comprehensive technical architecture diagram for a real-time news chatbot system with the following specifications:

### System Overview
- **Purpose**: Real-time news chatbot that continuously fetches headlines, processes with AI, and provides intelligent answers using RAG
- **Architecture**: Single-file MVP with real-time streaming processing powered by Pathway
- **Key Technologies**: Kafka, Pathway (streaming engine), Google Gemini, FastAPI, SentenceTransformers
- **Real-time Focus**: Continuous data ingestion, real-time processing, and instant user responses

### Components to Include

#### 1. External Services
- **NewsAPI** (External)
  - Continuously fetches headlines every 60 seconds
  - Provides real-time news data in JSON format
  - Rate limited by API key
  - Ensures always fresh, up-to-date news content

- **Google Gemini API** (External)
  - AI summarization service
  - Processes news articles for intelligent summaries
  - Fallback to simple text summarization if unavailable

#### 2. Message Streaming Layer
- **Zookeeper**
  - Kafka coordination service
  - Manages broker metadata and consumer groups
  - Handles fault tolerance and leader election

- **Kafka Cluster**
  - Distributed streaming platform
  - Two topics: `news_raw` and `news_processed`
  - Handles message durability and delivery

#### 3. Processing Layer (Pathway-Powered Real-time Processing)
- **Pathway Streaming Pipeline** (Core Real-time Engine)
  - Real-time Kafka consumption using `pw.io.kafka.read()`
  - Continuous stream processing with micro-batch updates
  - Applies embeddings via `pw.apply(embed_text)` in real-time
  - Streams processed data to `news_processed` topic instantly
  - Runs continuously with `pw.run()` for zero-latency processing
  - **Pathway Strengths**: Handles backpressure, fault tolerance, and exactly-once processing
  - **Real-time Benefits**: Sub-second processing, automatic scaling, and reliable delivery

#### 4. Application Layer (Real-time RAG System)
- **FastAPI Application** (Single file: app.py)
  - Background threads:
    - `news_fetcher`: Continuously fetches from NewsAPI → Kafka (real-time ingestion)
    - `news_processor`: Consumes processed news → builds real-time vector index
    - `pathway_processor`: Runs Pathway streaming pipeline (core real-time engine)
  - **Real-time Vector Index**: Continuously updated with latest news embeddings
  - **Live RAG System**: Always uses most recent news for answers
  - API endpoints: `/`, `/qa`, `/latest`, `/health`
  - **Real-time Features**: Sub-second response times, always fresh data

#### 5. User Interface
- **Chat UI** (HTML/JavaScript)
  - Real-time question answering
  - Latest news display with auto-refresh
  - Simple chat interface

### Real-time Data Flow
1. **NewsAPI** (Continuous 60s) → **Kafka news_raw** (Real-time ingestion)
2. **Pathway** reads news_raw → adds embeddings → writes news_processed (Sub-second processing)
3. **App** consumes news_processed → builds real-time vector index (Live updates)
4. **User** asks question → RAG search over latest news → returns real-time answer
5. **UI** auto-refreshes with latest news (Every 10 seconds)

### Technology Stack
- **Streaming**: Kafka + Zookeeper + Pathway
- **AI**: Google Gemini + SentenceTransformers
- **API**: FastAPI + Uvicorn
- **Storage**: In-memory vector index
- **Infrastructure**: Docker Compose

### Key Features to Highlight
- **Real-time Processing**: Pathway streaming pipeline with zero-latency processing
- **Always Fresh Data**: Continuous news ingestion and real-time updates
- **AI-Powered**: Gemini summarization + real-time vector search
- **Fault Tolerant**: Kafka durability + Zookeeper coordination + Pathway reliability
- **Scalable**: Horizontal scaling with Kafka partitions + Pathway auto-scaling
- **Simple**: Single-file architecture with powerful real-time capabilities
- **Pathway Advantages**: Handles backpressure, exactly-once processing, and automatic recovery

### Visual Elements to Include
- **Data Flow Arrows**: Show direction of data movement
- **Component Boxes**: Different colors for different layers
- **Topic Labels**: `news_raw` and `news_processed` topics
- **Thread Labels**: Background processing threads
- **API Endpoints**: REST API connections
- **External Services**: Cloud-based APIs
- **Docker Containers**: Service boundaries

### Layout Suggestions
- **Top**: External services (NewsAPI, Gemini)
- **Middle**: Streaming layer (Kafka, Zookeeper, Pathway)
- **Bottom**: Application layer (FastAPI, UI)
- **Side**: Data flow arrows and topic connections

### Additional Notes
- Show the single-file architecture (app.py) as a central component
- Highlight the real-time nature with streaming arrows and "LIVE" indicators
- Include error handling and fallback mechanisms
- Show the in-memory vector index as a continuously updated component
- Emphasize the RAG (Retrieval-Augmented Generation) flow with real-time data
- **Pathway Focus**: Show Pathway as the core real-time processing engine
- **Real-time Indicators**: Use "REAL-TIME", "LIVE", "CONTINUOUS" labels
- **Data Freshness**: Emphasize that answers are always based on the latest news
- **Pathway Benefits**: Highlight backpressure handling, fault tolerance, and exactly-once processing

### Color Scheme Suggestions
- **External Services**: Blue
- **Streaming Layer**: Green
- **Processing Layer**: Orange
- **Application Layer**: Purple
- **Data Flow**: Gray arrows

This should create a comprehensive technical design diagram that clearly shows the architecture, data flow, and key components of the Breaking News Chatbot MVP system.
