FROM docker.xuanyuan.me/library/python:3.11-slim AS llm-server
LABEL authors="amirdeljouyi"
# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends\
    git \
    unzip \
    curl \
    gnupg2 \
    docker.io \
    && apt-get clean

# Install NVIDIA Container Toolkit
RUN curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
RUN apt-get update \
  && apt-get install -y \
    nvidia-container-toolkit=1.18.0-1 \
    nvidia-container-toolkit-base=1.18.0-1 \
    libnvidia-container-tools=1.18.0-1 \
    libnvidia-container1=1.18.0-1

# Configure NVIDIA Container Runtime
RUN nvidia-ctk runtime configure

# Set up application environment
WORKDIR /app

# Clone the LLM-Server repository
RUN git clone https://github.com/amirdeljouyi/UTGen-LLM-server.git LLM-Server

WORKDIR /app/LLM-Server

RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    python3-dev \
    gcc

## Install Python dependencies in a virtual environment
RUN python -m venv .env && \
    . .env/bin/activate

RUN python -m pip install --no-cache-dir -r requirements.txt
RUN chmod 777 ./run-server.sh
RUN chmod 777 ./run-docker-server.sh

# Expose ports
EXPOSE 8000

### Default command to start the LLM server
# CMD ["bash", "-c", "source .env/bin/activate && ./run-docker-server.sh"]