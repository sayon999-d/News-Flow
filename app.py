#!/usr/bin/env python3
"""
Breaking News Chatbot MVP - Single File
Fetches news, processes with Gemini, serves chat UI via Kafka
"""
import json
import os
import time
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional
from config import NEWSAPI_KEY, GOOGLE_API_KEY, KAFKA_SERVERS, FETCH_INTERVAL, EMBEDDING_MODEL

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import numpy as np

# Try to import Kafka and Pathway, but make them optional
try:
    from confluent_kafka import Consumer, Producer
    KAFKA_AVAILABLE = True
except ImportError:
    print("⚠️  Kafka not available - running in simplified mode")
    KAFKA_AVAILABLE = False

try:
    import pathway as pw
    PATHWAY_AVAILABLE = True
except ImportError:
    print("⚠️  Pathway not available - running in simplified mode")
    PATHWAY_AVAILABLE = False

# Global state
news_index = []  # List of {text, url, embedding}
model = SentenceTransformer(EMBEDDING_MODEL)

# Pathway schema for news processing (only if Pathway is available)
def create_pathway_pipeline():
    """Create Pathway streaming pipeline for real-time news processing"""
    if not PATHWAY_AVAILABLE or not KAFKA_AVAILABLE:
        print("⚠️  Pathway or Kafka not available - skipping streaming pipeline")
        return None
    
    try:
        # Only define schema if Pathway is actually available
        class NewsItem(pw.Schema):
            title: str
            url: str
            summary: str
            publishedAt: str
            fetched_at: str
            
        # Read from Kafka
        news_stream = pw.io.kafka.read(
            brokers=KAFKA_SERVERS,
            topic="news_raw",
            format="json",
            schema=NewsItem,
            autocommit_duration_ms=1000,
        )
        
        # Add embeddings using Pathway
        def embed_text(text: str) -> List[float]:
            if not text:
                return [0.0] * 384  # Default embedding size
            try:
                embedding = model.encode([text], normalize_embeddings=True)[0]
                return embedding.tolist()
            except:
                return [0.0] * 384
        
        # Process and add embeddings
        with_embeddings = news_stream.select(
            title=news_stream.title,
            url=news_stream.url,
            summary=news_stream.summary,
            publishedAt=news_stream.publishedAt,
            fetched_at=news_stream.fetched_at,
            embedding=pw.apply(embed_text, news_stream.summary),
        )
        
        # Write processed news to a new topic
        pw.io.kafka.write(
            with_embeddings,
            brokers=KAFKA_SERVERS,
            topic="news_processed",
            format="json",
        )
        
        return with_embeddings
    except Exception as e:
        print(f"⚠️  Pathway pipeline creation failed: {e}")
        return None

# FastAPI app
app = FastAPI(title="Breaking News Summary")

# Kafka setup (only if Kafka is available)
def get_producer():
    if not KAFKA_AVAILABLE:
        return None
    return Producer({
        "bootstrap.servers": KAFKA_SERVERS,
        "enable.idempotence": True,
        "retries": 5,
        "linger.ms": 20,
        "acks": "all",
    })

def get_consumer(group_id: str):
    if not KAFKA_AVAILABLE:
        return None
    return Consumer({
        "bootstrap.servers": KAFKA_SERVERS,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
    })

# News fetching
def fetch_news():
    """Fetch headlines from NewsAPI"""
    if not NEWSAPI_KEY:
        print("No NEWSAPI_KEY - skipping fetch")
        return []
    
    try:
        url = "https://newsapi.org/v2/top-headlines"
        params = {"apiKey": NEWSAPI_KEY, "country": "us", "pageSize": 20}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("articles", [])
    except Exception as e:
        print(f"NewsAPI error: {e}")
        return []

# Gemini summarization
def summarize_with_gemini(text: str) -> str:
    """Summarize text using Google Gemini API"""
    if not GOOGLE_API_KEY or not text:
        return ""
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = f"Summarize this news article in 2-3 sentences:\n\n{text[:4000]}"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini error: {e}")
        return ""

def simple_summarize(text: str) -> str:
    """Simple fallback summarization"""
    if not text:
        return ""
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    return '. '.join(sentences[:3])

