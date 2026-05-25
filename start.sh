#!/bin/bash

# Start the Ollama service in the foreground temporarily
ollama serve &

# Get the PID of the service to kill it later
SERVICE_PID=$!

# Allow some time for the service to initialize
sleep 10

# Run the command to download the model
ollama pull llama3:latest

# Kill the service after the download completes
kill $SERVICE_PID
wait $SERVICE_PID  # Ensures the service has stopped before proceeding

# Optional: Verify that the model is downloaded and in place
# e.g., ls -l /path/to/model or similar command
