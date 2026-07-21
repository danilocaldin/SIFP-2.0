# Imagem da API (sifp/api) para hospedagem -- o app Streamlit (app.py) e
# o frontend Next.js (frontend/) não entram aqui, cada um tem seu próprio
# caminho de deploy (Streamlit roda local; frontend vai pra Vercel).
FROM python:3.13-slim

WORKDIR /app

# libgomp1 é dependência de runtime do scikit-learn (OpenMP); build-essential
# só é necessário se algum pacote precisar compilar a partir do source em
# vez de usar wheel pré-compilada, mas mantemos por segurança em imagens slim.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY sifp/ sifp/

EXPOSE 8000

CMD ["uvicorn", "sifp.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
