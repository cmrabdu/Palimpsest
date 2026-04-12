FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System dependencies: poppler (pdf2image), OpenCV libs, LaTeX (xelatex)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    texlive-xetex \
    texlive-latex-extra \
    texlive-lang-french \
    texlive-fonts-recommended \
    texlive-science \
    && rm -rf /var/lib/apt/lists/*

ARG APP_UID=1000
ARG APP_GID=1000

RUN addgroup --gid "${APP_GID}" app \
    && adduser --uid "${APP_UID}" --gid "${APP_GID}" --disabled-password --gecos "" app

COPY requirements.txt /tmp/requirements.txt

# Use headless OpenCV in Docker (no GUI needed), pin numpy<2 for older CPUs without AVX2
RUN sed -e 's/opencv-python/opencv-python-headless/' -e 's/numpy>=1.24.0/numpy>=1.24.0,<2/' /tmp/requirements.txt > /tmp/req.txt \
    && pip install --upgrade pip \
    && pip install -r /tmp/req.txt

COPY src /app/src
COPY web /app/web
COPY pipeline.py server.py config.example.yaml /app/

RUN mkdir -p /app/uploads /app/output /app/.cache \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
