# Usa a imagem oficial do Python 3.11 slim
FROM python:3.11-slim

# Define diretório de trabalho
WORKDIR /app

# Copia o arquivo de requirements (você pode criar um requirements.txt com as libs necessárias)
COPY requirements.txt .

# Instala dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código da pasta atual para o container
COPY . .

# Define a variável de ambiente para o token (opcional, pode setar no docker-compose)
ENV DISCORD_TOKEN=""
ENV GUILD_ID=""
ENV STATUS_CHANNEL_ID=""
ENV UPDATES_CHANNEL_ID=""
ENV COMMANDS_CHANNEL_ID=""
ENV UPDATE_LOG_URL=""

# Comando para rodar o bot
CMD ["python", "/app/main.py"]