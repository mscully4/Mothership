FROM public.ecr.aws/docker/library/python:3.12

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
RUN python3 -m pip install awslambdaric

# Copy the python source code over
COPY ./ ./

# Use the python lambda docker runtime environment
ENTRYPOINT [ "python3", "-m", "awslambdaric" ]
CMD ["mothership.main.process_event"]