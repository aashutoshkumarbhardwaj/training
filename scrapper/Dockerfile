FROM mcr.microsoft.com/playwright/python:latest

# Set working directory
WORKDIR /app

# Copy requirements so it's available in the image for reproducibility
COPY requirements.txt /app/requirements.txt

# Install key dependencies explicitly to avoid relying solely on the copied requirements.txt
RUN python -m pip install --no-cache-dir \
    supabase==2.3.1 \
    telethon==1.42.0 \
    python-dotenv==1.0.1 \
    playwright==1.41.2 \
    parsel \
    requests \
    feedparser \
    httpx==0.24.1 \
    gradio

# Copy the rest of the application
COPY . /app

# Expose the Gradio default port
EXPOSE 7860

ENV PYTHONUNBUFFERED=1

# Use the server entrypoint
CMD ["python", "server.py"]
FROM mcr.microsoft.com/playwright/python:latest

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt /app/requirements.txt

# Install key dependencies explicitly to avoid relying solely on the copied requirements.txt
# (this ensures gradio and the other packages are present even if the requirements file in the build
# context is different or malformed)
RUN python -m pip install --no-cache-dir \
	supabase==2.3.1 \
	telethon==1.42.0 \
	python-dotenv==1.0.1 \
	playwright==1.41.2 \
	parsel \
	requests \
	feedparser \
	httpx==0.24.1 \
	gradio

# Copy the rest of the application
COPY . /app

# Expose the Gradio default port
EXPOSE 7860

ENV PYTHONUNBUFFERED=1

# Use the server entrypoint
CMD ["python", "server.py"]
FROM mcr.microsoft.com/playwright/python:latest

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Ensure Gradio is installed (some base image/pip quirks can omit optional deps during multi-stage builds)
RUN python -m pip install --no-cache-dir gradio

# Copy the rest of the application
COPY . /app

# Expose the Gradio default port
EXPOSE 7860

ENV PYTHONUNBUFFERED=1

# Use the server entrypoint
CMD ["python", "server.py"]
FROM mcr.microsoft.com/playwright/python:latest

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the rest of the application
COPY . /app

# Expose the Gradio default port
EXPOSE 7860

ENV PYTHONUNBUFFERED=1

# Use the server entrypoint
CMD ["python", "server.py"]

