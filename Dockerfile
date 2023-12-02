FROM registry.gitlab.com/findeskp/v1-ec3/fd-app-python:v0.0.1

RUN mkdir -p /usr/src/app

WORKDIR /usr/src/app


COPY . .

ENTRYPOINT [ "./run.sh", "prod" ]