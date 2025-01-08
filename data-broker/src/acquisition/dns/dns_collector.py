"""
DNS Data Collector
Captures DNS queries and responses using dnspython and publishes to Kafka
"""

import os
import json
import time
import logging
import socket
import threading
from datetime import datetime
import uuid
from typing import Dict, Any

import dns.message
import dns.rdatatype
import dns.resolver
from dns.exception import DNSException
from kafka import KafkaProducer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DNSCollector:
    def __init__(self, kafka_bootstrap_servers, interface="0.0.0.0", port=53):
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.topic = "dns_data"
        self.interface = interface
        self.port = port
        self.running = False
        self.udp_socket = None
        self.tcp_socket = None
        
        # Cache for tracking query-response pairs
        self.query_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_lock = threading.Lock()
        
        # Start cache cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_cache)
        self.cleanup_thread.daemon = True

    def _setup_sockets(self):
        """Set up UDP and TCP sockets for DNS capture"""
        try:
            # UDP Socket
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.bind((self.interface, self.port))
            
            # TCP Socket
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.bind((self.interface, self.port))
            self.tcp_socket.listen(5)
            
            logger.info(f"DNS collector listening on {self.interface}:{self.port}")
        except Exception as e:
            logger.error(f"Error setting up sockets: {e}")
            raise

    def _cleanup_cache(self):
        """Periodically clean up old entries from query cache"""
        while self.running:
            time.sleep(60)  # Run cleanup every minute
            current_time = time.time()
            
            with self.cache_lock:
                to_delete = []
                for query_id, data in self.query_cache.items():
                    if current_time - data["timestamp"] > 300:  # 5 minutes timeout
                        to_delete.append(query_id)
                
                for query_id in to_delete:
                    del self.query_cache[query_id]

    def _process_dns_message(self, message, is_response=False):
        """Process a DNS message and format it for storage"""
        try:
            dns_msg = dns.message.from_wire(message)
            
            # Generate a unique ID for the query/response pair
            query_id = str(uuid.uuid4())
            
            timestamp = datetime.utcnow()
            
            processed_data = {
                "query_id": query_id,
                "timestamp": timestamp.isoformat(),
                "year": timestamp.year,
                "month": timestamp.month,
                "day": timestamp.day,
                "is_response": is_response,
                "message_id": dns_msg.id,
                "flags": dns_msg.flags,
                "questions": [],
                "answers": []
            }
            
            # Process questions
            for question in dns_msg.question:
                processed_data["questions"].append({
                    "name": str(question.name),
                    "type": dns.rdatatype.to_text(question.rdtype),
                    "class": dns.rdataclass.to_text(question.rdclass)
                })
            
            # Process answers for responses
            if is_response:
                for rrset in dns_msg.answer:
                    for rdata in rrset:
                        processed_data["answers"].append({
                            "name": str(rrset.name),
                            "type": dns.rdatatype.to_text(rrset.rdtype),
                            "ttl": rrset.ttl,
                            "data": str(rdata)
                        })
            
            return processed_data
            
        except DNSException as e:
            logger.error(f"Error processing DNS message: {e}")
            return None

    def _handle_udp(self):
        """Handle UDP DNS messages"""
        while self.running:
            try:
                message, addr = self.udp_socket.recvfrom(4096)
                data = self._process_dns_message(message)
                if data:
                    self.publish_dns_data(data)
            except Exception as e:
                logger.error(f"Error handling UDP message: {e}")

    def _handle_tcp(self):
        """Handle TCP DNS messages"""
        while self.running:
            try:
                conn, addr = self.tcp_socket.accept()
                length_bytes = conn.recv(2)
                length = int.from_bytes(length_bytes, byteorder='big')
                message = conn.recv(length)
                
                data = self._process_dns_message(message)
                if data:
                    self.publish_dns_data(data)
                    
                conn.close()
            except Exception as e:
                logger.error(f"Error handling TCP message: {e}")

    def publish_dns_data(self, data):
        """Publish DNS data to Kafka"""
        try:
            self.producer.send(self.topic, data)
            logger.debug(f"Published DNS data {data['query_id']}")
        except Exception as e:
            logger.error(f"Error publishing DNS data: {e}")

    def run(self):
        """Start the DNS collector"""
        self.running = True
        self._setup_sockets()
        
        # Start handler threads
        udp_thread = threading.Thread(target=self._handle_udp)
        tcp_thread = threading.Thread(target=self._handle_tcp)
        
        udp_thread.start()
        tcp_thread.start()
        self.cleanup_thread.start()
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down DNS collector...")
            self.running = False
            
            # Cleanup
            self.udp_socket.close()
            self.tcp_socket.close()
            
            udp_thread.join()
            tcp_thread.join()
            self.cleanup_thread.join()

if __name__ == "__main__":
    collector = DNSCollector(
        kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    )
    collector.run()
