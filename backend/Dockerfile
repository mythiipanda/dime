FROM python:3.11-slim
WORKDIR /srv
ARG DIME_REVISION=unknown
ENV DIME_REVISION=$DIME_REVISION
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY v2 ./v2
COPY scripts/build_team_four_factors.py scripts/generate_asset_manifest.py ./scripts/
COPY data ./data
# The canonical warehouse is immutable through store.connect(), so build the
# derived table into a scratch copy (via DIME_WAREHOUSE) and bake the result
# into the image's warehouse file.
RUN cp data/warehouse.duckdb data/_build.duckdb && \
    DIME_WAREHOUSE=/srv/data/_build.duckdb python scripts/build_team_four_factors.py && \
    mv data/_build.duckdb data/warehouse.duckdb
# Promotion binding: freeze the expected code/data/prompt manifest so startup
# fails fast if the baked assets don't match what was promoted.
RUN python scripts/generate_asset_manifest.py /srv/manifest/expected_asset_manifest.json
ENV DIME_EXPECTED_ASSET_MANIFEST=/srv/manifest/expected_asset_manifest.json
ENV PORT=8000
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
