#!/bin/bash

# Build script for Data Broker Processing Jobs

set -e  # Exit on error

# Default values
SKIP_TESTS=false
CLEAN_BUILD=false
PACKAGE_ONLY=false

# Function to display usage information
usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -h, --help        Show this help message"
    echo "  -c, --clean       Perform a clean build"
    echo "  -s, --skip-tests  Skip running tests"
    echo "  -p, --package     Package only (skip tests)"
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            ;;
        -c|--clean)
            CLEAN_BUILD=true
            shift
            ;;
        -s|--skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        -p|--package)
            PACKAGE_ONLY=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Ensure we're in the right directory
if [[ ! -f "pom.xml" ]]; then
    echo "Error: pom.xml not found. Please run this script from the processing directory."
    exit 1
fi

# Create necessary directories
mkdir -p target/lib
mkdir -p logs

echo "Building Data Broker Processing Jobs..."

# Clean if requested
if [[ "$CLEAN_BUILD" == "true" ]]; then
    echo "Performing clean build..."
    mvn clean
fi

# Build command construction
BUILD_CMD="mvn"

if [[ "$SKIP_TESTS" == "true" ]] || [[ "$PACKAGE_ONLY" == "true" ]]; then
    BUILD_CMD="$BUILD_CMD -DskipTests"
fi

if [[ "$PACKAGE_ONLY" == "true" ]]; then
    BUILD_CMD="$BUILD_CMD package"
else
    BUILD_CMD="$BUILD_CMD install"
fi

# Execute build
echo "Executing: $BUILD_CMD"
$BUILD_CMD

# Check if build was successful
if [[ $? -eq 0 ]]; then
    echo "Build successful!"
    echo "Generated artifacts:"
    ls -l target/*.jar
    
    echo -e "\nTo run the processors:"
    echo "1. ArXiv Processor:"
    echo "   flink run -c com.databroker.processing.arxiv.ArxivProcessor target/processing-1.0-SNAPSHOT.jar"
    echo "2. GitHub Processor:"
    echo "   flink run -c com.databroker.processing.github.GitHubProcessor target/processing-1.0-SNAPSHOT.jar"
    echo "3. News Processor:"
    echo "   flink run -c com.databroker.processing.news.NewsProcessor target/processing-1.0-SNAPSHOT.jar"
    echo "4. DNS Processor:"
    echo "   flink run -c com.databroker.processing.dns.DNSProcessor target/processing-1.0-SNAPSHOT.jar"
else
    echo "Build failed!"
    exit 1
fi

# Create run scripts for each processor
cat > run-arxiv-processor.sh << 'EOF'
#!/bin/bash
flink run -c com.databroker.processing.arxiv.ArxivProcessor target/processing-1.0-SNAPSHOT.jar
EOF

cat > run-github-processor.sh << 'EOF'
#!/bin/bash
flink run -c com.databroker.processing.github.GitHubProcessor target/processing-1.0-SNAPSHOT.jar
EOF

cat > run-news-processor.sh << 'EOF'
#!/bin/bash
flink run -c com.databroker.processing.news.NewsProcessor target/processing-1.0-SNAPSHOT.jar
EOF

cat > run-dns-processor.sh << 'EOF'
#!/bin/bash
flink run -c com.databroker.processing.dns.DNSProcessor target/processing-1.0-SNAPSHOT.jar
EOF

# Make run scripts executable
chmod +x run-*.sh

echo -e "\nCreated run scripts for each processor:"
ls -l run-*.sh
