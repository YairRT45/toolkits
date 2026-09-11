FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*
RUN python -m venv /env
ENV PATH="/env/bin:$PATH"
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./src /app/
EXPOSE 8000
CMD ["gunicorn", "toolkits.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]