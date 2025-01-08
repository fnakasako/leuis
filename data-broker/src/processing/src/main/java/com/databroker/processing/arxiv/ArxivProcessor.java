package com.databroker.processing.arxiv;

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

import java.util.Properties;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class ArxivProcessor {
    public static void main(String[] args) throws Exception {
        // Set up the streaming execution environment
        final StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        // Configure Kafka consumer
        Properties kafkaProps = new Properties();
        kafkaProps.setProperty("bootstrap.servers", "kafka-broker:9092");
        kafkaProps.setProperty("group.id", "arxiv-processor");

        // Create Kafka consumer for arxiv_raw topic
        FlinkKafkaConsumer<ObjectNode> kafkaConsumer = new FlinkKafkaConsumer<>(
            "arxiv_raw",
            new JsonNodeDeserializationSchema(),
            kafkaProps
        );
        kafkaConsumer.setStartFromLatest();

        // Create the data stream from Kafka
        DataStream<ObjectNode> arxivStream = env.addSource(kafkaConsumer);

        // Process and enrich the stream
        DataStream<ObjectNode> enrichedStream = arxivStream
            .map(new ArxivEnrichmentFunction())
            .name("enrich-arxiv-data");

        // Configure Elasticsearch sink for hot storage
        List<HttpHost> esHttpHosts = new ArrayList<>();
        esHttpHosts.add(new HttpHost("elasticsearch", 9200, "http"));

        ElasticsearchSink.Builder<ObjectNode> esSinkBuilder = new ElasticsearchSink.Builder<>(
            esHttpHosts,
            (element, ctx, indexer) -> {
                Map<String, Object> json = new HashMap<>();
                json.put("id", element.get("id").asText());
                json.put("title", element.get("title").asText());
                json.put("abstract", element.get("abstract").asText());
                json.put("authors", element.get("authors").asText());
                json.put("category", element.get("category").asText());
                json.put("timestamp", element.get("timestamp").asText());
                json.put("year", element.get("year").asInt());
                json.put("month", element.get("month").asInt());
                json.put("day", element.get("day").asInt());

                IndexRequest request = Requests.indexRequest()
                    .index("arxiv_recent")
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
        String deltaTablePath = "/data/cold-store/arxiv";
        
        // Using JDBC sink as an example (in practice, you'd use the Delta Lake connector)
        enrichedStream.addSink(
            JdbcSink.sink(
                "INSERT INTO arxiv_historical (id, title, abstract, authors, category, timestamp, year, month, day) " +
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (statement, element) -> {
                    statement.setString(1, element.get("id").asText());
                    statement.setString(2, element.get("title").asText());
                    statement.setString(3, element.get("abstract").asText());
                    statement.setString(4, element.get("authors").asText());
                    statement.setString(5, element.get("category").asText());
                    statement.setString(6, element.get("timestamp").asText());
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
                    .withUrl("jdbc:spark://databricks-cluster:10000/default")
                    .withDriverName("com.databricks.client.jdbc.Driver")
                    .withUsername("token")
                    .withPassword(System.getenv("DATABRICKS_TOKEN"))
                    .build()
            )
        ).name("delta-lake-sink");

        // Execute the Flink job
        env.execute("ArXiv Processing Pipeline");
    }
}

class ArxivEnrichmentFunction extends RichMapFunction<ObjectNode, ObjectNode> {
    private static final long serialVersionUID = 1L;

    @Override
    public ObjectNode map(ObjectNode paper) throws Exception {
        // Add any additional enrichment logic here
        // For example:
        // - Extract topics from abstract
        // - Normalize author names
        // - Add metadata
        return paper;
    }
}

class RetryRejectedExecutionFailureHandler implements ElasticsearchSink.FailureHandler {
    private static final long serialVersionUID = 1L;

    @Override
    public void onFailure(ActionRequest action, Throwable failure, int restStatusCode, RequestIndexer indexer) throws Throwable {
        if (ExceptionUtils.indexOfType(failure, EsRejectedExecutionException.class) != -1 ||
            ExceptionUtils.indexOfType(failure, NoNodeAvailableException.class) != -1) {
            indexer.add(action);
        } else {
            throw failure;
        }
    }
}
