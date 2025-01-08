"""
ArXiv Data Collector
Fetches papers from ArXiv API and publishes to Kafka
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
import requests
from kafka import KafkaProducer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ArXivCollector:
    def __init__(self, kafka_bootstrap_servers):
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.base_url = "http://export.arxiv.org/api/query"
        self.topic = "arxiv_raw"

    def fetch_papers(self, start_date, max_results=100):
        """Fetch papers from ArXiv API"""
        query_params = {
            'search_query': f'submittedDate:[{start_date.strftime("%Y%m%d")}0000 TO {datetime.now().strftime("%Y%m%d")}2359]',
            'start': 0,
            'max_results': max_results,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending'
        }
        
        try:
            response = requests.get(self.base_url, params=query_params)
            response.raise_for_status()
            return self._parse_response(response.text)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching papers: {e}")
            return []

    def _parse_response(self, response_text):
        """Parse ArXiv API response"""
        # Implementation would parse the XML response
        # and extract relevant paper information
        papers = []
        # XML parsing logic here
        return papers

    def publish_papers(self, papers):
        """Publish papers to Kafka"""
        for paper in papers:
            try:
                self.producer.send(self.topic, paper)
                logger.info(f"Published paper {paper['id']}")
            except Exception as e:
                logger.error(f"Error publishing paper {paper['id']}: {e}")

    def run(self, interval_minutes=60):
        """Main collection loop"""
        while True:
            start_date = datetime.now() - timedelta(days=1)
            papers = self.fetch_papers(start_date)
            self.publish_papers(papers)
            time.sleep(interval_minutes * 60)

if __name__ == "__main__":
    collector = ArXivCollector(os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
    collector.run()
