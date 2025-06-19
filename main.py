import discord
from discord import app_commands
import aiohttp
import asyncio
import time
import json
import os
import hashlib
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ==== CONFIGURAÇÕES ====
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 0))
STATUS_CHANNEL_ID = int(os.getenv("STATUS_CHANNEL_ID", 0))
UPDATES_CHANNEL_ID = int(os.getenv("UPDATES_CHANNEL_ID", 0))
COMMANDS_CHANNEL_ID = int(os.getenv("COMMANDS_CHANNEL_ID", 0))
UPDATE_LOG_URL = os.getenv("UPDATE_LOG_URL")
site_url = "https://kookie.app"
SAVE_FILE = "monitor_data.json"

if not TOKEN:
    raise ValueError("Token não encontrado! Configure a variável de ambiente DISCORD_TOKEN corretamente.")
if not GUILD_ID:
    raise ValueError("GUILD_ID não encontrado! Verifique a variável de ambiente GUILD_ID no .env")
if not STATUS_CHANNEL_ID:
    raise ValueError("STATUS_CHANNEL_ID não encontrado! Verifique a variável de ambiente STATUS_CHANNEL_ID no .env")
if not UPDATES_CHANNEL_ID:
    raise ValueError("UPDATES_CHANNEL_ID não encontrado! Verifique a variável de ambiente UPDATES_CHANNEL_ID no .env")
if not COMMANDS_CHANNEL_ID:
    raise ValueError("COMMANDS_CHANNEL_ID não encontrado! Verifique a variável de ambiente COMMANDS_CHANNEL_ID no .env")
if not UPDATE_LOG_URL:
    raise ValueError("UPDATE_LOG_URL não encontrado! Verifique a variável de ambiente UPDATE_LOG_URL no .env")

# ==== ESTADO ====
status_online = None
last_change_time = None
last_status_code = None
last_response_time = None
last_check_time = None
total_uptime = 0
total_downtime = 0
total_downtimes_count = 0
last_status_change_timestamp = None
last_updates_hash = None

# ==== UTILS ====
def format_uptime(seconds):
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    return f"{hours}h {mins}m {secs}s"

def save_state():
    data = {
        "status_online": status_online,
        "last_change_time": last_change_time,
        "last_status_code": last_status_code,
        "last_response_time": last_response_time,
        "last_check_time": last_check_time,
        "total_uptime": total_uptime,
        "total_downtime": total_downtime,
        "total_downtimes_count": total_downtimes_count,
        "last_status_change_timestamp": last_status_change_timestamp,
    }
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f)

def load_state():
    global status_online, last_change_time, last_status_code, last_response_time
    global last_check_time, total_uptime, total_downtime
    global total_downtimes_count, last_status_change_timestamp

    if not os.path.isfile(SAVE_FILE):
        return

    with open(SAVE_FILE, "r") as f:
        data = json.load(f)
        status_online = data.get("status_online")
        last_change_time = data.get("last_change_time")
        last_status_code = data.get("last_status_code")
        last_response_time = data.get("last_response_time")
        last_check_time = data.get("last_check_time")
        total_uptime = data.get("total_uptime", 0)
        total_downtime = data.get("total_downtime", 0)
        total_downtimes_count = data.get("total_downtimes_count", 0)
        last_status_change_timestamp = data.get("last_status_change_timestamp")

def is_correct_channel(interaction: discord.Interaction) -> bool:
    return interaction.channel.id == COMMANDS_CHANNEL_ID

async def fetch_updates():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(UPDATE_LOG_URL, timeout=10) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                updates = []
                for item in soup.select("li a")[:5]:
                    title = item.get_text(strip=True)
                    link = item["href"]
                    if not link.startswith("http"):
                        link = UPDATE_LOG_URL.rstrip("/") + "/" + link.lstrip("/")
                    updates.append((title, link))
                return updates
    except Exception as e:
        print("Erro ao buscar atualizações:", e)
        return None

# ==== DISCORD BOT ====
class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)  # Copia comandos globais para o servidor
        await self.tree.sync(guild=guild)  # Força o sync nesse servidor específico
        print(f"✅ Comandos sincronizados com o servidor {GUILD_ID}.")

        # Inicia as tarefas de monitoramento
        asyncio.create_task(monitor_site())
        asyncio.create_task(monitor_updates())

