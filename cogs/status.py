import discord
from discord.ext import commands, tasks
from discord import Embed
from discord import app_commands
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime
import time

from utils import get_site_status, ms_to_str, format_datetime_br, BR_TZ

STATUS_CHANNEL_ID = int(os.getenv("STATUS_CHANNEL_ID"))
KOOKIE_STATUS_URL = os.getenv("KOOKIE_STATUS_URL")
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB")

COLL_STATE = os.getenv("MONGO_STATUS_COLLECTION", "status")
COLL_LOGS = os.getenv("MONGO_STATUS_LOGS_COLLECTION", "status_logs")
COLL_ARCHIVE = os.getenv("MONGO_STATUS_ARCHIVE_COLLECTION", "status_logs_archive")


class StatusCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        db = AsyncIOMotorClient(MONGO_URI)[DB_NAME]
        self.db_state = db[COLL_STATE]
        self.db_logs = db[COLL_LOGS]
        self.db_archive = db[COLL_ARCHIVE]

        self.monitor_started = False

        # Estado base
        self.state = {
            "online": None,
            "last_status_change": None,  # timestamp

            "continuous_online": 0.0,
            "continuous_offline": 0.0,

            "total_online": 0.0,
            "total_offline": 0.0,

            "downtimes_count": 0,

            "last_http_code": None,
            "last_response_time": 0,
            "last_check": None,

            "status_message_id": None
        }

    # -------------------- Persistência --------------------
    async def load_state(self):
        print("🔄 Carregando estado do MongoDB...")
        doc = await self.db_state.find_one({"_id": "kookie"})
        if doc and "state" in doc:
            self.state.update(doc["state"])
            print("✅ Estado carregado:", self.state)
        else:
            await self.db_state.insert_one({"_id": "kookie", "state": self.state})
            print("⚠️ Estado não encontrado. Inicializando novo estado.")
            print("💾 Estado salvo no MongoDB:", self.state)

    async def save_state(self):
        await self.db_state.update_one(
            {"_id": "kookie"},
            {"$set": {"state": self.state}},
            upsert=True
        )
        print("💾 Estado atualizado no MongoDB.")

    # -------------------- Embed --------------------
    def build_embed(self, s, changed=False):
        online = s["online"]
        color = 0x00FF00 if online else 0xFF0000
        icon = "🟢" if online else "🔴"

        embed = Embed(
            title="Status do Kookie",
            url=KOOKIE_STATUS_URL,
            color=color
        )

        embed.add_field(name="Status atual", value=f"{icon} {'ONLINE' if online else 'OFFLINE'}", inline=True)
        embed.add_field(name="Código HTTP", value=str(s["last_http_code"]), inline=True)
        embed.add_field(name="Tempo de resposta", value=f"{s['last_response_time']}ms", inline=True)
        embed.add_field(
            name="Última verificação",
            value=format_datetime_br(s["last_check"]) if s["last_check"] else "--",
            inline=True
        )

        # Tempo contínuo
        if online:
            embed.add_field(
                name="Tempo contínuo online",
                value=ms_to_str(s["continuous_online"] * 1000),
                inline=True
            )
        else:
            embed.add_field(
                name="Tempo contínuo offline",
                value=ms_to_str(s["continuous_offline"] * 1000),
                inline=True
            )

        embed.add_field(name="Total de quedas", value=str(s["downtimes_count"]), inline=True)
        embed.add_field(name="Tempo total online", value=ms_to_str(s["total_online"] * 1000), inline=True)
        embed.add_field(name="Tempo total offline", value=ms_to_str(s["total_offline"] * 1000), inline=True)

        return embed

    # -------------------- Mensagem fixa --------------------
    async def get_status_message(self):
        channel = self.bot.get_channel(STATUS_CHANNEL_ID)
        if not channel:
            return None

        msg_id = self.state.get("status_message_id")
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                if msg.author.id == self.bot.user.id:
                    return msg
                else:
                    self.state["status_message_id"] = None
                    await self.save_state()
            except discord.NotFound:
                self.state["status_message_id"] = None
                await self.save_state()
            except Exception:
                pass

        # Procurar manualmente nas últimas 200 mensagens
        try:
            async for msg in channel.history(limit=200):
                if msg.author.id == self.bot.user.id and msg.embeds:
                    e = msg.embeds[0]
                    if e.title and "Status do Kookie" in e.title:
                        self.state["status_message_id"] = msg.id
                        await self.save_state()
                        print("🔁 Mensagem de status recuperada automaticamente (id salvo).")
                        return msg
        except Exception as e:
            print("⚠️ Erro ao procurar mensagem no canal:", e)

        return None

    # -------------------- Atualização de estado --------------------
    async def update_state(self, st):
        now_dt = datetime.now(BR_TZ)
        now_ts = now_dt.timestamp()

        if st is None:
            st = {"online": False, "http_code": 0, "response_time": 0}

        prev_online = self.state["online"]
        status_changed = prev_online is not None and prev_online != st["online"]

        if self.state["last_status_change"] is None:
            self.state["last_status_change"] = now_ts

        delta = now_ts - self.state["last_status_change"]

        if status_changed:
            if prev_online:
                self.state["total_online"] += self.state["continuous_online"] + delta
            else:
                self.state["total_offline"] += self.state["continuous_offline"] + delta

            self.state["continuous_online"] = 0
            self.state["continuous_offline"] = 0

            if prev_online and not st["online"]:
                self.state["downtimes_count"] += 1
        else:
            if st["online"]:
                self.state["continuous_online"] += delta
            else:
                self.state["continuous_offline"] += delta

        self.state["online"] = st["online"]
        self.state["last_http_code"] = st["http_code"]
        self.state["last_response_time"] = st["response_time"]
        self.state["last_check"] = now_dt
        self.state["last_status_change"] = now_ts

        await self.save_state()

        # -------------------- LOG DETALHADO --------------------
        status_text = "ONLINE" if self.state["online"] else "OFFLINE"
        cont_time = self.state["continuous_online"] if self.state["online"] else self.state["continuous_offline"]
        total_time = self.state["total_online"] if self.state["online"] else self.state["total_offline"]

        print(f"⏱️ [{now_dt.strftime('%d/%m/%Y %H:%M:%S')}] Status: {status_text}")
        print(f"   Código HTTP: {self.state['last_http_code']}, Tempo de resposta: {self.state['last_response_time']}ms")
        print(f"   Tempo contínuo {'online' if self.state['online'] else 'offline'}: {ms_to_str(cont_time*1000)}")
        print(f"   Tempo total {'online' if self.state['online'] else 'offline'}: {ms_to_str(total_time*1000)}")
        print(f"   Total de quedas: {self.state['downtimes_count']}")

        # Atualiza embed
        msg = await self.get_status_message()
        channel = self.bot.get_channel(STATUS_CHANNEL_ID)
        embed = self.build_embed(self.state)

        if msg:
            try:
                await msg.edit(embed=embed)
            except Exception:
                print("⚠️ Falha ao editar mensagem existente.")
        else:
            if channel:
                sent = await channel.send(embed=embed)
                self.state["status_message_id"] = sent.id
                await self.save_state()
                print("📤 Embed enviado no canal e id salvo.")

    # -------------------- Monitor --------------------
    @tasks.loop(seconds=60)
    async def monitor(self):
        try:
            st = await get_site_status(KOOKIE_STATUS_URL)
        except:
            st = None
        await self.update_state(st)

    @monitor.before_loop
    async def before_monitor(self):
        await self.bot.wait_until_ready()

    # -------------------- Comando /status --------------------
    @app_commands.command(
        name="status",
        description="Mostra o status atual do Kookie"
    )
    async def status_cmd(self, interaction: discord.Interaction):
        msg = await self.get_status_message()
        if msg:
            await interaction.response.send_message(embed=msg.embeds[0], ephemeral=True)
            return

        embed = self.build_embed(self.state)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # -------------------- READY --------------------
    @commands.Cog.listener()
    async def on_ready(self):
        if self.monitor_started:
            return

        await self.load_state()

        # Recupera mensagem existente ou busca manualmente
        msg = await self.get_status_message()

        # Atualiza tempo contínuo desde a última mudança
        now_dt = datetime.now(BR_TZ)
        last_change = self.state.get("last_status_change")
        if last_change:
            delta = now_dt.timestamp() - last_change
            if self.state.get("online"):
                self.state["continuous_online"] += delta
            else:
                self.state["continuous_offline"] += delta
        self.state["last_status_change"] = now_dt.timestamp()
        await self.save_state()

        # Atualiza embed
        if msg:
            embed = self.build_embed(self.state)
            try:
                await msg.edit(embed=embed)
            except Exception as e:
                print("⚠️ Falha ao atualizar mensagem existente:", e)
        else:
            channel = self.bot.get_channel(STATUS_CHANNEL_ID)
            if channel:
                embed = self.build_embed(self.state)
                sent = await channel.send(embed=embed)
                self.state["status_message_id"] = sent.id
                await self.save_state()
                print("📤 Embed enviado no canal e id salvo.")

        # Primeira verificação antes do loop
        try:
            st = await get_site_status(KOOKIE_STATUS_URL)
        except:
            st = None
        await self.update_state(st)

        # Inicia monitoramento
        self.monitor.start()
        self.monitor_started = True
        print("🟢 Monitor iniciado e mensagem de status sincronizada com o canal.")


async def setup(bot):
    await bot.add_cog(StatusCog(bot))