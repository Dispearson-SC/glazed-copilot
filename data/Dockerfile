# One-shot data build image (ETL -> DuckDB -> forecast). Source and outputs are bind-mounted, see infra/docker-compose.yml.
FROM python:3.12-slim
WORKDIR /work/data
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["sh", "build.sh"]
