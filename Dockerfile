FROM python:3.12

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--timeout", "600", "config.wsgi:application"]
EXPOSE 8000