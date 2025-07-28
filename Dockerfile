# Use an official lightweight Python image.
# Specifying the platform is good practice for compatibility.
FROM --platform=linux/amd64 python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the file that lists the dependencies
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the main script into the container
COPY main.py .

# This command runs when the container starts
CMD ["python", "main.py"]
