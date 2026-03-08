FROM python:3.10-slim

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -U pip && pip install -U -r requirements.txt
RUN pip install -U "yt-dlp[curl-cffi]"
COPY . /app
WORKDIR /app

RUN pip install -U "yt-dlp[browser]"


# Auto-update yt-dlp at container start
ENTRYPOINT ["bash", "-c", "python -m pip install -U yt-dlp && python main.py"]