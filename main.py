import discord
from discord import app_commands
import os
from flask import Flask
from threading import Thread

# ==========================================
# 設定エリア
# ==========================================
TOKEN = os.getenv("TOKEN") # ←こう書き換える（カッコの中身もこのまま！）
APP_ID = "ここにApplication ID" # ←IDはそのままでOK（IDは公開されても安全です）
# ==========================================

# --- Renderで動かすためのWebサーバー機能 ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
# ---------------------------------------

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# 簡易データベース（注意：再起動するとリセットされます）
user_points = {}

@client.event
async def on_ready():
    await tree.sync()
    print(f"ログインしました: {client.user}")

@tree.command(name="money", description="所持ポイントを確認")
async def money(interaction: discord.Interaction):
    uid = interaction.user.id
    pt = user_points.get(uid, 1000)
    await interaction.response.send_message(f"💰 {interaction.user.name}さんの所持ポイント: {pt} pt")

@tree.command(name="give", description="ポイントを渡す")
async def give(interaction: discord.Interaction, user: discord.User, amount: int):
    sender_id = interaction.user.id
    receiver_id = user.id
    
    sender_pt = user_points.get(sender_id, 1000)
    user_points[sender_id] = sender_pt # 初期化
    
    if amount <= 0:
        await interaction.response.send_message("❌ 1以上の数値を指定してください。")
        return
    if sender_pt < amount:
        await interaction.response.send_message("❌ ポイントが足りません！")
        return

    user_points[sender_id] -= amount
    user_points[receiver_id] = user_points.get(receiver_id, 1000) + amount
    
    await interaction.response.send_message(f"💸 {amount} pt を送金しました！")

@tree.command(name="add", description="【管理】ポイント付与")
async def add(interaction: discord.Interaction, user: discord.User, amount: int):
    uid = user.id
    user_points[uid] = user_points.get(uid, 1000) + amount
    await interaction.response.send_message(f"✅ ポイントを {amount} pt 追加しました。")

@tree.command(name="remove", description="【管理】ポイント没収")
async def remove(interaction: discord.Interaction, user: discord.User, amount: int):
    uid = user.id
    user_points[uid] = user_points.get(uid, 1000) - amount
    await interaction.response.send_message(f"🔻 ポイントを {amount} pt 没収しました。")

# Webサーバーを起動してからBotを起動
keep_alive()
client.run(TOKEN)
