# Data Broker System

A scalable data broker system that ingests, processes, and stores data from multiple sources with both hot and cold storage capabilities. The system follows a Lambda architecture pattern, providing both real-time and batch processing capabilities.

## System Architecture

```
data-broker/
├── src/
│   ├── acquisition/           # Data collectors for various sources
│   │   ├── arxiv/            # ArXiv papers collector
│   │   ├── github/           # GitHub events collector
│   │   ├── news/             # News articles collector
│   │   └── dns/              # DNS query collector
│   └── processing/           # Stream processing jobs
│       ├── src/
│       │   └── main/
│       │       ├── java/
│       │       │   └── com/
│       │       │       └── databroker/
│       │       │           └── processing/
│       │       │               ├── arxiv/
│       │       │               ├── github/
│       │       │               ├── news/
│       │       │               └── dns/
│       │       └── resources/
│       │           └── log4j.properties
│       ├── pom.xml           # Maven build configuration
│       ├── build.sh          # Build script
│       └── README.md         # Processing module documentation
├── ingestion/
│   └── kafka/               # Kafka configuration
├── storage/
│   ├── hot-store/          # Elasticsearch configuration (10-day retention)
│   └── cold-store/         # Databricks/Delta Lake configuration
├── monitoring/             # Monitoring and alerting
│   ├── prometheus-config.yml
│   └── grafana-dashboards.yml
└── docker-compose.yml      # Container orchestration
```

## Components

### 1. Data Acquisition

Python-based collectors for different data sources:
- **ArXiv Collector**: Fetches academic papers from ArXiv API
- **GitHub Collector**: Captures GitHub repository events
- **News Collector**: Aggregates news articles from various sources
- **DNS Collector**: Captures and processes DNS queries

### 2. Data Ingestion

Apache Kafka serves as the real-time ingestion layer:
- Multiple topics for different data types
- Configurable retention and partitioning
- High throughput message handling

### 3. Stream Processing

Apache Flink jobs for real-time data processing:
- Processes data from Kafka topics
- Enriches and transforms data
- Writes to both hot and cold storage
- Exactly-once processing guarantees

### 4. Storage

#### Hot Storage (Elasticsearch)
- Recent data (10 days retention)
- Low-latency queries
- Automatic index lifecycle management
- Real-time search capabilities

#### Cold Storage (Databricks/Delta Lake)
- Historical data storage
- Cost-effective long-term retention
- Support for large-scale analytics
- Integration with ML pipelines

### 5. Monitoring

Comprehensive monitoring stack:
- Prometheus for metrics collection
- Grafana for visualization
- AlertManager for alerting
- Custom dashboards for each component

## Building and Running

### Prerequisites

- Docker and Docker Compose v2.x
- Java 11 or later
- Python 3.8 or later
- Maven 3.6 or later
- Flink 1.17 or later

### Building the System

1. Build the processing jobs:
```bash
cd src/processing
./build.sh
```

2. Build the collectors:
```bash
cd src/acquisition
pip install -r requirements.txt
```

3. Start the infrastructure:
```bash
docker-compose up -d
```

### Running the Components

1. Start the collectors:
```bash
# In separate terminals
python src/acquisition/arxiv/arxiv_collector.py
python src/acquisition/github/github_collector.py
python src/acquisition/news/news_collector.py
python src/acquisition/dns/dns_collector.py
```

2. Start the processing jobs:
```bash
cd src/processing
./run-arxiv-processor.sh
./run-github-processor.sh
./run-news-processor.sh
./run-dns-processor.sh
```

### Accessing Services

- Kafka Manager: http://localhost:9000
- Elasticsearch: http://localhost:9200
- Kibana: http://localhost:5601
- Flink Dashboard: http://localhost:8081
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

## Configuration

Environment variables for customization:
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka broker addresses
- `ELASTICSEARCH_HOSTS`: Elasticsearch cluster addresses
- `DATABRICKS_HOST`: Databricks SQL endpoint
- `DATABRICKS_TOKEN`: Authentication token

See individual component README files for detailed configuration options.

## Monitoring and Maintenance

1. Monitor system health:
   - Check Grafana dashboards
   - Review Elasticsearch indices
   - Monitor Kafka consumer lag
   - Check Flink job status

2. Regular maintenance:
   - Verify backup procedures
   - Monitor disk usage
   - Check log rotation
   - Update security patches

## Development

1. Adding new data sources:
   - Create collector in `src/acquisition`
   - Add Kafka topic configuration
   - Implement Flink processor
   - Update monitoring dashboards

2. Modifying processors:
   - Edit source in `src/processing/src/main/java`
   - Run tests: `cd src/processing && mvn test`
   - Rebuild: `./build.sh`

## Documentation

- [Deployment Guide](DEPLOYMENT.md)
- [Processing Jobs](src/processing/README.md)
- [Monitoring Setup](monitoring/README.md)

## Support

For issues and support:
1. Check the documentation
2. Review the logs
3. Check Grafana dashboards
4. Contact the development team

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.
