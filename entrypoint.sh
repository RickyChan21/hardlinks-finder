#!/bin/bash

# Default to UID/GID 1000 if not provided
USER_ID=${PUID:-1000}
GROUP_ID=${PGID:-1000}

echo "Updating python user to UID $USER_ID and GID $GROUP_ID..."

# Modify the 'python' user and group created in the Dockerfile
groupmod -g "$GROUP_ID" python
usermod -u "$USER_ID" -g "$GROUP_ID" python

# Optional: Ensure the /app directory is owned by the user
# chown -R python:python /app

# Run the command as the specified user
echo "Starting Gunicorn as $(id python)..."
exec gosu python "$@"
