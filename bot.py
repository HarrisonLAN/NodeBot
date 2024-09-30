# bot.py
import os
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone, timedelta

# Create a bot instance
intents = discord.Intents.default()
intents.message_content = True  # Make sure message content is enabled
bot = commands.Bot(command_prefix="!", intents=intents)

# Dictionary to store event data
event_data = []

# Channel ID to send the persistent embed (replace with your channel's ID)
EVENTS_CHANNEL_ID = 1290333326485360671  # <-- Replace this with your actual channel ID
persistent_message = None  # This will store the message object of the persistent embed

# When the bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    # Sync the slash commands with the server
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} commands.')
    except Exception as e:
        print(f'Error syncing commands: {e}')

    # Start the loop to refresh the event embed every minute
    update_event_list.start()

    # Send the initial message if needed
    channel = bot.get_channel(EVENTS_CHANNEL_ID)
    if channel:
        await send_or_update_event_embed(channel)


# Task loop to update the event list every minute
@tasks.loop(minutes=1)
async def update_event_list():
    channel = bot.get_channel(EVENTS_CHANNEL_ID)
    if channel and persistent_message:
        await send_or_update_event_embed(channel)


# Function to create or update the persistent event embed with styling
async def send_or_update_event_embed(channel):
    global persistent_message

    # Remove outdated events (where the event time is in the past)
    current_time = datetime.now(timezone.utc)
    global event_data
    event_data = [event for event in event_data if event['time'] > current_time]

    # Sort events by their time (soonest first)
    event_data.sort(key=lambda x: x['time'])

    # Create the embed for the event list
    embed = discord.Embed(
        title="**Upcoming Timers**",
        color=discord.Color.blue(),
    )

    if event_data:
        # Add events to the embed with numbering
        for index, event in enumerate(event_data, start=1):
            # Subtract the current time from the event time (both are timezone-aware)
            time_remaining = event['time'] - current_time

            # Calculate hours and minutes from the time difference
            hours, remainder = divmod(int(time_remaining.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)

            # Get the time in UTC and local time
            utc_time_str = event['time'].strftime("%H:%M") + " UTC"  # Format time as HH:MM in UTC
            local_time_str = f"<t:{int(event['time'].timestamp())}:t>"  # Displays time in user's local time (HH:MM)

            # Add a styled field to the embed
            embed.add_field(
                name=f"**{index}.{event['resource']}**|" f"**in:** ```{hours}h {minutes}m```|"
                    f"**UTC:** `{utc_time_str}`|"
                    f"**Map:** *{event['map']}*", 
                value="",
                inline=False
            )
    else:
        embed.add_field(name="No events available", value="Use the buttons below to add or remove events.", inline=False)

    # View for the Add Event and Remove Event buttons
    view = EventActionView()

    if persistent_message is None:
        # If the persistent message doesn't exist, send it
        persistent_message = await channel.send(embed=embed, view=view)
    else:
        # If it exists, edit it with the updated embed
        await persistent_message.edit(embed=embed, view=view)



# Modal for adding event details
class AddEventModal(discord.ui.Modal, title="Add Event Form"):
    resource = discord.ui.TextInput(label="Resource", placeholder="Ore 8.4, Vortex Gold")
    time_str = discord.ui.TextInput(label="Event Time (in HH:MM format)", placeholder="01:30 for 1 hour 30 minutes from now")
    map_location = discord.ui.TextInput(label="Map Location", placeholder="Snag")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse the time input as hours and minutes (e.g., "1:30" means 1 hour and 30 minutes from now)
            hours, minutes = map(int, self.time_str.value.split(":"))
            duration = timedelta(hours=hours, minutes=minutes)

            # Calculate the event time by adding the duration to the current UTC time
            event_time = datetime.now(timezone.utc) + duration

            event_data.append({
                'resource': self.resource.value,
                'time': event_time,
                'map': self.map_location.value
            })

            await interaction.response.send_message(f"Event '{self.resource.value}' added successfully!", ephemeral=True)
            
            # Refresh the persistent embed after adding the event
            channel = bot.get_channel(EVENTS_CHANNEL_ID)
            if channel:
                await send_or_update_event_embed(channel)

        except ValueError:
            await interaction.response.send_message("Invalid time format. Please use the format HH:MM.", ephemeral=True)


# Modal for removing an event by number
class RemoveEventModal(discord.ui.Modal, title="Remove Event Form"):
    event_number = discord.ui.TextInput(label="Event Number", placeholder="Enter the number of the event to remove", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        global event_data
        try:
            # Get the event number input
            event_number = int(self.event_number.value)
            if 1 <= event_number <= len(event_data):
                # Remove the event by index (subtract 1 because list is 0-indexed)
                removed_event = event_data.pop(event_number - 1)
                await interaction.response.send_message(f"Event '{removed_event['resource']}' removed successfully!", ephemeral=True)
            else:
                await interaction.response.send_message("Invalid event number.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Invalid event number.", ephemeral=True)
        
        # Refresh the persistent embed after removing the event
        channel = bot.get_channel(EVENTS_CHANNEL_ID)
        if channel:
            await send_or_update_event_embed(channel)


# View to handle both buttons
class EventActionView(discord.ui.View):
    @discord.ui.button(label="Add Event", style=discord.ButtonStyle.green, custom_id="add_event")
    async def add_event_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show the modal when the "Add Event" button is clicked
        await interaction.response.send_modal(AddEventModal())

    @discord.ui.button(label="Remove Event", style=discord.ButtonStyle.red, custom_id="remove_event")
    async def remove_event_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show the modal when the "Remove Event" button is clicked
        await interaction.response.send_modal(RemoveEventModal())


# Command to force-update the event embed (admin use, optional)
@bot.tree.command(name="update_events", description="Force update the events embed")
async def update_events(interaction: discord.Interaction):
    channel = bot.get_channel(EVENTS_CHANNEL_ID)
    if channel:
        await send_or_update_event_embed(channel)
    await interaction.response.send_message("Event embed updated!", ephemeral=True)

bot.run(TOKEN)
