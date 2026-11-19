# Scopewatch hosted demo: the API and the built web app in one container, behind the judges' password.
#
# Build inputs (see docs/DEPLOY.md):
#   web/dist        npm run build in web/
#   cache/demo/v2   python -m scripts.bundle_demo   (git-ignored: licensed data, private image only)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SCOPEWATCH_CACHE=/app/cache \
    SCOPEWATCH_REQUIRE_AUTH=1 \
    STL_DATA_DIR=/srv/no-raw-data

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine engine
COPY api api
COPY pipeline pipeline
COPY config config
COPY web/dist web/dist
COPY cache/demo/v2 cache/v2

# no root at runtime; VOD links the judges save go to cache/v2/user.sqlite
RUN useradd --create-home scopewatch && chown -R scopewatch /app/cache
USER scopewatch

EXPOSE 8080
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8080"]
