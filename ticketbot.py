import discord
from discord.ext import commands
import asyncio
import io 
import base64
import os
from github import Github
import chat_exporter



TOKEN = 'write here your bot token'

intents = discord.Intents.all()  # Enables all intents
bot = commands.Bot(command_prefix='!', intents=intents)

CATEGORY_IDS = {
    'Help': 1158548830967582811,  # Replace with actual IDs
    'Bugs': 1158548710930784379,
    'Report User': 1158548582916440195,  # Updated key
    'Ideas': 1158548463458472007
}


CLAIM_ROLE_ID = 1158546600763863090  # Replace with actual ID

users_with_tickets = {}
tickets_claimed_by = {}
ticket_counters = {category: 0 for category in CATEGORY_IDS.keys()}


# Define the get_transcript function
async def get_transcript(channel: discord.TextChannel):
    export = await chat_exporter.export(channel=channel)
    file_name = f"{channel.id}.html"
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(export)
    
    # Open the generated HTML file and read its contents
    with open(file_name, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Modify the CSS to remove the height: 100%; style, zoom in, and style buttons
    modified_css = html_content.replace("height: 100%;", "")
    additional_css = """
        @media (min-width: 768px) {
            body {
                zoom: 1.5;  /* Adjust this value to control the zoom level */
            }
        }
        button {
            padding: 10px;
            font-size: 1em;
            margin: 5px;
            cursor: pointer;
        }
    """
    modified_content = modified_css.replace("</style>", f"{additional_css}</style>")
    
    # Write the modified content back to the HTML file
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(modified_content)
    
    return file_name




# Define the upload function
def upload(file_path: str, channel_id: int):
    github = Github('your github token')
    repo = github.get_repo('your repo name')
    path = f"transcripts/{channel_id}.html"
    try:
        contents = repo.get_contents(path, ref='main')
        repo.update_file(path, f"Update transcript for ticket {channel_id}", open(file_path, 'r', encoding='utf-8').read(), contents.sha, branch='main')
    except Exception:
        repo.create_file(path, f"Add transcript for ticket {channel_id}", open(file_path, 'r', encoding='utf-8').read(), branch='main')
    os.remove(file_path)
    return f"yourlink{path}"

class CloseTicketView(discord.ui.View):
    def __init__(self, channel, user_id, category):
        super().__init__()
        self.channel = channel
        self.user_id = user_id
        self.category = category

        self.confirm_button = discord.ui.Button(style=discord.ButtonStyle.danger, label="Yes", custom_id="confirm_close_ticket")
        self.confirm_button.callback = self.confirm_close
        self.add_item(self.confirm_button)

        self.cancel_button = discord.ui.Button(style=discord.ButtonStyle.secondary, label="Cancel", custom_id="cancel_close_ticket")
        self.cancel_button.callback = self.cancel_close
        self.add_item(self.cancel_button)

    async def confirm_close(self, interaction: discord.Interaction):
        try:
            # Call get_transcript to generate the transcript
            file_name = await get_transcript(self.channel)
            
            # Call upload to upload the transcript to GitHub and get the URL
            url = upload(file_name, self.channel.id)
            
            # Delete the ticket channel immediately as requested
            await self.channel.delete()
            users_with_tickets[self.user_id].discard(self.category)
            
            # Create and send an initial embed message to the user
            embed = discord.Embed(
                title="Transcript Processing",
                description="Your transcript will be ready in a minute.",
                color=discord.Color.orange()
            )
            message = await interaction.user.send(embed=embed)
            
            # Wait for 1 minute
            await asyncio.sleep(70)
            
            # Edit the embed message to provide the link to the transcript
            embed.title = "Transcript Ready"
            embed.description = f"[Click here]({url}) to view your transcript."
            embed.color = discord.Color.green()
            await message.edit(embed=embed)

            # Assuming `tickets_claimed_by` and `users_with_tickets` are defined somewhere else in your code
            claimer_id = tickets_claimed_by.get(self.channel.id)
            if claimer_id:
                claimer = self.channel.guild.get_member(claimer_id)
                await claimer.send(f"Here is the transcript of the ticket you claimed: {url}")

            self.stop()
            
        except Exception as e:
            print("Error during confirm_close:", e)
            await interaction.response.send_message("An error occurred while closing the ticket.")

    async def cancel_close(self, interaction: discord.Interaction):
        await interaction.response.send_message("Ticket closure has been cancelled.")

















class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__()
        buttons = [
            discord.ui.Button(style=discord.ButtonStyle.green, label="Help", emoji="❓", custom_id="open_ticket_Help"),
            discord.ui.Button(style=discord.ButtonStyle.grey, label="Bugs", emoji="🐛", custom_id="open_ticket_Bugs"),
            discord.ui.Button(style=discord.ButtonStyle.red, label="Report User", emoji="👤", custom_id="open_ticket_Report-User"),
            discord.ui.Button(style=discord.ButtonStyle.blurple, label="Ideas", emoji="💡", custom_id="open_ticket_Ideas")
        ]
        for button in buttons:
            self.add_item(button)

class ClaimTicketView(discord.ui.View):
    def __init__(self, ticket_channel_id):
        super().__init__()
        self.ticket_channel_id = ticket_channel_id
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.primary, label="Claim", emoji="🔒", custom_id="claim_ticket"))

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.command()
async def ticket(ctx):
    view = TicketView()
    embed = discord.Embed(
        title="🎟️ Ticket System",
        description="Open a new ticket by selecting the appropriate category below.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=view)

@bot.command()
async def close(ctx):
    category = ctx.channel.category.name
    if ctx.channel.category_id not in CATEGORY_IDS.values():
        await ctx.send("This command can only be used in a ticket channel.")
        return

    claim_role = discord.utils.get(ctx.guild.roles, id=CLAIM_ROLE_ID)
    if claim_role not in ctx.author.roles and ctx.author.id not in users_with_tickets:
        await ctx.send("You don't have permission to close this ticket.")
        return

    view = CloseTicketView(ctx.channel, ctx.author.id, category)
    await ctx.send("Are you sure you want to close this ticket?", view=view)

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data["custom_id"]
        
        if custom_id.startswith("open_ticket_"):
            category_name = custom_id.split("_")[-1].replace('-', ' ')
            category_id = CATEGORY_IDS[category_name]

            user_id = interaction.user.id
            
            if user_id in users_with_tickets and category_name in users_with_tickets[user_id]:
                await interaction.response.send_message(f"You already have an open {category_name} ticket.", ephemeral=True)
                return

            await interaction.response.send_message("Check your DMs to provide the reason for your ticket.", ephemeral=True)

            embed = discord.Embed(
                title="🎫 New Ticket",
                description="Please reply with the reason for opening this ticket within the next 60 seconds.",
                color=discord.Color.blue()
            )
            await interaction.user.send(embed=embed)

            def check(message):
                return message.author.id == user_id and isinstance(message.channel, discord.DMChannel)

            try:
                message = await bot.wait_for('message', check=check, timeout=60)
            except asyncio.TimeoutError:
                await interaction.user.send('You took too long to provide the reason.')
                return
            
            guild = interaction.guild
            category = discord.utils.get(guild.categories, id=category_id)
            ticket_counters[category_name] += 1
            channel = await guild.create_text_channel(f'{category_name.lower().replace(" ", "-")}-ticket-{ticket_counters[category_name]}', category=category)

            # Grant read access to the user who created the ticket
            await channel.set_permissions(interaction.user, read_messages=True)

            users_with_tickets.setdefault(user_id, set()).add(category_name)

            claim_view = ClaimTicketView(channel.id)
            claim_embed = discord.Embed(
                title=f"🎟️ {category_name} Ticket #{ticket_counters[category_name]}",
                description=f"**Reason:** {message.content}",
                color=discord.Color.green()
            )
            await channel.send(embed=claim_embed, view=claim_view)

            confirm_embed = discord.Embed(
                title="✅ Ticket Created",
                description=f"Your ticket has been created in {category_name}! You can view it [here](https://discord.com/channels/{guild.id}/{channel.id}).",
                color=discord.Color.green()
            )
            await interaction.user.send(embed=confirm_embed)

        elif custom_id == "claim_ticket":
            claim_role = discord.utils.get(interaction.guild.roles, id=CLAIM_ROLE_ID)
            if claim_role not in interaction.user.roles:
                await interaction.response.send_message("You can't claim this ticket.", ephemeral=True)
                return

            ticket_channel_id = interaction.channel.id
            if ticket_channel_id in tickets_claimed_by:
                await interaction.response.send_message(f"This ticket has already been claimed by <@{tickets_claimed_by[ticket_channel_id]}>.", ephemeral=True)
                return

            tickets_claimed_by[ticket_channel_id] = interaction.user.id
            await interaction.response.send_message(f"<@{interaction.user.id}> has claimed this ticket.")


bot.run(TOKEN)
