import discord
from discord.ext import commands, tasks
from discord import app_commands, ButtonStyle
from discord.ui import Button, View
import random
import json
import os
from flask import Flask
from threading import Thread

TOKEN = "YOUR_DISCORD_BOT_TOKEN"  # Replace with your bot token

intents = discord.Intents.default()
client = commands.Bot(command_prefix="!", intents=intents)
bot = client
tree = bot.tree

ECONOMY_FILE = "economy.json"
COOLDOWNS_FILE = "cooldowns.json"

def load_json(filename):
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            json.dump({}, f)
    with open(filename, "r") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

# === Flask keep-alive ===
app = Flask("")

@app.route("/")
def home():
    return "Bot is alive!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    Thread(target=run).start()

# === Snake Game ===
class SnakeView(View):
    def __init__(self, user):
        super().__init__(timeout=60)
        self.user = user
        self.board = [["⬛"] * 5 for _ in range(5)]
        self.snake = [(2, 2)]
        self.food = (random.randint(0, 4), random.randint(0, 4))
        while self.food == self.snake[0]:
            self.food = (random.randint(0, 4), random.randint(0, 4))
        self.direction = (0, 1)
        self.update_board()

    def update_board(self):
        for y in range(5):
            for x in range(5):
                self.board[y][x] = "⬛"
        self.board[self.food[1]][self.food[0]] = "🍎"
        for x, y in self.snake:
            self.board[y][x] = "🟩"
        head_x, head_y = self.snake[-1]
        self.board[head_y][head_x] = "🟥"

    def render(self):
        return "\n".join("".join(row) for row in self.board)

    def move(self, dx, dy):
        head_x, head_y = self.snake[-1]
        new_x = (head_x + dx) % 5
        new_y = (head_y + dy) % 5
        new_head = (new_x, new_y)
        if new_head in self.snake:
            return False
        self.snake.append(new_head)
        if new_head == self.food:
            self.food = (random.randint(0, 4), random.randint(0, 4))
        else:
            self.snake.pop(0)
        self.update_board()
        return True

    async def interaction_check(self, interaction):
        return interaction.user.id == self.user.id

    async def respond(self, interaction):
        await interaction.response.edit_message(content=self.render(), view=self)

    @discord.ui.button(label="⬅", style=ButtonStyle.primary)
    async def left(self, interaction, _):
        if self.move(-1, 0):
            await self.respond(interaction)

    @discord.ui.button(label="⬆", style=ButtonStyle.primary)
    async def up(self, interaction, _):
        if self.move(0, -1):
            await self.respond(interaction)

    @discord.ui.button(label="⬇", style=ButtonStyle.primary)
    async def down(self, interaction, _):
        if self.move(0, 1):
            await self.respond(interaction)

    @discord.ui.button(label="➡", style=ButtonStyle.primary)
    async def right(self, interaction, _):
        if self.move(1, 0):
            await self.respond(interaction)

@tree.command(name="snake", description="Play Snake game for free")
async def snake(interaction: discord.Interaction):
    view = SnakeView(interaction.user)
    await interaction.response.send_message(content=view.render(), view=view)

