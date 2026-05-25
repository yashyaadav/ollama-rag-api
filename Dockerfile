# Use arm64v8/Ubuntu:latest as the base image
FROM arm64v8/ubuntu:latest

# Prevent apt from displaying prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies required for pyenv and Python compilation
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    llvm \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev

# Install pyenv
RUN curl https://pyenv.run | bash

# Set environment variables for pyenv and ensure it is initialized correctly in this layer and subsequent layers
ENV PYENV_ROOT /root/.pyenv
ENV PATH $PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH

# Install Python 3.11.9 using pyenv and set it as the default Python version
RUN pyenv install 3.11.9 && \
    pyenv global 3.11.9

# Update pip and install virtualenv
RUN pip install --upgrade pip && \
    pip install virtualenv

# Create a virtual environment named 'venv'
RUN virtualenv /app/venv

# Set the virtual environment as the default Python environment for all subsequent commands
ENV PATH /app/venv/bin:$PATH

# Install Ollama using the provided install script
RUN curl -fsSL https://ollama.com/install.sh | sh

# Set the working directory in the container
WORKDIR /app

# Copy the entire current directory contents into the container's working directory
COPY . /app

# Install Python dependencies using pip in the virtual environment
RUN /app/venv/bin/pip install -r /app/requirements.txt

# Specifically, copy custom scripts and the start script into the container
COPY ./custom_scripts /app/custom_scripts
COPY start.sh /app/start.sh

# Make sure the start script is executable
RUN chmod +x /app/start.sh
RUN /app/start.sh

RUN chmod +x /app/up.sh /app/privateGPT.py

# Expose port 11434 for Ollama service and 5000 for the Flask application
EXPOSE 11434 5000

# Set command for container start
CMD ["/app/up.sh"]
