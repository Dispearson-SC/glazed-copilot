# Agent-Core (Glazed vertical) image. Build context: ../Agent-Core/Core (see infra/docker-compose.yml).
FROM python:3.12-slim
WORKDIR /app/Core

# Layer 1 (cached): third-party dependencies only, read from pyproject.toml.
COPY pyproject.toml ./
RUN python - <<'PY' > /tmp/requirements.txt
import tomllib
print("\n".join(tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]))
PY
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Layer 2: the code. Editable so the package finds profiles/, policy/ and skills/ next to src/.
COPY src ./src
COPY profiles ./profiles
COPY policy ./policy
COPY skills ./skills
RUN pip install --no-cache-dir --no-deps -e .

ENV AGENT_CORE_HTTP_HOST=0.0.0.0 AGENT_CORE_HTTP_PORT=8000
EXPOSE 8000
CMD ["python", "-m", "agent_core", "serve"]
