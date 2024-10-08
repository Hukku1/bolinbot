import discord
from discord.ext import commands
import time
import aiohttp
from datetime import datetime
from ticket import TicketManager
import os
import json
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io

TOKEN = 'TOKEN'
COMMAND_PREFIX = '!'

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
rate_limit_errors = 0
rate_limit_last_reset = time.time()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
ticket_manager = TicketManager(bot)
start_time = time.time()

async def on_error(event, *args, **kwargs):
    global rate_limit_errors, rate_limit_last_reset
    if isinstance(args[0], discord.HTTPException) and args[0].status == 429:
        rate_limit_errors += 1
    current_time = time.time()
    if current_time - rate_limit_last_reset > 3600:  # Reset a cada hora
        rate_limit_last_reset = current_time
        rate_limit_errors = 0

def wrap_text(draw, text, font, max_width):
    """Wrap text to fit within a given width."""
    lines = []
    words = text.split()
    line = ""
    for word in words:
        test_line = f"{line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        text_width = bbox[2] - bbox[0]
        if text_width <= max_width:
            line = test_line
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines

async def create_ticket_log_image(channel_name, messages):
    width = 800  # Largura fixa da imagem
    margin = 40  # Margem para texto e imagens
    text_height = 40  # Altura de cada linha de texto
    attachment_size = 465  # Tamanho fixo para anexos
    height = margin * 3 + (len(messages) * text_height)
    for _, _, attachments in messages:
        if attachments:
            height += attachment_size + margin
    height += margin
    background_color = (255, 255, 255)
    text_color = (0, 0, 0)
    font_path = "arial.ttf"
    image = Image.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(image)
    title_text = f"Log do ticket: {channel_name}"
    title_font = ImageFont.truetype(font_path, 24)
    draw.text((margin, margin), title_text, fill=text_color, font=title_font)
    async with aiohttp.ClientSession() as session:
        y_offset = 2 * margin + text_height
        font = ImageFont.truetype(font_path, 20)
        for user, message, attachments in messages:
            # Baixar o avatar do usuário
            async with session.get(user.avatar.url) as response:
                if response.status == 200:
                    avatar_bytes = await response.read()
                    avatar_image = Image.open(io.BytesIO(avatar_bytes)).resize((30, 30))
                    image.paste(avatar_image, (margin, y_offset))
            wrapped_message = wrap_text(draw, f"{user.name}: {message}", font, width - 2 * margin)
            for line in wrapped_message:
                draw.text((50 + margin, y_offset), line, fill=text_color, font=font)
                y_offset += text_height

            # Baixar e adicionar anexos
            for attachment in attachments:
                async with session.get(attachment.url) as response:
                    if response.status == 200:
                        attachment_bytes = await response.read()
                        attachment_image = Image.open(io.BytesIO(attachment_bytes))
                        attachment_image.thumbnail((attachment_size, attachment_size), Image.LANCZOS)
                        attachment_image = ImageOps.contain(attachment_image, (attachment_size, attachment_size))
                        attachment_image = ImageOps.expand(attachment_image, border=margin, fill=background_color)  # Adiciona uma borda para o espaço extra
                        image.paste(attachment_image, (50 + margin, y_offset), attachment_image)
                        y_offset += attachment_image.height + margin
    image_path = f"{channel_name}_log.png"
    image.save(image_path)
    return image_path

LOG_CHANNEL_FILE = 'log_channel.json'

def get_log_channel_id():
    if os.path.exists(LOG_CHANNEL_FILE):
        with open(LOG_CHANNEL_FILE, 'r') as f:
            data = json.load(f)
            return data.get('log_channel_id')
    return None

def set_log_channel_id(channel_id):
    with open(LOG_CHANNEL_FILE, 'w') as f:
        json.dump({'log_channel_id': channel_id}, f)

@bot.event
async def on_ready():
    print(f'{bot.user} conectado com sucesso ao gateway do Discord!')
    await ticket_manager.register_buttons_for_existing_embed()
    await bot.change_presence(activity=discord.Game(name="Rede Bolin ❤"))

@bot.command(name='setticketchannel')
@commands.has_permissions(administrator=True)
async def set_ticket_channel(ctx, channel: discord.TextChannel):
    ticket_manager.set_ticket_channel(channel)
    await ctx.send(f'Embed de tickets mandado para: {channel.mention}')
    await ticket_manager.send_ticket_embed()

@bot.command()
@commands.has_permissions(administrator=True)
async def setlogchannel(ctx, channel: discord.TextChannel):
    set_log_channel_id(channel.id)
    await ctx.send(f"Canal de logs definido para {channel.mention}.")
