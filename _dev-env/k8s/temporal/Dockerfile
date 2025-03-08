FROM debian:12-slim

EXPOSE 7233
EXPOSE 8233

ARG TARGETARCH
ENV ARCH=$TARGETARCH

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC


RUN echo $ARCH > arch.txt
RUN apt-get update && apt-get install -y curl

RUN mkdir -p /temporal /srv/temporal
WORKDIR /temporal

ENV TEMPORAL_CLI_VERSION=latest
RUN curl --output temporal-cli.tar.gz "https://temporal.download/cli/archive/$TEMPORAL_CLI_VERSION?platform=linux&arch=$ARCH"

RUN tar -xzf temporal-cli.tar.gz

ENV TEMPORAL_IP_BIND=0.0.0.0
ENV TEMPORAL_LOG_FORMAT=json
ENV TEMPORAL_LOG_LEVEL=info
ENV TEMPORAL_NAMESPACE=mynamespace
CMD "./temporal" "server" "start-dev"               \
    "--ip" "${TEMPORAL_IP_BIND}"                \
    "--log-format" "${TEMPORAL_LOG_FORMAT}"         \
    "--log-level" "${TEMPORAL_LOG_LEVEL}"           \
    "--namespace" "${TEMPORAL_NAMESPACE}"           \
    "--db-filename" "/srv/temporal/temporal.db"