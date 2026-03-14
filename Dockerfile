# Base image with Python 3.10 (slim for smaller size)
FROM python:3.10-slim

# avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# set working directory early so Docker cache works well
WORKDIR /app

# install system packages we need (ffmpeg for media processing)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxrender1 \
        libxext6 \
    && rm -rf /var/lib/apt/lists/*

# copy requirements first to take advantage of layer caching
COPY requirements.txt .

# install python dependencies
RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "yt-dlp[curl-cffi]" "yt-dlp[browser]"

# copy the rest of the application code
COPY . .

# create a non-root user for better security and give ownership of /app
RUN useradd --create-home appuser \
    && chown -R appuser /app
USER appuser

# ensure Python outputs are logged immediately and no .pyc files are generated
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# entrypoint updates yt-dlp on each start and then runs main.py
ENTRYPOINT ["bash", "-c", "python -m pip install -U yt-dlp && exec python main.py"]

# default command (can be overridden by Cloud Run)
CMD ["python", "main.py"]