# === Blackjack Game ===
class BlackjackView(View):
    def __init__(self, user, bet):
        super().__init__(timeout=60)
        self.user = user
        self.bet = bet
        self.economy = load_json(ECONOMY_FILE)
        self.deck = self.create_deck()
        random.shuffle(self.deck)
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]
        self.game_over = False

    def create_deck(self):
        return [v for v in ([str(n) for n in range(2, 11)] + ["J", "Q", "K", "A"]) * 4]

    def calculate(self, hand):
        values = {'J': 10, 'Q': 10, 'K': 10, 'A': 11}
        total = sum(values.get(card, int(card)) for card in hand)
        aces = hand.count("A")
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total

    def display_hand(self, hand):
        return " ".join(hand)

    async def interaction_check(self, interaction):
        return interaction.user.id == self.user.id

    async def finish_game(self, interaction):
        self.game_over = True
        for child in self.children:
            child.disabled = True

        player_score = self.calculate(self.player_hand)
        dealer_score = self.calculate(self.dealer_hand)

        result = ""
        if player_score > 21:
            result = "You busted! ❌"
        else:
            while dealer_score < 17:
                self.dealer_hand.append(self.deck.pop())
                dealer_score = self.calculate(self.dealer_hand)

            if dealer_score > 21 or player_score > dealer_score:
                result = "You win! ✅"
                self.economy[str(self.user.id)] += self.bet * 2
            elif player_score == dealer_score:
                result = "Push! 🤝"
                self.economy[str(self.user.id)] += self.bet
            else:
                result = "Dealer wins! ❌"

        save_json(ECONOMY_FILE, self.economy)

        await interaction.response.edit_message(
            content=(
                f"🃏 Blackjack\n"
                f"Your hand: {self.display_hand(self.player_hand)} (Total: {player_score})\n"
                f"Dealer's hand: {self.display_hand(self.dealer_hand)} (Total: {dealer_score})\n"
                f"**{result}**"
            ),
            view=self
        )

    @discord.ui.button(label="Hit", style=ButtonStyle.success)
    async def hit(self, interaction: discord.Interaction, button: Button):
        if not self.game_over:
            self.player_hand.append(self.deck.pop())
            if self.calculate(self.player_hand) > 21:
                await self.finish_game(interaction)
            else:
                await interaction.response.edit_message(
                    content=(
                        f"🃏 Blackjack\n"
                        f"Your hand: {self.display_hand(self.player_hand)} (Total: {self.calculate(self.player_hand)})\n"
                        f"Dealer's hand: {self.dealer_hand[0]} ❓"
                    ),
                    view=self
                )

    @discord.ui.button(label="Stand", style=ButtonStyle.danger)
    async def stand(self, interaction: discord.Interaction, button: Button):
        if not self.game_over:
            await self.finish_game(interaction)

@tree.command(name="blackjack", description="Play Blackjack with a coin bet")
@app_commands.describe(bet="Bet amount")
async def blackjack(interaction: discord.Interaction, bet: int):
    user_id = str(interaction.user.id)
    economy = load_json(ECONOMY_FILE)
    balance = economy.get(user_id, 0)

    if bet <= 0:
        return await interaction.response.send_message("Bet must be more than 0.", ephemeral=True)
    if balance < bet:
        return await interaction.response.send_message("You don't have enough coins.", ephemeral=True)

    economy[user_id] -= bet
    save_json(ECONOMY_FILE, economy)

    view = BlackjackView(interaction.user, bet)
    await interaction.response.send_message(
        content=(
            f"🃏 Blackjack\n"
            f"Your hand: {view.display_hand(view.player_hand)} (Total: {view.calculate(view.player_hand)})\n"
            f"Dealer's hand: {view.dealer_hand[0]} ❓"
        ),
        view=view
    )

# === Economy Commands ===
@tree.command(name="balance", description="Check your coin balance")
async def balance(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    economy = load_json(ECONOMY_FILE)
    coins = economy.get(user_id, 0)
    await interaction.response.send_message(f"You have {coins} coins.")

@tree.command(name="daily", description="Claim daily reward")
async def daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    economy = load_json(ECONOMY_FILE)
    cooldowns = load_json(COOLDOWNS_FILE)

    from datetime import datetime, timedelta
    now = datetime.utcnow()
    last = cooldowns.get(user_id)
    if last:
        last = datetime.fromisoformat(last)
        if now - last < timedelta(hours=24):
            remaining = timedelta(hours=24) - (now - last)
            return await interaction.response.send_message(f"Come back in {remaining}.", ephemeral=True)

    economy[user_id] = economy.get(user_id, 0) + 100
    cooldowns[user_id] = now.isoformat()

    save_json(ECONOMY_FILE, economy)
    save_json(COOLDOWNS_FILE, cooldowns)
    await interaction.response.send_message("You claimed 100 coins!")

@tree.command(name="give", description="Give coins to another user")
@app_commands.describe(user="User to give coins to", amount="Amount to give")
async def give(interaction: discord.Interaction, user: discord.User, amount: int):
    sender_id = str(interaction.user.id)
    receiver_id = str(user.id)
    economy = load_json(ECONOMY_FILE)

    if interaction.user.id != 824385180944433204:
        return await interaction.response.send_message("You can't use this command.", ephemeral=True)

    economy[receiver_id] = economy.get(receiver_id, 0) + amount
    save_json(ECONOMY_FILE, economy)
    await interaction.response.send_message(f"Gave {amount} coins to {user.mention}.")

# === On Ready ===
@bot.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {bot.user}")

keep_alive()
bot.run(DISCORD_TOKEN)

