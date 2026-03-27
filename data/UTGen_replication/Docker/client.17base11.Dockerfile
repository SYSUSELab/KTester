# Base image
# FROM eclipse-temurin:11-jdk AS utgen-client
FROM docker.xuanyuan.me/library/eclipse-temurin:17-jdk AS utgen-client
LABEL authors="amirdeljouyi"

# Install system dependencies
RUN apt-get update && apt-get install -y \
  unzip \
  zip \
  git \
  && apt-get clean

# Install SDKMAN for additional Java management if needed
RUN curl -s "https://get.sdkman.io" | bash && \
    bash -c "source $HOME/.sdkman/bin/sdkman-init.sh && sdk version"

WORKDIR /app

RUN git clone https://github.com/amirdeljouyi/UTGen-replication-package-dataset.git dataset

WORKDIR /app/dataset

# Ensure run-utestgen.sh is executable
RUN chmod +x ./run-utestgen.docker.sh
RUN chmod +x ./run-experiment.sh

# CMD ["bash", "-c", "./run-experiment.sh"]
CMD ["bash", "-c", "tail -f /dev/null"]