FROM python:3.11-slim
WORKDIR /srv
ARG DIME_REVISION=unknown
ENV DIME_REVISION=$DIME_REVISION
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY v2 ./v2
COPY scripts/build_team_four_factors.py ./scripts/build_team_four_factors.py
COPY data ./data
RUN python scripts/build_team_four_factors.py
ENV PORT=8000
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
