FROM mcr.microsoft.com/playwright/python:v1.21.0-focal

RUN apt-get update && \
    apt-get install -y \
    g++ \
    make \
    cmake \
    unzip \
    libcurl4-openssl-dev

# Set the working directory in the container
WORKDIR /home/pwuser

# Copies requirements.txt file into the container
COPY requirements.txt ./

# Install dependencies
ENV PIP_ROOT_USER_ACTION=ignore
RUN python3 -m pip install -r requirements.txt

# I don't understand why I need to do this given that I'm using
# image that should already have the drivers, but I get errors if
# I don't, will look into later
RUN python3 -m playwright install

# Copy the python source code over
COPY ./src/ ./

# Use the python lambda docker runtime environment
ENTRYPOINT [ "/usr/bin/python3", "-m", "awslambdaric" ]
CMD ["lambda_function.lambda_handler"]