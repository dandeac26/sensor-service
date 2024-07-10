# Use an official Python runtime as a parent image
FROM python:3.11.9-bookworm

# Set the working directory in the container
WORKDIR /usr/src/app

# Create a virtual environment within the container
RUN python3 -m venv venv

# adding the virtual environment's bin directory to PATH
ENV PATH="/usr/src/app/venv/bin:$PATH"

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Update package lists and install build-essential for package compilation
RUN apt-get update && apt-get install -y build-essential

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Clean up the apt cache to reduce image size
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Make port 8001 available to the world outside this container
EXPOSE 8001

# Define environment variable
ENV MODULE_NAME=main
ENV VARIABLE_NAME=app
ENV PORT=8001

# Run app.py when the container launches, using the virtual environment
CMD ["sh", "-c", "uvicorn $MODULE_NAME:$VARIABLE_NAME --host 0.0.0.0 --port $PORT"]