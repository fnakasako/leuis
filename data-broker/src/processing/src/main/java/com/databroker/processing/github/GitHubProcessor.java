package com.databroker.processing.github;

import org.apache.flink.api.common.functions.RichMapFunction;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.connectors.kafka.FlinkKafkaConsumer;
import org.apache.flink.formats.json.JsonNodeDeserializationSchema;
import org.apache.flink.streaming.connectors.elasticsearch7.ElasticsearchSink;
import org.apache.flink.streaming.connectors.elasticsearch7.RequestIndexer;
import org.apache.flink.connector.jdbc.JdbcConnectionOptions;
import org.apache.flink.connector.jdbc.JdbcExecutionOptions;
import org.apache.flink.connector.jdbc.JdbcSink;

import org.apache.http.HttpHost;
import org.elasticsearch.action.ActionRequest;
import org.elasticsearch.action.index.IndexRequest;
import org.elasticsearch.client.Requests;
import org.elasticsearch.client.transport.NoNodeAvailableException;
import org.elasticsearch.common.util.concurrent.EsRejectedExecutionException;

import com.fasterxml.jackson.databind.node.ObjectNode;
import org.apache.commons.lang3.exception.ExceptionUtils;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Properties;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class GitHubProcessor {
    private static final Logger LOG = LoggerFactory.getLogger(GitHubProcessor.class);

    public static void main(String[] args) throws Exception {
        // Set up the streaming execution environment
        final StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        // Configure Kafka consumer
        Properties kafkaProps = new Properties();
        kafkaProps.setProperty("bootstrap.servers", 
            System.getenv().getOrDefault("KAFKA_BOOTSTRAP_SERVERS", "kafka-broker:9092"));
        kafkaProps.setProperty("group.id", "github-processor");

        // Create Kafka consumer for github_events topic
        FlinkKafkaConsumer<ObjectNode> kafkaConsumer = new FlinkKafkaConsumer<>(
            System.getenv().getOrDefault("GITHUB_KAFKA_TOPIC", "github_events"),
            new JsonNodeDeserializationSchema(),
            kafkaProps
        );
        kafkaConsumer.setStartFromLatest();

        // Create the data stream from Kafka
        DataStream<ObjectNode> githubStream = env.addSource(kafkaConsumer);

        // Process and enrich the stream
        DataStream<ObjectNode> enrichedStream = githubStream
            .map(new GitHubEnrichmentFunction())
            .name("enrich-github-data");

        // Configure Elasticsearch sink for hot storage
        List<HttpHost> esHttpHosts = new ArrayList<>();
        String[] esHosts = System.getenv()
            .getOrDefault("ELASTICSEARCH_HOSTS", "elasticsearch:9200")
            .split(",");
        
        for (String host : esHosts) {
            String[] parts = host.split(":");
            esHttpHosts.add(new HttpHost(parts[0], Integer.parseInt(parts[1]), "http"));
        }

        ElasticsearchSink.Builder<ObjectNode> esSinkBuilder = new ElasticsearchSink.Builder<>(
            esHttpHosts,
            (element, ctx, indexer) -> {
                Map<String, Object> json = new HashMap<>();
                json.put("event_id", element.get("event_id").asText());
                json.put("event_type", element.get("event_type").asText());
                json.put("repository", element.get("repository").asText());
                json.put("user", element.get("user").asText());
                json.put("timestamp", element.get("timestamp").asText());
                json.put("payload", element.get("payload"));
                json.put("year", element.get("year").asInt());
                json.put("month", element.get("month").asInt());
                json.put("day", element.get("day").asInt());

                IndexRequest request = Requests.indexRequest()
                    .index(System.getenv().getOrDefault("GITHUB_ES_INDEX", "github_recent"))
                    .source(json);
                indexer.add(request);
            }
        );

        // Configure the Elasticsearch sink
        esSinkBuilder.setBulkFlushMaxActions(1000);
        esSinkBuilder.setBulkFlushMaxSizeMb(5);
        esSinkBuilder.setBulkFlushInterval(30000);
        esSinkBuilder.setFailureHandler(new RetryRejectedExecutionFailureHandler());

        // Add Elasticsearch sink to the enriched stream
        enrichedStream.addSink(esSinkBuilder.build())
            .name("elasticsearch-sink");

        // Configure Delta Lake sink for cold storage
        String deltaTablePath = "/data/cold-store/github";
        
        // Using JDBC sink as an example (in practice, you'd use the Delta Lake connector)
        enrichedStream.addSink(
            JdbcSink.sink(
                "INSERT INTO github_historical (event_id, event_type, repository, user, timestamp, payload, year, month, day) " +
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (statement, element) -> {
                    statement.setString(1, element.get("event_id").asText());
                    statement.setString(2, element.get("event_type").asText());
                    statement.setString(3, element.get("repository").asText());
                    statement.setString(4, element.get("user").asText());
                    statement.setString(5, element.get("timestamp").asText());
                    statement.setString(6, element.get("payload").toString());
                    statement.setInt(7, element.get("year").asInt());
                    statement.setInt(8, element.get("month").asInt());
                    statement.setInt(9, element.get("day").asInt());
                },
                JdbcExecutionOptions.builder()
                    .withBatchSize(1000)
                    .withBatchIntervalMs(200)
                    .withMaxRetries(3)
                    .build(),
                new JdbcConnectionOptions.JdbcConnectionOptionsBuilder()
                    .withUrl(System.getenv().getOrDefault("DATABRICKS_HOST", 
                        "jdbc:spark://databricks-cluster:10000/default"))
                    .withDriverName("com.databricks.client.jdbc.Driver")
                    .withUsername("token")
                    .withPassword(System.getenv("DATABRICKS_TOKEN"))
                    .build()
            )
        ).name("delta-lake-sink");

        // Execute the Flink job
        env.execute("GitHub Events Processing Pipeline");
    }
}

class GitHubEnrichmentFunction extends RichMapFunction<ObjectNode, ObjectNode> {
    private static final long serialVersionUID = 1L;
    private static final Logger LOG = LoggerFactory.getLogger(GitHubEnrichmentFunction.class);

    @Override
    public ObjectNode map(ObjectNode event) throws Exception {
        try {
            // Add any additional enrichment logic here
            // For example:
            // - Categorize events
            // - Add repository metadata
            // - Normalize user information
            return event;
        } catch (Exception e) {
            LOG.error("Error enriching GitHub event: {}", e.getMessage());
            throw e;
        }
    }
}

class RetryRejectedExecutionFailureHandler implements ElasticsearchSink.FailureHandler {
    private static final long serialVersionUID = 1L;
    private static final Logger LOG = LoggerFactory.getLogger(RetryRejectedExecutionFailureHandler.class);

    @Override
    public void onFailure(ActionRequest action, Throwable failure, int restStatusCode, RequestIndexer indexer) throws Throwable {
        if (ExceptionUtils.indexOfType(failure, EsRejectedExecutionException.class) != -1 ||
            ExceptionUtils.indexOfType(failure, NoNodeAvailableException.class) != -1) {
            LOG.warn("Elasticsearch request rejected, retrying: {}", failure.getMessage());
            indexer.add(action);
        } else {
            LOG.error("Elasticsearch request failed: {}", failure.getMessage());
            throw failure;
        }
    }
}
