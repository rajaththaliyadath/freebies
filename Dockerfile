FROM mcr.microsoft.com/playwright:v1.40.0-jammy

WORKDIR /app

# Install Python + pip (Playwright base image is Node-focused).
RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 python3-pip \
  && rm -rf /var/lib/apt/lists/*

# Keep Python output unbuffered in container logs.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "main.py"]
