# Breaking News Chatbot MVP

A real-time news chatbot that fetches headlines, processes them with AI, and provides intelligent answers using RAG (Retrieval-Augmented Generation). Built with Pathway for streaming processing, Google Gemini for summarization, and Kafka for message streaming.

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- NewsAPI key (free at https://newsapi.org)
- Google Gemini API key (free at https://makersuite.google.com/app/apikey)

### Setup & Run

1. **Clone and navigate to the project:**
```bash
cd /Users/rehanshamsi/Desktop/demo
```

2. **Add your API keys to `.env`:**
```bash
echo "NEWSAPI_KEY=your_newsapi_key_here" >> .env
echo "GOOGLE_API_KEY=your_gemini_key_here" >> .env
```

3. **Start the application:**
```bash
docker compose up -d --build
```

4. **Open the chat interface:**
   - Navigate to http://localhost:8000
   - Ask questions about the latest news!

## 🏗️ Architecture

### System Overview
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   NewsAPI   │───▶│   Kafka    │───▶│  Pathway   │───▶│  FastAPI   │
│ (External)  │    │ (Streaming)│    │(Processing)│    │ (RAG+UI)  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### Components

**1. Data Ingestion**
- Fetches headlines from NewsAPI every 60 seconds
- Deduplicates articles by URL
- Publishes to Kafka `news_raw` topic

**2. Streaming Processing (Pathway)**
- Real-time Kafka consumption using `pw.io.kafka.read()`
- Applies embeddings via `pw.apply(embed_text)`
- Streams processed data to `news_processed` topic
- Runs continuously with `pw.run()`

**3. AI Processing**
- **Google Gemini**: Intelligent summarization of news articles
- **SentenceTransformers**: Vector embeddings for similarity search
- **Fallback**: Simple text summarization if Gemini unavailable

**4. RAG System**
- In-memory vector index for fast retrieval
- Rolling window of last 100 news items
- Real-time similarity search for question answering

**5. User Interface**
- FastAPI web server with chat UI
- Real-time question answering
- Latest news display with auto-refresh

## 📊 Data Flow

```
1. NewsAPI (60s) → Kafka news_raw
2. Pathway reads news_raw → adds embeddings → writes news_processed  
3. App consumes news_processed → builds vector index
4. User asks question → RAG search → returns answer + sources
```

## 🔧 Configuration

### Environment Variables
- `NEWSAPI_KEY`: Your NewsAPI key (required)
- `GOOGLE_API_KEY`: Your Gemini API key (optional, uses fallback if not provided)
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka servers (default: localhost:9092)
- `FETCH_INTERVAL_SECONDS`: News fetch interval (default: 60)
- `EMBEDDING_MODEL`: Sentence transformer model (default: all-MiniLM-L6-v2)

### API Endpoints
- `GET /` - Chat interface
- `POST /qa` - Ask questions (JSON: `{"question": "your question"}`)
- `GET /latest` - Recent news items
- `GET /health` - System status

## 🛠️ Development

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (requires Kafka running)
python app.py
```

### Docker Development
```bash
# Build and run
docker compose up -d --build

# View logs
docker compose logs -f app

# Stop services
docker compose down
```

## 📈 Features

### Real-time Processing
- **Pathway Streaming**: Continuous processing of news streams
- **Kafka Durability**: Reliable message delivery and storage
- **Auto-scaling**: Handles varying news volumes

### AI-Powered Intelligence
- **Gemini Summarization**: High-quality article summaries
- **Vector Search**: Semantic similarity for relevant news retrieval
- **RAG Answers**: Context-aware responses based on recent news

### User Experience
- **Simple Interface**: Clean chat UI for easy interaction
- **Fast Responses**: Sub-second answer generation
- **Live Updates**: Auto-refreshing latest news display

## 🔍 Troubleshooting

### Common Issues

**1. No news appearing:**
- Check NewsAPI key is valid and not rate-limited
- Verify Kafka is running: `docker compose ps`
- Check logs: `docker compose logs app`

**2. Gemini not working:**
- Verify Google API key is correct
- Check API quotas and billing
- App will use fallback summarization

**3. Kafka connection issues:**
- Ensure Kafka is fully started: `docker compose logs kafka`
- Check network connectivity between services
- Restart services: `docker compose restart`

### Health Checks
```bash
# Check service status
curl http://localhost:8000/health

# View recent news
curl http://localhost:8000/latest

# Test question answering
curl -X POST http://localhost:8000/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "What is happening in tech news?"}'
```

## 🚀 Production Considerations

### Scaling
- **Horizontal**: Add more app instances behind load balancer
- **Vertical**: Increase memory for larger vector index
- **Storage**: Add Redis/PostgreSQL for persistence

### Monitoring
- **Health Endpoint**: `/health` for system status
- **Logs**: Structured logging for debugging
- **Metrics**: Kafka consumer lag monitoring

### Security
- **API Keys**: Store in environment variables
- **Network**: Internal Docker network for service communication
- **Rate Limiting**: Built-in NewsAPI and Gemini rate limits

## 📝 License

MIT License - feel free to use and modify for your projects!

## 🤝 Contributing

This is a hackathon MVP - contributions welcome! Areas for improvement:
- Add Twitter/X news ingestion
- Implement streaming vector database
- Add real-time UI updates via WebSocket
- Enhance error handling and monitoring

