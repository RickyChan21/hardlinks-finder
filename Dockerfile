# Use the latest stable, official Python runtime as a parent image
FROM python:3.14-slim-bookworm

# Set environment variables
# Prevents Python from writing pyc files to disk
ENV PYTHONDONTWRITEBYTECODE=1
# Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

# Create a non-privileged user to run the app
RUN groupadd -g 1000 python && \
    useradd -r -u 1000 -g python python

# Install gosu and passwd utilities for PUID/PGID support
RUN apt-get update && apt-get install -y --no-install-recommends gosu passwd && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Install dependencies first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Ensure entrypoint is executable
RUN chmod +x entrypoint.sh

# Expose the port the app runs on
EXPOSE 5000

# Use the entrypoint script to handle PUID/PGID
ENTRYPOINT ["./entrypoint.sh"]

# Run gunicorn through the entrypoint
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:5000", "app:app"]
