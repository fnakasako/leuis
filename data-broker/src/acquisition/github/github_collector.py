"""
GitHub Events Collector
Collects repository events from GitHub API and publishes to Kafka
"""

import os
import json
import time
import logging
from datetime import datetime
import requests
from kafka import KafkaProducer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GitHubCollector:
    def __init__(self, kafka_bootstrap_servers, github_token=None):
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.topic = "github_events"
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {github_token}" if github_token else None
        }
        self.rate_limit_remaining = None
        self.rate_limit_reset = None

    def _check_rate_limit(self):
        """Check GitHub API rate limit status"""
        try:
            response = requests.get(
                f"{self.base_url}/rate_limit",
                headers=self.headers
            )
            response.raise_for_status()
            limits = response.json()["resources"]["core"]
            self.rate_limit_remaining = limits["remaining"]
            self.rate_limit_reset = limits["reset"]
            
            if self.rate_limit_remaining == 0:
                wait_time = self.rate_limit_reset - int(time.time())
                if wait_time > 0:
                    logger.warning(f"Rate limit exceeded. Waiting {wait_time} seconds.")
                    time.sleep(wait_time)
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"Error checking rate limit: {e}")

    def fetch_events(self, repository):
        """Fetch events for a specific repository"""
        self._check_rate_limit()
        
        try:
            url = f"{self.base_url}/repos/{repository}/events"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return self._process_events(response.json())
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching events for {repository}: {e}")
            return []

    def _process_events(self, events):
        """Process and format GitHub events"""
        processed_events = []
        for event in events:
            try:
                processed_event = {
                    "event_id": event["id"],
                    "event_type": event["type"],
                    "repository": event["repo"]["name"],
                    "user": event["actor"]["login"],
                    "timestamp": event["created_at"],
                    "payload": event["payload"],
                    "year": datetime.strptime(event["created_at"], "%Y-%m-%dT%H:%M:%SZ").year,
                    "month": datetime.strptime(event["created_at"], "%Y-%m-%dT%H:%M:%SZ").month,
                    "day": datetime.strptime(event["created_at"], "%Y-%m-%dT%H:%M:%SZ").day
                }
                processed_events.append(processed_event)
            except KeyError as e:
                logger.error(f"Error processing event {event.get('id', 'unknown')}: {e}")
                continue
                
        return processed_events

    def publish_events(self, events):
        """Publish events to Kafka"""
        for event in events:
            try:
                self.producer.send(self.topic, event)
                logger.info(f"Published event {event['event_id']}")
            except Exception as e:
                logger.error(f"Error publishing event {event['event_id']}: {e}")

    def run(self, repositories, interval_seconds=300):
        """Main collection loop"""
        while True:
            for repo in repositories:
                events = self.fetch_events(repo)
                self.publish_events(events)
                time.sleep(2)  # Small delay between repository requests
            
            logger.info(f"Completed event collection cycle. Waiting {interval_seconds} seconds.")
            time.sleep(interval_seconds)

if __name__ == "__main__":
    # Example repositories to monitor
    target_repos = [
        "tensorflow/tensorflow",
        "pytorch/pytorch",
        "huggingface/transformers",
        "microsoft/DeepSpeed"
    ]
    
    collector = GitHubCollector(
        kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        github_token=os.getenv("GITHUB_TOKEN")
    )
    collector.run(target_repos)
