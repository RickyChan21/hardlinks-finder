# Use the latest stable, official Python runtime as a parent image
FROM python:3.14-slim-bookworm

# Set environment variables
# Prevents Python from writing pyc files to disk
ENV PYTHONDONTWRITEBYTECODE=1
# Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

# Create a non-privileged user to run the app
# This is a security best practice to prevent container breakout attacks
RUN groupadd -g 1000 python && \
    useradd -r -u 1000 -g python python

# Set the working directory
WORKDIR /app

# Install dependencies first to leverage Docker layer caching
# This ensures that rebuilding the image is fast when only code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
# Ensure the non-root user owns the files
COPY --chown=python:python . .

# Switch to the non-privileged user
USER python

# Expose the port the app runs on
EXPOSE 5000

# Use gunicorn as a production-grade WSGI server
# -w 4: 4 worker processes
# -b 0.0.0.0:5000: Bind to all interfaces on port 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
