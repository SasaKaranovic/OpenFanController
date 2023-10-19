# Download base image ubuntu 22.04
FROM ubuntu:22.04

# LABEL about the custom image
LABEL maintainer="sasa@karanovic.ca"
LABEL version="0.1"
LABEL description="OpenFan Controller Web GUI and Server docker image"

# Disable Prompt During Packages Installation
ARG DEBIAN_FRONTEND=noninteractive

# Update Ubuntu Software repository
RUN apt update

# Install nginx, php-fpm and supervisord from ubuntu repository
RUN apt install -y python3 python3-pip
RUN rm -rf /var/lib/apt/lists/*
RUN apt clean

# Copy all source files
ADD Software/Python /mnt/OpenFan
ADD Software/start.sh /mnt/OpenFan

# Install python modules
RUN pip3 install -r /mnt/OpenFan/requirements.txt

RUN ["chmod", "+x", "/mnt/OpenFan/start.sh"]


# Expose Port for the Application
EXPOSE 3000

# Run entrypoint
ENTRYPOINT ["/mnt/OpenFan/start.sh"]

