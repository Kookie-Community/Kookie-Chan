import discord
from discord.ext import commands

class PingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(
        name="ping",
        description="Mostra a latência do bot"
    )
    async def ping(self, interaction: discord.Interaction):
        latency_ms = round(self.bot.latency * 1000)

        # Define a cor da embed dependendo da latência
        if latency_ms < 100:
            color = 0x00FF00  # verde
        elif latency_ms < 200:
            color = 0xFFFF00  # amarelo
        else:
            color = 0xFF0000  # vermelho

        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latência atual: **{latency_ms} ms**",
            color=color
        )
        embed.timestamp = discord.utils.utcnow()

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(PingCog(bot))