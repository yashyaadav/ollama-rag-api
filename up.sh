#!/bin/bash

# Start the initial setup script
/app/start.sh

# Run any initial processes
python3 /app/ingest.py

# Start the Ollama service in the background and wait for it to be ready
ollama serve &
sleep 5  # Wait for Ollama to initialize

# Run the Flask script in the background
python3 /app/privateGPT.py &

# Keep the script running or execute further commands
tail -f /dev/null
