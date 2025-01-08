"""
News Collector
Collects news articles from various sources and publishes to Kafka
Currently supports NewsAPI, but can be extended for other sources
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
import hashlib
import requests
from kafka import KafkaProducer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsCollector:
    def __init__(self, kafka_bootstrap_servers, newsapi_key=None):
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.topic = "news_feed"
        self.newsapi_key = newsapi_key or os.getenv("NEWSAPI_KEY")
        if not self.newsapi_key:
            raise ValueError("NewsAPI key is required")
        
        self.base_url = "https://newsapi.org/v2"
        self.categories = [
            "technology", "science", "business",
            "health", "general"
        ]

    def _generate_article_id(self, article):
        """Generate a unique ID for an article"""
        unique_string = f"{article['url']}{article['publishedAt']}"
        return hashlib.sha256(unique_string.encode()).hexdigest()

    def fetch_articles(self, category, from_date):
        """Fetch articles from NewsAPI for a specific category"""
        endpoint = f"{self.base_url}/top-headlines"
        
        params = {
            "category": category,
            "language": "en",
            "from": from_date.isoformat(),
            "sortBy": "publishedAt",
            "pageSize": 100,
            "apiKey": self.newsapi_key
        }
        
        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            return self._process_articles(response.json()["articles"], category)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {category} news: {e}")
            return []
        except KeyError as e:
            logger.error(f"Error parsing response for {category}: {e}")
            return []

    def _process_articles(self, articles, category):
        """Process and format news articles"""
        processed_articles = []
        
        for article in articles:
            try:
                # Parse the publication date
                pub_date = datetime.strptime(
                    article["publishedAt"],
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                
                processed_article = {
                    "article_id": self._generate_article_id(article),
                    "title": article["title"],
                    "content": article["content"],
                    "source": article["source"]["name"],
                    "author": article["author"] or "Unknown",
                    "category": category,
                    "url": article["url"],
                    "timestamp": article["publishedAt"],
                    "year": pub_date.year,
                    "month": pub_date.month,
                    "day": pub_date.day
                }
                
                processed_articles.append(processed_article)
            except (KeyError, ValueError) as e:
                logger.error(f"Error processing article: {e}")
                continue
                
        return processed_articles

    def publish_articles(self, articles):
        """Publish articles to Kafka"""
        for article in articles:
            try:
                self.producer.send(self.topic, article)
                logger.info(f"Published article {article['article_id']}")
            except Exception as e:
                logger.error(f"Error publishing article {article['article_id']}: {e}")

    def run(self, interval_minutes=15):
        """Main collection loop"""
        while True:
            from_date = datetime.utcnow() - timedelta(minutes=interval_minutes)
            
            for category in self.categories:
                try:
                    logger.info(f"Fetching {category} news")
                    articles = self.fetch_articles(category, from_date)
                    self.publish_articles(articles)
                    
                    # Respect API rate limits
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"Error processing category {category}: {e}")
                    continue
            
            logger.info(f"Completed news collection cycle. Waiting {interval_minutes} minutes.")
            time.sleep(interval_minutes * 60)

class NewsSourceAdapter:
    """Base class for implementing additional news sources"""
    
    def __init__(self):
        self.name = "base_adapter"
    
    def fetch_articles(self, from_date):
        """Fetch articles from the source"""
        raise NotImplementedError
    
    def process_articles(self, raw_articles):
        """Process articles into standard format"""
        raise NotImplementedError

if __name__ == "__main__":
    collector = NewsCollector(
        kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        newsapi_key=os.getenv("NEWSAPI_KEY")
    )
    collector.run()
