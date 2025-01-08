# Data Broker Processing Jobs

This module contains Apache Flink stream processing jobs for the data broker system. The jobs process data from various sources and write to both hot (Elasticsearch) and cold (Delta Lake) storage.

## Project Structure

```
processing/
├── src/
│   ├── main/
│   │   ├── java/
│   │   │   └── com/
│   │   │       └── databroker/
│   │   │           └── processing/
│   │   │               ├── arxiv/
│   │   │               ├── github/
│   │   │               ├── news/
│   │   │               └── dns/
│   │   └── resources/
│   │       └── log4j.properties
│   └── test/
│       └── java/
│           └── com/
│               └── databroker/
│                   └── processing/
└── pom.xml
```

## Building

To build all processing jobs:

```bash
mvn clean package
```

This will create JAR files for each processor in the `target` directory.

## Deployment

The generated JAR files can be submitted to the Flink cluster using:

```bash
flink run -c com.databroker.processing.arxiv.ArxivProcessor target/processing-1.0-SNAPSHOT.jar
flink run -c com.databroker.processing.github.GitHubProcessor target/processing-1.0-SNAPSHOT.jar
flink run -c com.databroker.processing.news.NewsProcessor target/processing-1.0-SNAPSHOT.jar
flink run -c com.databroker.processing.dns.DNSProcessor target/processing-1.0-SNAPSHOT.jar
```

## Configuration

Each processor can be configured using environment variables:

### Common Settings
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka broker addresses (default: kafka-broker:9092)
- `ELASTICSEARCH_HOSTS`: Elasticsearch cluster addresses (default: elasticsearch:9200)
- `DATABRICKS_HOST`: Databricks SQL endpoint (default: databricks-cluster:10000)
- `DATABRICKS_TOKEN`: Authentication token for Databricks

### Processor-Specific Settings
- ArXiv Processor:
  - `ARXIV_KAFKA_TOPIC`: Input topic name (default: arxiv_raw)
  - `ARXIV_ES_INDEX`: Elasticsearch index name (default: arxiv_recent)
  
- GitHub Processor:
  - `GITHUB_KAFKA_TOPIC`: Input topic name (default: github_events)
  - `GITHUB_ES_INDEX`: Elasticsearch index name (default: github_recent)
  
- News Processor:
  - `NEWS_KAFKA_TOPIC`: Input topic name (default: news_feed)
  - `NEWS_ES_INDEX`: Elasticsearch index name (default: news_recent)
  
- DNS Processor:
  - `DNS_KAFKA_TOPIC`: Input topic name (default: dns_data)
  - `DNS_ES_INDEX`: Elasticsearch index name (default: dns_recent)

## Monitoring

The jobs expose metrics through Flink's metrics system, which can be collected by Prometheus and visualized in Grafana.

Key metrics include:
- Records processed per second
- Processing latency
- Checkpoint duration and size
- Kafka consumer lag
- Elasticsearch bulk request success/failure rates

## Development

To add a new processor:

1. Create a new package under `com.databroker.processing`
2. Implement the processor following the same pattern as existing ones
3. Add configuration to `pom.xml` if new dependencies are needed
4. Add deployment instructions to this README
5. Update monitoring dashboards to include the new processor

## Testing

Run unit tests:
```bash
mvn test
```

Run integration tests:
```bash
mvn verify -P integration-tests