intents = discord.Intents.default()
client = MyClient(intents=intents)

@client.event
async def on_ready():
    print(f"🤖 Bot conectado como {client.user}")

# ==== COMANDOS ====
@client.tree.command(name="status", description="Mostra o status atual do site", guild=discord.Object(id=GUILD_ID))
async def status(interaction: discord.Interaction):
    if not is_correct_channel(interaction):
        await interaction.response.send_message("❌ Este comando só pode ser usado no canal de comandos permitido.", ephemeral=True)
        return

    state_msg = "🟢 ONLINE" if status_online else "🔴 OFFLINE"
    color = discord.Color.green() if status_online else discord.Color.red()
    uptime = format_uptime(time.time() - last_change_time) if last_change_time else "Desconhecido"
    last_check = datetime.fromtimestamp(last_check_time).strftime("%d/%m/%Y %H:%M:%S") if last_check_time else "Desconhecido"
    total_uptime_str = format_uptime(total_uptime + (time.time() - last_status_change_timestamp) if status_online and last_status_change_timestamp else total_uptime)
    total_downtime_str = format_uptime(total_downtime + (time.time() - last_status_change_timestamp) if not status_online and last_status_change_timestamp else total_downtime)

    embed = discord.Embed(title="📡 Status Atual do Site", url=site_url, color=color)
    embed.add_field(name="Status atual", value=state_msg, inline=True)
    embed.add_field(name="Código HTTP", value=str(last_status_code) if last_status_code else "Nenhum", inline=True)
    embed.add_field(name="Tempo de resposta", value=f"{last_response_time} ms" if last_response_time else "N/A", inline=True)
    embed.add_field(name="Última verificação", value=last_check, inline=True)
    embed.add_field(name="Uptime desde a última alteração", value=uptime, inline=True)
    embed.add_field(name="Total de quedas", value=str(total_downtimes_count), inline=True)
    embed.add_field(name="Tempo total online", value=total_uptime_str, inline=True)
    embed.add_field(name="Tempo total offline", value=total_downtime_str, inline=True)
    embed.set_footer(text="Monitoramento de status do Kookie")

    await interaction.response.send_message(embed=embed)

@client.tree.command(name="atualizações", description="Mostra as últimas atualizações do site", guild=discord.Object(id=GUILD_ID))
async def atualizacoes(interaction: discord.Interaction):
    if not is_correct_channel(interaction):
        await interaction.response.send_message("❌ Este comando só pode ser usado no canal de comandos permitido.", ephemeral=True)
        return

    updates = await fetch_updates()
    if not updates:
        await interaction.response.send_message("⚠️ Nenhuma atualização encontrada ou erro ao buscar.", ephemeral=True)
        return

    embed = discord.Embed(title="📝 Últimas Atualizações", url=UPDATE_LOG_URL, color=discord.Color.blurple())
    for i, (title, link) in enumerate(updates[:5], 1):
        embed.add_field(name=f"{i}. {title}", value=f"[Ver mais]({link})", inline=False)
    embed.set_footer(text="Atualizações do Kookie")

    await interaction.response.send_message(embed=embed)

@client.tree.command(name="ping", description="Mostra o ping atual do bot", guild=discord.Object(id=GUILD_ID))
async def ping(interaction: discord.Interaction):
    if not is_correct_channel(interaction):
        await interaction.response.send_message("❌ Este comando só pode ser usado no canal de comandos permitido.", ephemeral=True)
        return

    latency_ms = round(client.latency * 1000)
    embed = discord.Embed(title="🏓 Pong!", description=f"Latência do bot: **{latency_ms}ms**", color=discord.Color.blue())
    embed.set_footer(text="Ping medido pelo bot")
    await interaction.response.send_message(embed=embed)

