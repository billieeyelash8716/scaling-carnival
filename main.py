import discord
from discord.ext import commands
from discord import app_commands, ButtonStyle
from discord.ui import Button, View
import random
import json
import os
from flask import Flask
from threading import Thread

# === Discord Setup ===
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# === File Handling ===
ECONOMY_FILE = "economy.json"
COOLDOWNS_FILE = "cooldowns.json"

def load_json(filename):
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            json.dump({}, f)
    with open(filename, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

# === Flask Keep-Alive ===
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
        self.food = self.spawn_food()
        self.direction = (0, 1)
        self.update_board()

    def spawn_food(self):
        while True:
            pos = (random.randint(0, 4), random.randint(0, 4))
            if pos not in self.snake:
                return pos

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
            self.food = self.spawn_food()
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
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.user_install()
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
        values = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
                  '8': 8, '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10, 'A': 11}
        total = sum(values[card] for card in hand)
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

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.success)
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

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.danger)
    async def stand(self, interaction: discord.Interaction, button: Button):
        if not self.game_over:
            await self.finish_game(interaction)

@tree.command(name="blackjack", description="Play Blackjack with a coin bet")
@app_commands.describe(bet="Bet amount")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.user_install()
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

@tree.command(name="roulette", description="Bet on red, black, or green")
@app_commands.describe(color="Choose red, black, or green", bet="Bet amount")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.user_install()
async def roulette(interaction: discord.Interaction, color: str, bet: int):
    user_id = str(interaction.user.id)
    economy = load_json(ECONOMY_FILE)
    balance = economy.get(user_id, 0)
    color = color.lower()

    if color not in ["red", "black", "green"]:
        return await interaction.response.send_message("Color must be red, black, or green.", ephemeral=True)
    if bet <= 0:
        return await interaction.response.send_message("Bet must be more than 0.", ephemeral=True)
    if balance < bet:
        return await interaction.response.send_message("You don't have enough coins.", ephemeral=True)

    # Deduct bet first
    economy[user_id] = balance - bet

    # Odds setup
    is_admin = interaction.user.id == 824385180944433204

    if is_admin:
        win = random.choices([True, False], weights=[8, 2])[0]  # 80% chance to win
        if win:
            outcome = color
        else:
            outcome = random.choice(["red", "black", "green"])
            while outcome == color:
                outcome = random.choice(["red", "black", "green"])
    else:
        outcome = random.choices(
            ["red", "black", "green"],
            weights=[47, 47, 6],
            k=1
        )[0]

    # Calculate result
    if outcome == color:
        multiplier = {"red": 2, "black": 2, "green": 15}[color]
        winnings = bet * multiplier
        economy[user_id] += winnings
        result = f"You won! The ball landed on **{outcome}**.\nYou won {winnings} coins!"
    else:
        result = f"You lost. The ball landed on **{outcome}**."

    save_json(ECONOMY_FILE, economy)
    await interaction.response.send_message(result)


# === Economy Commands ===
@tree.command(name="balance", description="Check your coin balance")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.user_install()
async def balance(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    economy = load_json(ECONOMY_FILE)
    coins = economy.get(user_id, 0)
    await interaction.response.send_message(f"You have {coins} coins.")

@tree.command(name="daily", description="Claim daily reward")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.user_install()
async def daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    economy = load_json(ECONOMY_FILE)
    cooldowns = load_json(COOLDOWNS_FILE)

    from datetime import datetime, timedelta
    now = datetime.utcnow()
    last = cooldowns.get(user_id)

    if last:
        last = datetime.fromisoformat(last)
        elapsed = now - last
        cooldown_period = timedelta(hours=24)
        if elapsed < cooldown_period:
            remaining = cooldown_period - elapsed
            hours, remainder = divmod(int(remaining.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            return await interaction.response.send_message(
                f"Come back in {hours}h {minutes}m {seconds}s.", ephemeral=True
            )

    economy[user_id] = economy.get(user_id, 0) + 100
    cooldowns[user_id] = now.isoformat()

    save_json(ECONOMY_FILE, economy)
    save_json(COOLDOWNS_FILE, cooldowns)
    await interaction.response.send_message("You claimed 100 coins!")

@tree.command(name="give", description="Give coins to another user")
@app_commands.describe(user="User to give coins to", amount="Amount to give")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.user_install()
async def give(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != 824385180944433204:
        return await interaction.response.send_message("You can't use this command.", ephemeral=True)

    economy = load_json(ECONOMY_FILE)
    receiver_id = str(user.id)
    economy[receiver_id] = economy.get(receiver_id, 0) + amount
    save_json(ECONOMY_FILE, economy)
    await interaction.response.send_message(f"Gave {amount} coins to {user.name}.")

@tree.command(name="say", description="Send a message as the bot.")
@app_commands.describe(message="The message to send")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.user_install()
async def say(interaction: discord.Interaction, message: str):
    if interaction.user.id != 824385180944433204:
        return await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)

    await interaction.channel.send(message)
    await interaction.response.send_message("Message sent.", ephemeral=True)

# === On Ready ===
@bot.event
async def on_ready():
    await tree.sync()
    await bot.change_presence(
        status=discord.Status.idle,
        activity=discord.Game(name="with your toes!")
    )
    print(f"Logged in as {bot.user}")

# === Run Bot ===
if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("TOKEN")
    if not TOKEN:
        print("TOKEN is missing. Set it in Render environment variables.")
    else:
        bot.run(TOKEN)
