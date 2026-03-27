FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y libpq-dev gcc netcat-openbsd && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and wait script
COPY . /app/
RUN chmod +x /app/entrypoint.sh

# Expose Streamlit default port
EXPOSE 8501

ENTRYPOINT ["/app/entrypoint.sh"]
