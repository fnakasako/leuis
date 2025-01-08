# Data Broker Deployment Guide

This guide explains how to deploy and configure the Data Broker system, including all its components: Kafka, Flink, Elasticsearch (hot storage), Databricks (cold storage), and the monitoring stack.

## Prerequisites

- Docker and Docker Compose v2.x
- Databricks account with workspace access
- At least 16GB RAM for local deployment
- Sufficient disk space (recommended: 100GB+)

## Component Overview

1. **Data Ingestion (Kafka)**
   - Real-time data ingestion
   - Message queuing and buffering
   - Data source connectors

2. **Stream Processing (Flink)**
   - Real-time data processing
   - Data enrichment and transformation
   - Dual write to hot and cold storage

3. **Hot Storage (Elasticsearch)**
   - Recent data storage (10 days)
   - Low-latency queries
   - Real-time search and analytics

4. **Cold Storage (Databricks/Delta Lake)**
   - Historical data storage
   - Batch processing
   - Long-term analytics

5. **Monitoring Stack**
   - Prometheus for metrics collection
   - Grafana for visualization
   - AlertManager for alerting

## Deployment Steps

### 1. Initial Setup

```bash
# Clone the repository
git clone <repository-url>
cd data-broker

# Create necessary directories
mkdir -p data/{kafka,elasticsearch,prometheus}
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```bash
# Kafka
KAFKA_HEAP_OPTS=-Xmx1G -Xms1G

# Elasticsearch
ES_JAVA_OPTS=-Xmx2g -Xmx2g
ELASTIC_PASSWORD=your_secure_password

# Grafana
GF_SECURITY_ADMIN_PASSWORD=your_admin_password
```

### 3. Databricks Setup

1. Log into your Databricks workspace
2. Create a new cluster using the configuration in `storage/cold-store/databricks-config.yml`
3. Configure Unity Catalog:
   ```sql
   CREATE CATALOG IF NOT EXISTS data_broker;
   USE CATALOG data_broker;
   CREATE SCHEMA IF NOT EXISTS public;
   ```
4. Create Delta tables:
   ```sql
   -- Create tables for each data type (arxiv, github, news, dns)
   -- Schema definitions are in databricks-config.yml
   ```

### 4. Start the Services

```bash
# Start all services except Databricks
docker compose up -d

# Verify services are running
docker compose ps
```

### 5. Configure Elasticsearch

```bash
# Initialize Elasticsearch security
docker compose exec elasticsearch elasticsearch-setup-passwords auto

# Create indices and ILM policies
curl -X PUT "localhost:9200/_ilm/policy/hot_store_policy" -H 'Content-Type: application/json' -d @storage/hot-store/elasticsearch-config.yml
```

### 6. Configure Kafka

```bash
# Create topics
docker compose exec kafka-broker kafka-topics --create --bootstrap-server localhost:9092 --topic arxiv_raw --partitions 8 --replication-factor 1
docker compose exec kafka-broker kafka-topics --create --bootstrap-server localhost:9092 --topic github_events --partitions 16 --replication-factor 1
docker compose exec kafka-broker kafka-topics --create --bootstrap-server localhost:9092 --topic news_feed --partitions 8 --replication-factor 1
docker compose exec kafka-broker kafka-topics --create --bootstrap-server localhost:9092 --topic dns_data --partitions 32 --replication-factor 1
```

### 7. Deploy Flink Jobs

```bash
# Submit Flink jobs
docker compose exec flink-jobmanager flink run /opt/flink/jobs/arxiv-processor.jar
docker compose exec flink-jobmanager flink run /opt/flink/jobs/github-processor.jar
docker compose exec flink-jobmanager flink run /opt/flink/jobs/news-processor.jar
docker compose exec flink-jobmanager flink run /opt/flink/jobs/dns-processor.jar
```

### 8. Access Services

- Kafka Manager: http://localhost:9000
- Flink Dashboard: http://localhost:8081
- Elasticsearch: http://localhost:9200
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

## Monitoring and Maintenance

### Health Checks

1. **Kafka**
   ```bash
   # Check topic status
   docker compose exec kafka-broker kafka-topics --describe --bootstrap-server localhost:9092
   ```

2. **Elasticsearch**
   ```bash
   # Check cluster health
   curl -X GET "localhost:9200/_cluster/health?pretty"
   ```

3. **Flink**
   ```bash
   # Check job status
   curl -X GET "localhost:8081/jobs/overview"
   ```

### Backup Procedures

1. **Elasticsearch**
   - Configure snapshots to S3/GCS
   - Regular automated backups

2. **Databricks**
   - Delta Lake provides time travel capabilities
   - Regular table snapshots
   - Backup important notebooks

### Scaling Guidelines

1. **Kafka**
   - Add brokers for horizontal scaling
   - Adjust partition count based on throughput
   - Monitor consumer lag

2. **Elasticsearch**
   - Add nodes to the cluster
   - Adjust shard configuration
   - Optimize index settings

3. **Flink**
   - Increase parallelism
   - Add taskmanagers
   - Tune checkpoint intervals

4. **Databricks**
   - Adjust cluster size
   - Optimize Delta Lake tables
   - Configure auto-scaling

## Troubleshooting

### Common Issues

1. **Kafka Connection Issues**
   - Check ZooKeeper connectivity
   - Verify network settings
   - Ensure correct listener configuration
   - Check broker logs for errors

2. **Elasticsearch Performance**
   - Monitor JVM heap usage
   - Check shard distribution
   - Verify index lifecycle policies
   - Analyze slow query logs

3. **Flink Job Failures**
   - Examine checkpoint statistics
   - Review job manager logs
   - Check for backpressure
   - Verify state backend configuration

4. **Databricks Connectivity**
   - Check network connectivity
   - Verify access tokens
   - Review cluster logs
   - Monitor job execution history

### Logging

All components are configured to send logs to standard output, which can be viewed using:
```bash
docker compose logs [service-name]
```

For persistent logging, configure log forwarding to your preferred logging solution (ELK, Splunk, etc.).

### Metrics Collection

1. **System Metrics**
   - CPU, Memory, Disk usage
   - Network I/O
   - Container statistics

2. **Application Metrics**
   - Kafka: Producer/Consumer rates, lag
   - Elasticsearch: Query rates, indexing rates
   - Flink: Processing time, checkpointing
   - Databricks: Query performance, cluster utilization

## Security Considerations

1. **Network Security**
   - Use internal Docker network
   - Restrict external access
   - Configure SSL/TLS
   - Implement proper firewall rules

2. **Authentication**
   - Secure all service endpoints
   - Use strong passwords
   - Implement RBAC
   - Regular credential rotation

3. **Data Security**
   - Encrypt data at rest
   - Secure data in transit
   - Regular security audits
   - Access logging

## Maintenance Procedures

1. **Regular Updates**
   - Schedule maintenance windows
   - Update components systematically
   - Test updates in staging
   - Maintain backup schedule

2. **Performance Tuning**
   - Regular monitoring review
   - Resource allocation adjustment
   - Query optimization
   - Cache management

3. **Disaster Recovery**
   - Maintain backup strategy
   - Document recovery procedures
   - Regular recovery testing
   - Incident response plan

## Support and Resources

- Documentation: `/docs` directory
- Issue Tracking: GitHub Issues
- Community Support: Slack channel
- Emergency Contact: ops-team@company.com

Remember to regularly check for updates and security patches for all components.
