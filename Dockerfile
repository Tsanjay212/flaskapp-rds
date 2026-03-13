
FROM python:3.10-slim

WORKDIR /app

# Copy all app files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run the Flask app with Gunicorn on port 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
