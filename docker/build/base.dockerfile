FROM  ubuntu:20.04

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai

SHELL ["/bin/bash", "-c"]

RUN apt-get clean && \
    apt-get autoclean
COPY apt/sources.list /etc/apt/

RUN apt-get update -o Acquire::Retries=3 && \
    apt-get install -y \
    libssl-dev gcc g++ make gdb \
    curl \
    lsof \
    build-essential \
    libboost-all-dev \
    vim \
    libzmq3-dev \
    libgoogle-glog-dev \
    cmake \
    libbsd-dev \
    iproute2 \
    python3 \
    python3-pip \
    alsa-utils libasound2-dev && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir \
    fastapi==0.110.3 \
    fastapi-cli==0.0.4 \
    python-multipart==0.0.9 \
    "uvicorn[standard]==0.29.0"

COPY install/eventpp /tmp/install/eventpp
RUN /tmp/install/eventpp/install_eventpp.sh 

COPY install/simdjson /tmp/install/simdjson
RUN /tmp/install/simdjson/install_simdjson.sh 