def process_article_directly(article_data):
    """Process article directly when Kafka is not available"""
    try:
        title = article_data.get("title", "")
        description = article_data.get("description", "")
        url = article_data.get("url", "")
        fetched_at = article_data.get("fetched_at", "")
        
        # Combine title and description for summarization
        text = f"{title}. {description}".strip()
        
        # Use simple summarization to avoid Gemini quota issues
        # Only use Gemini for every 5th article to stay within quota
        if len(news_index) % 5 == 0:
            summary = summarize_with_gemini(text) or simple_summarize(text)
        else:
            summary = simple_summarize(text)
        
        if summary:
            # Add to in-memory index
            embedding = model.encode([summary], normalize_embeddings=True)[0]
            news_item = {
                "text": summary,
                "url": url,
                "title": title,
                "embedding": embedding.tolist(),
                "fetched_at": fetched_at,
                "is_realtime": True,
                "processed_at": datetime.utcnow().isoformat()
            }
            news_index.append(news_item)
            
            # Keep only last 100 items (most recent)
            if len(news_index) > 100:
                news_index.pop(0)
            
            print(f"✅ Indexed DIRECTLY: {title[:50]}... (fetched: {fetched_at})")
    except Exception as e:
        print(f"❌ Direct processor error: {e}")

# Background workers
def news_fetcher():
    """Background thread that continuously fetches real-time news and processes directly"""
    seen_urls = set()
    
    print("🔄 Starting real-time news fetcher...")
    
    while True:
        try:
            articles = fetch_news()
            new_articles = []
            current_time = datetime.utcnow().isoformat()
            
            for article in articles:
                url = article.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    article_data = {
                        "title": article.get("title", ""),
                        "description": article.get("description", ""),
                        "url": url,
                        "publishedAt": article.get("publishedAt", ""),
                        "fetched_at": current_time,
                        "is_realtime": True  # Mark as real-time data
                    }
                    new_articles.append(article_data)
                    
                    # Always process directly (simplified mode)
                    process_article_directly(article_data)
            
            if new_articles:
                print(f"📰 Processed {len(new_articles)} NEW real-time articles directly at {current_time}")
            
            # Keep only recent URLs to prevent memory bloat
            if len(seen_urls) > 1000:
                seen_urls = set(list(seen_urls)[-500:])
            
        except Exception as e:
            print(f"❌ Fetcher error: {e}")
        
        time.sleep(FETCH_INTERVAL)

def news_processor():
    """Background thread that processes real-time news and builds live index"""
    if not KAFKA_AVAILABLE:
        print("⚠️  Kafka not available - skipping news processor (using direct processing)")
        return
        
    consumer = get_consumer("news-processor")
    if not consumer:
        print("⚠️  Consumer not available - skipping news processor")
        return
        
    consumer.subscribe(["news_raw"])
    
    print("🔄 Starting real-time news processor...")
    
    while True:
        try:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"❌ Consumer error: {msg.error()}")
                continue
            
            article = json.loads(msg.value().decode("utf-8"))
            title = article.get("title", "")
            description = article.get("description", "")
            url = article.get("url", "")
            is_realtime = article.get("is_realtime", False)
            fetched_at = article.get("fetched_at", "")
            
            # Combine title and description for summarization
            text = f"{title}. {description}".strip()
            
            # Summarize with Gemini or fallback
            summary = summarize_with_gemini(text) or simple_summarize(text)
            
            if summary:
                # Add to in-memory index with real-time metadata
                embedding = model.encode([summary], normalize_embeddings=True)[0]
                news_item = {
                    "text": summary,
                    "url": url,
                    "title": title,
                    "embedding": embedding.tolist(),
                    "fetched_at": fetched_at,
                    "is_realtime": is_realtime,
                    "processed_at": datetime.utcnow().isoformat()
                }
                news_index.append(news_item)
                
                # Keep only last 100 items (most recent)
                if len(news_index) > 100:
                    news_index.pop(0)
                
                print(f"✅ Indexed REAL-TIME: {title[:50]}... (fetched: {fetched_at})")
                
        except Exception as e:
            print(f"❌ Processor error: {e}")

