import discord
from discord.ext import commands
from datetime import datetime
import json
import os

class TicketManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticket_channel_id = None
        self.ticket_message_id = None
        self.data_file = 'ticket_data.json'
        self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                self.ticket_channel_id = data.get('ticket_channel_id')
                self.ticket_message_id = data.get('ticket_message_id')
                self.ticket_count = data.get('ticket_count', 0)
        else:
            self.ticket_count = 0

    def save_data(self):
        with open(self.data_file, 'w') as f:
            json.dump({
                'ticket_channel_id': self.ticket_channel_id,
                'ticket_message_id': self.ticket_message_id,
                'ticket_count': self.ticket_count
            }, f)

    def set_ticket_channel(self, channel):
        self.ticket_channel_id = channel.id
        self.ticket_message_id = None 
        self.save_data()

    async def send_ticket_embed(self):
        if not self.ticket_channel_id:
            return

        channel = self.bot.get_channel(self.ticket_channel_id)
        if channel:
            embed = discord.Embed(
                title="Bem-vindo ao Suporte da Rede Bolin!",
                description="Para solicitar assistência, clique no tópico que melhor descreve sua situação abaixo. Após abrir o atendimento, aguarde a resposta de um membro da equipe de suporte. Faremos o possível para atender sua solicitação o mais rápido possível!\n\n**🔧 Horários de Atendimento:**\nSegunda a Sexta-feira, das 13h às 21h (Horário de Brasília)",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url="https://images-ext-1.discordapp.net/external/8Qfksp8qYCewfxovCI32O24-AC2DecRzEGg1bd2LzLk/https/cdn.discordapp.com/icons/1234140028028981318/fc0bb733b5d6e996688ec15f3af37c48.png?format=webp&quality=lossless")
            embed.set_footer(text="Rede Bolin",icon_url="https://images-ext-1.discordapp.net/external/8Qfksp8qYCewfxovCI32O24-AC2DecRzEGg1bd2LzLk/https/cdn.discordapp.com/icons/1234140028028981318/fc0bb733b5d6e996688ec15f3af37c48.png?format=webp&quality=lossless")
            # Define buttons for each category
            categories = ["Geral", "Reportes", "Punições", "Parcerias"]
            view = discord.ui.View(timeout=None)
            for category in categories:
                button = discord.ui.Button(label=category, style=discord.ButtonStyle.green)
                button.callback = self.make_button_callback(category)
                view.add_item(button)
            message = await channel.send(embed=embed, view=view)
            self.ticket_message_id = message.id
            self.save_data()
    async def register_buttons_for_existing_embed(self):
        if not self.ticket_channel_id or not self.ticket_message_id:
            return
        channel = self.bot.get_channel(self.ticket_channel_id)
        if channel:
            try:
                message = await channel.fetch_message(self.ticket_message_id)
                view = discord.ui.View(timeout=None)
                categories = ["Geral", "Reportes", "Punições", "Parcerias"]
                for category in categories:
                    button = discord.ui.Button(label=category, style=discord.ButtonStyle.green)
                    button.callback = self.make_button_callback(category)
                    view.add_item(button)
                await message.edit(view=view)
            except discord.NotFound:
                print("Mensagem não encontrada, talvez ela tenha sido deletada?")
    def make_button_callback(self, category):
        async def button_callback(interaction: discord.Interaction):
            if interaction.message.id == self.ticket_message_id:
                await self.create_ticket(interaction.user, category)
                await interaction.response.send_message(f"Um ticket da categoria {category} foi criado!", ephemeral=True)
        return button_callback
    async def create_ticket(self, user: discord.User, category: str):
        guild = self.bot.get_guild(self.bot.guilds[0].id)
        self.ticket_count += 1
        self.save_data()
        category_channel = await guild.create_category(
            f"Ticket-{user.name}",
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user: discord.PermissionOverwrite(read_messages=True)
            }
        )
        channel_name = f"{user.name}-{self.ticket_count}"
        channel = await guild.create_text_channel(channel_name, category=category_channel)
        embed = discord.Embed(
            title="Ticket Criado!",
            description=f"{user.mention}, Ticket criado para: **{category}**.\nDiga seu nick dentro do jogo, e o motivo da abertura do ticket.",
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url="https://images-ext-1.discordapp.net/external/8Qfksp8qYCewfxovCI32O24-AC2DecRzEGg1bd2LzLk/https/cdn.discordapp.com/icons/1234140028028981318/fc0bb733b5d6e996688ec15f3af37c48.png?format=webp&quality=lossless")
        embed.set_footer(text="⛔ Para fechar o ticket, suportes, usem `!close`", icon_url="https://images-ext-1.discordapp.net/external/8Qfksp8qYCewfxovCI32O24-AC2DecRzEGg1bd2LzLk/https/cdn.discordapp.com/icons/1234140028028981318/fc0bb733b5d6e996688ec15f3af37c48.png?format=webp&quality=lossless")
        await channel.send(content="@here", embed=embed)
def setup(bot):
    bot.add_cog(TicketManager(bot))