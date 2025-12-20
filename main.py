import discord
from discord import app_commands
import os
from flask import Flask
from threading import Thread

# ==========================================
# 設定エリア
# ==========================================
TOKEN = os.getenv("TOKEN")
APP_ID = "1451611154861523024" # ←もし消えていたら書き直してください
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

# 簡易データベース
user_points = {}

@client.event
async def on_ready():
    await tree.sync()
    print(f"ログインしました: {client.user}", flush=True)
    
    # ▼▼▼ ここを追加しました ▼▼▼
    # 「プレイ中: /money で残高確認」と表示させる設定
    await client.change_presence(activity=discord.Game(name="/money で所持ポイントを確認"))

# ▼▼▼ ここからコマンド定義（プロフィール表示対応版） ▼▼▼

@tree.command(name="money", description="所持ポイントを確認")
@app_commands.allowed_installs(guilds=True, users=True) # ←これがプロフィール表示の鍵です
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def money(interaction: discord.Interaction):
    uid = interaction.user.id
    pt = user_points.get(uid, 1000)
    await interaction.response.send_message(f"💰 {interaction.user.mention} さんの所持ポイント: {pt} pt")

@tree.command(name="give", description="ポイントを渡す")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def give(interaction: discord.Interaction, user: discord.User, amount: int):
    sender_id = interaction.user.id
    receiver_id = user.id
    
    sender_pt = user_points.get(sender_id, 1000)
    user_points[sender_id] = sender_pt
    
    if amount <= 0:
        await interaction.response.send_message("❌ 1以上の数値を指定してください。", ephemeral=True)
        return
    if sender_pt < amount:
        await interaction.response.send_message("❌ ポイントが足りません！", ephemeral=True)
        return

    user_points[sender_id] -= amount
    user_points[receiver_id] = user_points.get(receiver_id, 1000) + amount
    
    await interaction.response.send_message(f"💸 {interaction.user.mention} から {user.mention} へ {amount} pt 送金しました！")

@tree.command(name="add", description="ポイントを付与")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def add(interaction: discord.Interaction, user: discord.User, amount: int):
    uid = user.id
    user_points[uid] = user_points.get(uid, 1000) + amount
    await interaction.response.send_message(f"✅ {user.mention} に {amount} pt 追加しました。")

@tree.command(name="remove", description="ポイントを没収")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def remove(interaction: discord.Interaction, user: discord.User, amount: int):
    uid = user.id
    user_points[uid] = user_points.get(uid, 1000) - amount
    await interaction.response.send_message(f"🔻 {user.mention} から {amount} pt 没収しました。")

# Webサーバーを起動してからBotを起動
keep_alive()
client.run(TOKEN)
