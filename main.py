import os
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
import discord

# -----------------------------
# Configuração inicial
# -----------------------------
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="none", intents=intents)

slash_synced = False

# -----------------------------
# Carregamento de cogs
# -----------------------------
async def load_cog(cog_name: str):
    try:
        await bot.load_extension(cog_name)
        print(f"[+] Cog '{cog_name}' carregada")
    except Exception as e:
        print(f"[!] Erro ao carregar '{cog_name}': {e}")

async def load_cogs():
    print("⏳ Carregando cogs...")
    tasks_list = []
    for file in os.listdir("./cogs"):
        if file.endswith(".py"):
            cog_name = f"cogs.{file[:-3]}"
            tasks_list.append(load_cog(cog_name))
    if tasks_list:
        await asyncio.gather(*tasks_list)
    print("✅ Todas as cogs carregadas!")

async def init_database():
    print("⏳ Inicializando banco de dados...")
    # Coloque aqui seu código real de inicialização
    await asyncio.sleep(1)
    print("✅ Banco de dados inicializado!")

# -----------------------------
# Evento on_ready
# -----------------------------
@bot.event
async def on_ready():
    global slash_synced
    if not slash_synced:
        print("⏳ Sincronizando comandos de slash...")
        try:
            await bot.tree.sync()
            print("✅ Comandos de slash sincronizados!")
        except Exception as e:
            print(f"[!] Erro ao sincronizar comandos de slash: {e}")
        slash_synced = True
    print(f"✅ Bot {bot.user} está online!")

# -----------------------------
# Função principal
# -----------------------------
async def main():
    await load_cogs()
    await init_database()
    print("⏳ Conectando o bot...")
    await bot.start(os.getenv("DISCORD_TOKEN"))

# -----------------------------
# Entry point
# -----------------------------
if __name__ == "__main__":
    asyncio.run(main())
