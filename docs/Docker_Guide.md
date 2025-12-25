# 🐳 Guia Docker para a Kookie Chan

## Este guia explica como rodar o bot em Docker, usando docker-compose, com atualização automática de código e dependências via GitHub Actions e Watchtower.

> [!WARNING]
> Mantenha arquivos sensíveis como .env fora do Dockerfile para segurança.

## 1. Dockerfile otimizado

- Crie Dockerfile:

```
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY ../requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY ../main.py .
COPY ../utils.py .
COPY ../cogs ./cogs
COPY ../database ./database

ARG FORCE_REBUILD

CMD ["python", "main.py"]
```

# Benefícios:

- Atualiza dependências no build

- Cache otimizado

- Imagem leve (Python slim)

- Cria imagem docker multi-arch (suporta Linux e ARM)

- Evita criação de arquivos .pyc

## 2. docker-compose.yml completo:

```
services:
  bot:
    image: meuusuario/meubot:latest
    container_name: meubot
    restart: unless-stopped
    env_file:
      - ../.env
    volumes:
      - ./data:/app/data
    depends_on:
      - mongo
    networks:
      - botnet

  mongo:
    image: mongo:6
    container_name: mongodb
    restart: unless-stopped
    environment:
      MONGO_INITDB_ROOT_USERNAME: root
      MONGO_INITDB_ROOT_PASSWORD: senha
    volumes:
      - mongo_data:/data/db
    networks:
      - botnet

  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --interval 60 bot   # Verifica atualizações a cada 60s
    networks:
      - botnet

volumes:
  mongo_data:

networks:
  botnet:
```

# Benefícios:

- Persistência de dados

- Watchtower atualiza automaticamente o bot

- Reinício automático em caso de falha

- Rede interna isolada

# 3. GitHub Actions – Build e Push automático

- Crie .github/workflows/deploy.yml:

```
name: Docker Image Build Push
on:
  workflow_dispatch:
  push:
    branches:
      - main

jobs:
  build-and-push:
    runs-on: ubuntu-latest

    steps:
      # Checkout do código
      - name: Checkout repository
        uses: actions/checkout@v4

      # Configura QEMU para emulação ARM
      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      # Configura Docker Buildx
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
        with:
          driver: docker-container

      # Login no Docker Hub
      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      # Build e push da imagem multi-arch
      - name: Build and push Docker image
        uses: docker/build-push-action@v6
        with:
          context: .
          file: ./docker/dockerfile
          push: true
          platforms: |
            linux/amd64
            linux/arm/v7
            linux/arm64/v8
          tags: |
            meuusuario/meubot:latest
          build-args: |
            FORCE_REBUILD=${{ github.run_id }}

      # Teste multi-arch
      - name: Test multi-arch image
        shell: bash
        run: |
          echo "Testing linux/amd64..."
          docker run --rm --platform linux/amd64 markelpher/kookiechan:latest \
            python -c "import sys; print(sys.platform, sys.version)"

          echo "Testing linux/arm/v7..."
          docker run --rm --platform linux/arm/v7 markelpher/kookiechan:latest \
            python -c "import sys; print(sys.platform, sys.version)"

          echo "Testing linux/arm64/v8..."
          docker run --rm --platform linux/arm64/v8 markelpher/kookiechan:latest \
            python -c "import sys; print(sys.platform, sys.version)"

      # Notificação
      - name: Notify
        run: echo "Docker image multi-arch (amd64 + ARM v7/v8) built, pushed and tested successfully."
```

# Benefícios:

- Atualiza código e dependências automaticamente

- Tag SHA permite rastrear versões

- Tag latest permite Watchtower atualizar container na VPS

- Suporte multi-arch (Linux & ARM)

# 4. Configurar Secrets no GitHub

- No repositório → Settings → Secrets → Actions → New repository secret:

DOCKER_USERNAME	/ Seu usuário Docker Hub

DOCKER_PASSWORD	/ Senha ou token Docker Hub

IMAGE_NAME	/ Nome completo da imagem, ex: meuusuario/meubot

# 5. Rodando o bot na VPS

- Subir os serviços:

```
docker compose up -d
```

- Ver logs do bot:

```
docker compose logs -f bot
```

# 6. Variáveis de ambiente

- Crie .env com:

```
DISCORD_TOKEN=seu_token
```

```
MONGO_URI=mongodb://root:senha@mongodb:27017/
```

```
OTHER_VAR=valor
```

- No docker-compose.yml:

```
env_file:
  - .env
  ```

# 7. Dicas de produção

- Use tags SHA para rollback rápido

- Faça backup do volume mongo_data

- Teste localmente:

```
docker build -t meuusuario/meubot:latest .
```

```
docker run -it --rm --env-file .env meuusuario/meubot:latest
```

- Monitore logs do Watchtower:

```
docker logs -f watchtower
```