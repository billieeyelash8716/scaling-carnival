import os
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
import threading
import random
import json

# Flask keep-alive
app = Flask(__name__)
@app.route("/")
def home():
    return "Bot is running!"
def run_flask():
    app.run(host="0.0.0.0", port=8080)

# Economy data file
DATA_FILE = "economy.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# Bot setup
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()

# Slash commands
@bot.tree.command(name="ping", description="Check if the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")

@bot.tree.command(name="balance", description="Check your coin balance")
async def balance(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    data = load_data()
    coins = data.get(user_id, 0)
    await interaction.response.send_message(f"You have {coins} coins.")

@bot.tree.command(name="daily", description="Get your daily coin bonus")
async def daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    data = load_data()
    data[user_id] = data.get(user_id, 0) + 100
    save_data(data)
    await interaction.response.send_message("You received 100 coins!")

@bot.tree.command(name="snake", description="Play a simple Snake game (text-based)")
async def snake(interaction: discord.Interaction):
    directions = ["⬅️", "➡️", "⬆️", "⬇️"]
    game_board = [
        ["⬛"] * 5 for _ in range(5)
    ]
    game_board[2][2] = "🟩"
    snake_text = "\n".join("".join(row) for row in game_board)
    await interaction.response.send_message(f"Snake Game\nUse imagination!
{snake_text}\nControls: {' '.join(directions)}")

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.run(os.getenv("DISCORD_TOKEN"))
