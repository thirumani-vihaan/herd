FROM python:3.11-slim

WORKDIR /code

# Install required system packages
RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

COPY requirements.lock.txt /code/requirements.lock.txt

# Install python packages
RUN pip install --no-cache-dir --upgrade -r /code/requirements.lock.txt

# Copy the source code
COPY ./app /code/app
COPY ./data /code/data
COPY ./config /code/config

# Hugging Face Spaces exposes port 7860
EXPOSE 7860

CMD ["uvicorn", "app.api.ingest:app", "--host", "0.0.0.0", "--port", "7860"]