def pathway_processor():
    """Background thread running Pathway streaming pipeline for real-time processing"""
    if not PATHWAY_AVAILABLE or not KAFKA_AVAILABLE:
        print("⚠️  Pathway or Kafka not available - skipping streaming pipeline")
        return
        
    try:
        print("🚀 Starting Pathway REAL-TIME streaming pipeline...")
        pipeline = create_pathway_pipeline()
        if pipeline:
            print("✅ Pathway pipeline active - processing real-time news streams")
            pw.run()
        else:
            print("⚠️  Pathway pipeline creation failed")
    except Exception as e:
        print(f"❌ Pathway error: {e}")
        print("🔄 Retrying Pathway pipeline in 5 seconds...")
        time.sleep(5)
        # Retry the pipeline
        try:
            pipeline = create_pathway_pipeline()
            if pipeline:
                pw.run()
        except Exception as retry_error:
            print(f"❌ Pathway retry failed: {retry_error}")

# API endpoints
@app.get("/", response_class=HTMLResponse)
def chat_ui():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NewsFlow - AI News Summary</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            
            body { 
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; 
                background: #0b0b0b;
                min-height: 100vh;
                color: #e5e7eb;
            }
            
            .container { 
                max-width: 1200px; 
                margin: 0 auto; 
                padding: 20px;
            }
            
            .header { 
                text-align: center; 
                margin-bottom: 40px; 
                color: white;
            }
            
            .header h1 { 
                font-size: 3rem; 
                font-weight: 700; 
                margin-bottom: 10px;
                text-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }
            
            .header p { 
                font-size: 1.2rem; 
                opacity: 0.9; 
                font-weight: 300;
            }
            
            .main-content {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 30px;
                margin-bottom: 30px;
            }
            
            .summary { 
                background: #111111;
                backdrop-filter: blur(10px);
                border-radius: 20px; 
                padding: 30px; 
                box-shadow: 0 20px 40px rgba(0,0,0,0.6);
                border: 1px solid rgba(255,255,255,0.08);
            }
            
            .summary-header {
                display: flex;
                align-items: center;
                margin-bottom: 20px;
                gap: 10px;
            }
            
            .summary h3 { 
                color: #ffffff; 
                font-size: 1.5rem;
                font-weight: 600;
            }
            
            .summary-text { 
                line-height: 1.7; 
                color: #e5e7eb; 
                font-size: 16px;
                margin-bottom: 20px;
                background: #0f1115;
                padding: 20px;
                border-radius: 12px;
                border-left: 4px solid #ffffff;
            }
            
            .refresh-btn { 
                background: #ffffff;
                color: #000000; 
                border: none; 
                padding: 12px 24px; 
                border-radius: 50px; 
                cursor: pointer; 
                font-weight: 500;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(255, 255, 255, 0.1);
            }
            
            .refresh-btn:hover { 
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(255, 255, 255, 0.15);
            }
            
            .latest { 
                background: #111111;
                backdrop-filter: blur(10px);
                border-radius: 20px; 
                padding: 30px; 
                box-shadow: 0 20px 40px rgba(0,0,0,0.6);
                border: 1px solid rgba(255,255,255,0.08);
                max-height: 600px;
                overflow-y: auto;
            }
            
            .latest h3 { 
                color: #ffffff; 
                margin-bottom: 20px; 
                font-size: 1.5rem;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .status { 
                text-align: center; 
                color: #9ca3af; 
                margin-bottom: 20px;
                font-weight: 500;
                background: #1f2937;
                padding: 8px 16px;
                border-radius: 20px;
                display: inline-block;
            }
            
            .news-grid {
                display: grid;
                gap: 16px;
            }
            
            .card { 
                background: #1a1a1a;
                border: 1px solid #333333; 
                border-radius: 16px; 
                padding: 20px; 
                transition: all 0.3s ease;
                position: relative;
                overflow: hidden;
            }
            
            .card::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 3px;
                background: linear-gradient(90deg, #ffffff, #aaaaaa);
                transform: scaleX(0);
                transition: transform 0.3s ease;
            }
            
            .card:hover { 
                transform: translateY(-4px);
                box-shadow: 0 10px 25px rgba(0,0,0,0.5);
                border-color: #ffffff;
            }
            
            .card:hover::before {
                transform: scaleX(1);
            }
            
            .card-title { 
                font-weight: 600; 
                color: #f5f5f5; 
                margin-bottom: 12px;
                font-size: 1.1rem;
                line-height: 1.4;
            }
            
            .card-title a { 
                color: #ffffff; 
                text-decoration: none;
                transition: color 0.3s ease;
            }
            
            .card-title a:hover { 
                color: #dddddd;
                text-decoration: underline;
            }
            
            .card-text { 
                color: #d1d5db; 
                font-size: 14px; 
                line-height: 1.6;
                margin-bottom: 12px;
            }
            
            .card-meta { 
                color: #9ca3af; 
                font-size: 12px;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .loading {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid #555555;
                border-radius: 50%;
                border-top-color: #ffffff;
                animation: spin 1s ease-in-out infinite;
            }
            
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            
            .stats {
                background: #111111;
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 20px;
                margin-bottom: 20px;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                border: 1px solid rgba(255,255,255,0.08);
            }
            
            .stat-item {
                text-align: center;
                padding: 15px;
                background: #1a1a1a;
                border-radius: 12px;
                border: 1px solid #333333;
            }
            
            .stat-number {
                font-size: 2rem;
                font-weight: 700;
                color: #ffffff;
                margin-bottom: 5px;
            }
            
            .stat-label {
                color: #9ca3af;
                font-size: 0.9rem;
                font-weight: 500;
            }
            
            @media (max-width: 768px) {
                .main-content {
                    grid-template-columns: 1fr;
                }
                
                .header h1 {
                    font-size: 2rem;
                }
                
                .container {
                    padding: 15px;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 NewsFlow</h1>
                <p>AI-Powered Real-time News Intelligence</p>
            </div>
            
            <div class="stats" id="stats">
                <div class="stat-item">
                    <div class="stat-number" id="article-count">-</div>
                    <div class="stat-label">Articles Processed</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="last-update">-</div>
                    <div class="stat-label">Last Update</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="system-status">🟢</div>
                    <div class="stat-label">System Status</div>
                </div>
            </div>
            
            <div class="main-content">
                <div class="summary">
                    <div class="summary-header">
                        <h3>🤖 AI Intelligence Summary</h3>
                    </div>
                    <div id="summary" class="summary-text">
                        <div class="loading"></div> Generating intelligent news summary...
                    </div>
                    <button class="refresh-btn" onclick="loadSummary()">
                        🔄 Refresh Intelligence
                    </button>
                </div>
                
                <div class="latest">
                    <h3>📋 Latest Intelligence Feed</h3>
                    <div class="status" id="status">Initializing news feed...</div>
                    <div class="news-grid" id="latest"></div>
                </div>
            </div>
        </div>
        
        <script>
            async function loadSummary() {
                const summaryEl = document.getElementById('summary');
                summaryEl.innerHTML = '<div class="loading"></div> Generating intelligent summary...';
                
                try {
                    const res = await fetch('/summary');
                    const data = await res.json();
                    summaryEl.innerHTML = data.summary || 'No intelligence data available yet.';
                } catch (error) {
                    summaryEl.innerHTML = 'Error generating summary. Please try again.';
                }
            }
            
            async function loadLatest() {
                const res = await fetch('/latest');
                const list = await res.json();
                const el = document.getElementById('latest');
                const status = document.getElementById('status');
                
                if (list.length === 0) {
                    status.textContent = 'No intelligence data available yet.';
                    el.innerHTML = '';
                    return;
                }
                
                status.textContent = `Processing ${list.length} intelligence reports`;
                el.innerHTML = '';
                
                list.forEach(i => {
                    const d = document.createElement('div');
                    d.className = 'card';
                    d.innerHTML = `
                        <div class="card-title">
                            <a href="${i.url}" target="_blank">${i.title}</a>
                        </div>
                        <div class="card-text">${i.text}</div>
                        <div class="card-meta">
                            🕒 ${new Date(i.fetched_at).toLocaleString()}
                        </div>
                    `;
                    el.appendChild(d);
                });
                
                // Update stats
                document.getElementById('article-count').textContent = list.length;
                document.getElementById('last-update').textContent = 'Now';
            }
            
            // Load initial data
            loadSummary();
            loadLatest();
            
            // Auto-refresh every 30 seconds
            setInterval(() => {
                loadSummary();
                loadLatest();
            }, 30000);
        </script>
    </body>
    </html>
    """

# Removed QA endpoint - now using summary instead

@app.get("/summary")
def get_summary():
    """Get AI-generated summary of all latest news"""
    print(f"🔍 Summary endpoint called - news_index length: {len(news_index)}")
    
    if not news_index:
        return {"summary": "No news articles available yet. Please wait for news to be processed."}
    
    # Get all recent news items
    recent_items = news_index[-20:]  # Get last 20 items for better context
    
    # Create context text for summarization
    context_text = "\n".join([f"• {item['title']}: {item['text']}" for item in recent_items])
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=GOOGLE_API_KEY)
        model_gemini = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = f"""Please provide a comprehensive summary of the following breaking news articles. 
        Organize the summary by major topics/themes and highlight the most important developments.
        Keep it informative but concise (2-3 paragraphs).

        News Articles:
        {context_text}

        Summary:"""
        
        response = model_gemini.generate_content(prompt)
        summary = response.text.strip()
        
        print(f"✅ Generated summary using Gemini")
        return {"summary": summary, "article_count": len(recent_items)}
        
    except Exception as e:
        print(f"⚠️  Gemini summary failed: {e}")
        # Fallback to simple summary
        topics = {}
        for item in recent_items:
            # Simple topic extraction (first few words of title)
            topic = item['title'].split()[:3]
            topic_key = ' '.join(topic)
            if topic_key not in topics:
                topics[topic_key] = []
            topics[topic_key].append(item['text'])
        
        summary_parts = []
        for topic, articles in list(topics.items())[:5]:  # Top 5 topics
            summary_parts.append(f"**{topic}**: {' '.join(articles[:2])}")
        
        fallback_summary = "\n\n".join(summary_parts)
        return {"summary": fallback_summary, "article_count": len(recent_items)}

@app.get("/latest")
def latest():
    """Get latest REAL-TIME indexed news"""
    print(f"🔍 Latest endpoint called - news_index length: {len(news_index)}")
    if not news_index:
        print("⚠️  No news indexed yet")
        return []
    
    # Return most recent 10 items with real-time metadata
    recent_items = news_index[-10:]
    print(f"📰 Returning {len(recent_items)} recent items")
    return recent_items

@app.get("/health")
def health():
    """Health check with real-time status"""
    realtime_count = sum(1 for item in news_index if item.get("is_realtime", False))
    return {
        "status": "ok", 
        "indexed_news": len(news_index),
        "realtime_news": realtime_count,
        "processing_status": "✅ Real-time processing active",
        "kafka_status": "✅ Available" if KAFKA_AVAILABLE else "❌ Not available",
        "pathway_status": "✅ Available" if PATHWAY_AVAILABLE else "❌ Not available",
        "mode": "Full Kafka + Pathway" if KAFKA_AVAILABLE and PATHWAY_AVAILABLE else "Simplified Direct Processing"
    }

# Startup
@app.on_event("startup")
def startup():
    """Start background workers for REAL-TIME processing"""
    print("🚀 Starting Breaking News Chatbot MVP with REAL-TIME processing...")
    print(f"📰 NewsAPI Key: {'✅' if NEWSAPI_KEY else '❌'}")
    print(f"🤖 Gemini Key: {'✅' if GOOGLE_API_KEY else '❌'}")
    print(f"📡 Kafka: {'✅' if KAFKA_AVAILABLE else '❌'} ({KAFKA_SERVERS})")
    print(f"⚡ Pathway: {'✅' if PATHWAY_AVAILABLE else '❌'} (REAL-TIME streaming pipeline)")
    print("🔄 Real-time data processing: ACTIVE")
    
    # Start background threads for continuous real-time processing
    threading.Thread(target=news_fetcher, daemon=True).start()
    
    # Start in simplified mode (direct processing without Kafka)
    print("✅ Background workers started - REAL-TIME news processing ACTIVE (simplified mode)")
    print("📰 News will be fetched and processed directly without Kafka")
    
    print("🎯 System will continuously fetch, process, and index latest news")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
