FROM alpine:latest
RUN apk update
RUN apk add py-pip
RUN apk add --no-cache python3-dev 
RUN pip install --upgrade pip
WORKDIR /app
COPY . /app
# Default file with MESSAGE field that will be replaced by configMap when deployed to K8
COPY config/config.cfg /tmp/config.cfg
RUN pip --no-cache-dir install -r requirements.txt
CMD ["python3", "hello-world.py"]