# ==== MONITORAMENTO DE STATUS E ATUALIZAÇÕES ====
async def check_site():
    global status_online, last_change_time, last_status_code, last_response_time
    global last_check_time, last_status_change_timestamp
    global total_downtime, total_uptime, total_downtimes_count

    last_check_time = time.time()
    try:
        async with aiohttp.ClientSession() as session:
            start = time.time()
            async with session.get(site_url, timeout=10) as response:
                resp_time = (time.time() - start) * 1000
                last_response_time = int(resp_time)
                last_status_code = response.status

                if response.status == 200:
                    if status_online is not True:
                        status_online = True
                        last_change_time = time.time()
                        if last_status_change_timestamp:
                            total_downtime += time.time() - last_status_change_timestamp
                        last_status_change_timestamp = time.time()
                    save_state()
                    return True
                else:
                    if status_online is not False:
                        status_online = False
                        last_change_time = time.time()
                        total_downtimes_count += 1
                        if last_status_change_timestamp:
                            total_uptime += time.time() - last_status_change_timestamp
                        last_status_change_timestamp = time.time()
                    save_state()
                    return False
    except Exception:
        if status_online is not False:
            status_online = False
            last_change_time = time.time()
            total_downtimes_count += 1
            if last_status_change_timestamp:
                total_uptime += time.time() - last_status_change_timestamp
            last_status_change_timestamp = time.time()
        last_status_code = None
        last_response_time = None
        save_state()
        return False

async def monitor_site():
    await client.wait_until_ready()
    channel = client.get_channel(STATUS_CHANNEL_ID)

    while not client.is_closed():
        prev_status = status_online
        current_status = await check_site()

        if prev_status is not None and prev_status != current_status:
            state_msg = "🟢 ONLINE" if current_status else "🔴 OFFLINE"
            color = discord.Color.green() if current_status else discord.Color.red()
            uptime = format_uptime(time.time() - last_change_time) if last_change_time else "Desconhecido"
            last_check = datetime.fromtimestamp(last_check_time).strftime("%d/%m/%Y %H:%M:%S") if last_check_time else "Desconhecido"
            total_uptime_str = format_uptime(total_uptime + (time.time() - last_status_change_timestamp) if current_status and last_status_change_timestamp else total_uptime)
            total_downtime_str = format_uptime(total_downtime + (time.time() - last_status_change_timestamp) if not current_status and last_status_change_timestamp else total_downtime)
            msg_custom = "Tudo funcionando perfeitamente! ✅" if current_status else "Problemas detectados, aguarde… ⚠️"

            embed = discord.Embed(title="Mudança no status do Kookie", url=site_url, color=color)
            embed.add_field(name="Novo status", value=state_msg, inline=True)
            embed.add_field(name="Código HTTP", value=str(last_status_code) if last_status_code else "Nenhum", inline=True)
            embed.add_field(name="Tempo de resposta", value=f"{last_response_time} ms" if last_response_time else "N/A", inline=True)
            embed.add_field(name="Última verificação", value=last_check, inline=True)
            embed.add_field(name="Uptime desde a última alteração", value=uptime, inline=True)
            embed.add_field(name="Total de quedas", value=str(total_downtimes_count), inline=True)
            embed.add_field(name="Tempo total online", value=total_uptime_str, inline=True)
            embed.add_field(name="Tempo total offline", value=total_downtime_str, inline=True)
            embed.add_field(name="Mensagem", value=msg_custom, inline=False)
            embed.set_footer(text="Monitoramento de status do Kookie")
            await channel.send(embed=embed)

        await asyncio.sleep(60)

async def monitor_updates():
    global last_updates_hash
    await client.wait_until_ready()
    channel = client.get_channel(UPDATES_CHANNEL_ID)

    while not client.is_closed():
        updates = await fetch_updates()
        if updates:
            hash_now = hashlib.md5("".join(t for t, _ in updates).encode()).hexdigest()
            if last_updates_hash != hash_now:
                last_updates_hash = hash_now

                embed = discord.Embed(title="🆕 Nova Atualização Detectada!", url=UPDATE_LOG_URL, color=discord.Color.purple())
                for i, (title, link) in enumerate(updates[:3], 1):
                    embed.add_field(name=f"{i}. {title}", value=f"[Ver mais]({link})", inline=False)
                embed.set_footer(text="Atualizações automáticas do Kookie")
                await channel.send(embed=embed)
        await asyncio.sleep(300)

# ==== INICIAR ====
load_state()
client.run(TOKEN)