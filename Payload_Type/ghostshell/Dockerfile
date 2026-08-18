FROM python:3.11-slim

# Mythic payload translator container. Mythic builds this image, then runs it
# to compile payloads on demand. The mythic_container SDK is the only runtime
# dependency (ADR-003: the agent side is stdlib-only; this container can use pip).
RUN pip3 install --no-cache-dir mythic-container

WORKDIR /Mythic
COPY . /Mythic/

# Mythic invokes `python3 main.py` to start the translator service.
CMD ["python3", "main.py"]
