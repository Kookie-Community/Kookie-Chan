import discord
from discord.ext import commands, tasks
from discord import Embed
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import os
import asyncio
import aiohttp
from bs4 import BeautifulSoup

# Configurações do MongoDB
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB")
COLL_UPDATES = os.getenv("MONGO_UPDATES_COLLECTION", "updates")
COLL_ARCHIVE = os.getenv("MONGO_UPDATES_ARCHIVE_COLLECTION", "updates_archive")

# Canal e URL de anúncios
UPDATES_CHANNEL_ID = int(os.getenv("UPDATES_CHANNEL_ID", 0))
KOOKIE_UPDATES_URL = os.getenv("KOOKIE_UPDATES_URL")

# Verificação da URL
if not KOOKIE_UPDATES_URL:
    raise ValueError("❌ A variável de ambiente KOOKIE_UPDATES_URL não está definida!") 

async def get_kookie_updates(limit=5):
    """
    Busca os últimos updates da página de anúncios do Kookie.
    Retorna uma lista de dicionários com 'title', 'description' e 'date'.
    """
    updates = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(KOOKIE_UPDATES_URL) as resp:
                if resp.status != 200:
                    print(f"⚠️ Não foi possível acessar a página de updates (HTTP {resp.status})")
                    return updates

                text = await resp.text()
                soup = BeautifulSoup(text, "html.parser")

                # Ajuste os seletores conforme o HTML real do site
                items = soup.select(".announcement-item")  # cada anúncio
                for item in items[:limit]:
                    title_elem = item.select_one(".announcement-title")
                    desc_elem = item.select_one(".announcement-description")
                    date_elem = item.select_one(".announcement-date")

                    title = title_elem.text.strip() if title_elem else "Sem título"
                    description = desc_elem.text.strip() if desc_elem else "Sem descrição"
                    date_text = date_elem.text.strip() if date_elem else None

                    try:
                        date = datetime.strptime(date_text, "%d/%m/%Y") if date_text else datetime.utcnow()
                    except Exception:
                        date = datetime.utcnow()

                    updates.append({"title": title, "description": description, "date": date})
    except Exception as e:
        print(f"❌ Erro ao buscar updates: {e}")

    return updates


class UpdatesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        db = AsyncIOMotorClient(MONGO_URI)[DB_NAME]
        self.db_updates = db[COLL_UPDATES]
        self.db_archive = db[COLL_ARCHIVE]
        self.auto_updates_started = False
        self.compact_started = False

    async def save_update(self, update):
        exists = await self.db_updates.find_one({"title": update["title"]})
        if not exists:
            await self.db_updates.insert_one({
                "title": update["title"],
                "description": update["description"],
                "date": update["date"],
                "timestamp": datetime.utcnow()
            })
            return True
        return False

    async def save_updates(self, updates):
        new_updates = []
        for u in updates:
            if await self.save_update(u):
                new_updates.append(u)
        return new_updates

    def build_updates_embed(self, updates):
        embed = Embed(
            title="📢 Últimas atualizações do Kookie",
            color=0xFFD700
        )
        for update in updates:
            date_str = update["date"].strftime("%d/%m/%Y %H:%M")
            embed.add_field(
                name=f"{update['title']} ({date_str})",
                value=update["description"],
                inline=False
            )
        return embed

    async def fetch_and_save_updates(self, limit=5):
        updates = await get_kookie_updates(limit)
        new_updates = await self.save_updates(updates)
        return new_updates

    @commands.hybrid_command(name="updates", description="Mostra as últimas atualizações e notícias do Kookie")
    async def updates_cmd(self, ctx, limit: int = 5):
        await ctx.interaction.response.defer(ephemeral=True)
        try:
            await self.fetch_and_save_updates(limit)
            cursor = self.db_updates.find().sort("timestamp", -1).limit(limit)
            saved_updates = await cursor.to_list(length=limit)
            if not saved_updates:
                await ctx.interaction.followup.send("Nenhuma atualização encontrada.", ephemeral=True)
                return
            embed = self.build_updates_embed(saved_updates)
            await ctx.interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await ctx.interaction.followup.send(f"❌ Falha ao buscar atualizações: {e}", ephemeral=True)

    @tasks.loop(minutes=10)
    async def auto_post_updates(self):
        if UPDATES_CHANNEL_ID == 0:
            print("⚠️ Canal de updates não configurado.")
            return
        channel = self.bot.get_channel(UPDATES_CHANNEL_ID)
        if not channel:
            print("⚠️ Canal de updates não encontrado!")
            return
        try:
            new_updates = await self.fetch_and_save_updates(limit=10)
            if new_updates:
                embed = self.build_updates_embed(new_updates)
                await channel.send(embed=embed)
                print(f"📢 {len(new_updates)} novos updates enviados no canal.")
        except Exception as e:
            print("❌ Falha ao enviar updates automáticos:", e)

    @tasks.loop(hours=24)
    async def compactar_updates_antigos(self):
        cutoff = datetime.utcnow() - timedelta(days=30)
        old_updates_cursor = self.db_updates.find({"timestamp": {"$lt": cutoff}})
        old_updates = await old_updates_cursor.to_list(length=None)
        if not old_updates:
            return

        daily_summary = {}
        for update in old_updates:
            day = update["date"].strftime("%Y-%m-%d")
            if day not in daily_summary:
                daily_summary[day] = {"date": day, "updates": []}
            daily_summary[day]["updates"].append(update)

        for day_data in daily_summary.values():
            await self.db_archive.update_one({"date": day_data["date"]}, {"$set": day_data}, upsert=True)

        await self.db_updates.delete_many({"timestamp": {"$lt": cutoff}})
        print(f"🗂️ Updates antigos compactados e deletados ({len(old_updates)} registros).")

    @compactar_updates_antigos.before_loop
    async def before_compactar(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.auto_updates_started:
            self.auto_post_updates.start()
            self.auto_updates_started = True
            print("🟢 Tarefa automática de updates iniciada!")
        if not self.compact_started:
            self.compactar_updates_antigos.start()
            self.compact_started = True
            print("🟢 Compactação diária de updates iniciada!")


async def setup(bot):
    await bot.add_cog(UpdatesCog(bot))