# Use an official Ubuntu 22.04 LTS runtime as a parent image
FROM ubuntu:22.04

# Set noninteractive mode and default timezone
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Set the working directory in the container
WORKDIR /usr/src/app

# Install required packages and dependencies
RUN apt-get update && \
    apt-get install -y software-properties-common wget python3-pip libpq-dev && \
    add-apt-repository ppa:lightningnetwork/ppa && \
    apt-get update && \
    apt-get install -y nano && \
    apt-get install -y lightningd && \
    mkdir -p /root/.lightning/plugins && \
    cd /root/.lightning/plugins && \
    wget https://github.com/nbd-wtf/trustedcoin/releases/download/v0.7.0/trustedcoin-v0.7.0-linux-amd64.tar.gz && \
    tar -xvf trustedcoin-v0.7.0-linux-amd64.tar.gz && \
    # Install electrum libraries
    apt-get install -y python3-pyqt5 libsecp256k1-dev python3-cryptography && \
    wget https://download.electrum.org/4.5.5/Electrum-4.5.5.tar.gz && \
    # Install with PIP
    apt-get install -y python3-setuptools && \
    python3 -m pip install Electrum-4.5.5.tar.gz && \
    # Add export PATH="$PATH:$HOME/.local/bin" to path
    export PATH="$PATH:$HOME/.local/bin" && \
    cd /usr/src/app \
    
# Copy testnet-config as config file inside ~/.lightning/
COPY testnet-config /root/.lightning/config
# COPY config /root/.lightning/config


# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Copy the entrypoint script into the container
COPY entrypoint.sh /usr/src/app/entrypoint.sh

# Ensure the entrypoint script is executable
RUN chmod +x /usr/src/app/entrypoint.sh

EXPOSE 9735

# Install required Python packages
RUN pip3 install --no-cache-dir pyln-client psycopg2-binary requests

# Use the entrypoint script as the entry point for the container
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]