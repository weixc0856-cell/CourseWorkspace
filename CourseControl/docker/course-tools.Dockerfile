FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# The base image already ships bash, coreutils, awk, sed, grep, python3 and uv.
# Keep the E1 image offline-buildable: no apt-get, no network at build time.
RUN useradd --create-home --uid 1000 course

ENV HOME=/home/course
USER course
WORKDIR /work