@bot.command()
@commands.has_permissions(administrator=True)
async def close(ctx):
    log_channel_id = get_log_channel_id()
    if log_channel_id:
        log_channel = bot.get_channel(int(log_channel_id))
        if log_channel is None:
            await ctx.send("Canal de logs não encontrado. Defina o canal de logs usando `!setlogchannel #canal`.")
            return
        if ctx.channel.category and ctx.channel.category.name.startswith("Ticket-"):
            try:
                messages = []
                async for message in ctx.channel.history(limit=100, oldest_first=True):
                    attachments = message.attachments if message.attachments else []
                    messages.append((message.author, message.content, attachments))
                image_path = await create_ticket_log_image(ctx.channel.name, messages)
                await log_channel.send(
                    f"Ticket {ctx.channel.name} **|** Fechado por {ctx.author.mention} **|**  Às {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}.",
                    file=discord.File(image_path)
                )
                await ctx.channel.delete()
                await ctx.channel.category.delete()
                # Remove a imagem após o envio
                os.remove(image_path)
            except Exception as e:
                await ctx.send(f"Não foi possível fechar o ticket: {e}")
        else:
            await ctx.send("Este canal não é um canal de ticket.")
    else:
        await ctx.send("Ação cancelada, Canal de logs não definido. Defina o canal de logs usando `!setlogchannel #canal`.")
@bot.command(name='debug')
@commands.is_owner()
async def debug_command(ctx):
    ping = bot.latency * 1000  #ms
    uptime = int(time.time() - start_time)
    hours, remainder = divmod(uptime, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_formatted = f"{hours}h {minutes}m {seconds}s"
    cache_info = (
        f"Canais: {len(bot.guilds[0].channels)}, "
        f"Servidores: {len(bot.guilds)}, "
        f"Usuários: {len(bot.users)}"
    )
    current_time = time.time()
    rate_limit_duration = current_time - rate_limit_last_reset
    rate_limit_info = (
        f"Erros de rate limit: {rate_limit_errors}\n"
    )
    
    # Cogs status
    cogs_status = "\n".join([f"{cog}: {'Carregado' if cog in bot.cogs else 'Não carregado'}" for cog in bot.cogs])

    # Gateway info
    gateway_latency = bot.latency * 1000
    gateway_latency_formatted = f"{gateway_latency:.1f} ms"
    
    # Ticket info
    channel_info = "Canal não setado"
    message_info = "Embed não setado"
    ticket_count = ticket_manager.ticket_count

    if ticket_manager.ticket_channel_id:
        channel = bot.get_channel(ticket_manager.ticket_channel_id)
        if channel:
            channel_info = f"{channel.mention} - ID: {ticket_manager.ticket_channel_id}"

            if ticket_manager.ticket_message_id:
                try:
                    message = await channel.fetch_message(ticket_manager.ticket_message_id)
                    message_info = f"[Message]({message.jump_url}) - ID: {ticket_manager.ticket_message_id}"
                except discord.NotFound:
                    message_info = "Embed não encontrado/acessível"
            else:
                message_info = "Nenhuma mensagem de ticket foi setada."
    embed = discord.Embed(
        title="INFO PARA DEBUG",
        description="Status atual dos sistemas do bot.",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Canal do Embed", value=channel_info, inline=False)
    embed.add_field(name="Embed do Ticket", value=message_info, inline=False)
    embed.add_field(name="Próximo ID", value=ticket_count + 1, inline=True)
    embed.add_field(name="Total de Tickets", value=ticket_count, inline=True)
    embed.add_field(name="Ping do Bot", value=f"{ping:.2f} ms", inline=False)
    embed.add_field(name="Uptime", value=uptime_formatted, inline=True)
    embed.add_field(name="Itens em Cache", value=cache_info, inline=False)
    embed.add_field(name="Taxa de Limite de Requisições", value=rate_limit_info, inline=False)
    embed.add_field(name="Status dos Cogs", value=cogs_status, inline=False)
    embed.add_field(name="Tempo Médio do Gateway", value=gateway_latency_formatted, inline=False)
    embed.set_thumbnail(url="https://images-ext-1.discordapp.net/external/8Qfksp8qYCewfxovCI32O24-AC2DecRzEGg1bd2LzLk/https/cdn.discordapp.com/icons/1234140028028981318/fc0bb733b5d6e996688ec15f3af37c48.png?format=webp&quality=lossless")
    embed.set_footer(text="Rede Bolin", icon_url="https://images-ext-1.discordapp.net/external/8Qfksp8qYCewfxovCI32O24-AC2DecRzEGg1bd2LzLk/https/cdn.discordapp.com/icons/1234140028028981318/fc0bb733b5d6e996688ec15f3af37c48.png?format=webp&quality=lossless")
    await ctx.send(embed=embed)
@bot.command()
async def ip(ctx):
    embed = discord.Embed(
        description="🔢 IP do servidor para **JAVA:** `redebolin.com.br`\n🔢 IP do servidor para **BEDROCK:** `mobile.redebolin.com.br` **Porta:** `19259`\n\n**Versão Java:** 1.16, 1.18, 1.19 e 1.21.X. \n**Versão Bedrock:** 1.20.50",
        colour=0x7b2d2d
    )
    await ctx.send(embed=embed)
bot.run(TOKEN)
