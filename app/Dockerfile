FROM python:3.12-slim

WORKDIR /app

# Dependências primeiro: aproveita o cache de camadas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código da aplicação
COPY app.py .

# Pasta onde o volume compartilhado será montado
RUN mkdir -p /data

EXPOSE 5000

CMD ["python", "app.py"]
