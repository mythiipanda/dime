FROM python:3.11-slim
WORKDIR /srv
ARG DIME_REVISION=unknown
ENV DIME_REVISION=$DIME_REVISION
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY v2 ./v2
COPY shared ./shared
COPY entrypoint.py ./entrypoint.py
COPY scripts/build_team_four_factors.py scripts/generate_asset_manifest.py scripts/seed_team_ratings.py ./scripts/
COPY data ./data
RUN cp data/warehouse.duckdb data/_build.duckdb && \
    DIME_WAREHOUSE=/srv/data/_build.duckdb python scripts/build_team_four_factors.py && \
    DIME_WAREHOUSE=/srv/data/_build.duckdb python scripts/seed_team_ratings.py 2024-25 && \
    mv data/_build.duckdb data/warehouse.duckdb
RUN python scripts/generate_asset_manifest.py /srv/manifest/expected_asset_manifest.json
ENV DIME_EXPECTED_ASSET_MANIFEST=/srv/manifest/expected_asset_manifest.json
ENV PORT=8000
EXPOSE 8000
CMD ["uvicorn", "entrypoint:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
