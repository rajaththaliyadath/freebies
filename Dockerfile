FROM mcr.microsoft.com/playwright:v1.40.0-jammy

WORKDIR /app

# Keep Python output unbuffered in container logs.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "main.py"]
