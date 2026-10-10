FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
EXPOSE 8100
CMD ["uvicorn", "glazed_backend.adapters.driving.app:create_app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8100"]
