import discord
from discord import app_commands
import os
from flask import Flask
from threading import Thread
import datetime

# ==========================================
# 設定エリア
# ==========================================
TOKEN = os.getenv("TOKEN")
APP_ID = "1451611154861523024" # ←もし消えていたら書き直してください

# ★通知を送りたいチャンネルのID（数字のみ）
ALERT_CHANNEL_ID = 1449751244351733831
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
intents.voice_states = True # 通話状態の監視に必須
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# 簡易データベース（ポイント用）
user_points = {}

# 通話開始時間を記録する辞書 {チャンネルID: 開始時間}
call_start_times = {}

@client.event
async def on_ready():
    await tree.sync()
    print(f"ログインしました: {client.user}", flush=True)
    await client.change_presence(activity=discord.Game(name="/money で残高確認"))

# ▼▼▼ 通話お知らせ機能（高機能版） ▼▼▼
@client.event
async def on_voice_state_update(member, before, after):
    # 通知チャンネルを取得
    alert_channel = client.get_channel(ALERT_CHANNEL_ID)
    if alert_channel is None:
        return

    # 日本時間のタイムゾーン設定
    jst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(jst)

    # --- ① 通話開始（誰もいないチャンネルに誰かが入った） ---
    if after.channel is not None and len(after.channel.members) == 1:
        # 開始時間を記録
        call_start_times[after.channel.id] = now

        # 埋め込みメッセージ（Embed）を作成
        embed = discord.Embed(title="通話開始", color=0xff4d4d) # 赤色
        embed.add_field(name="チャンネル", value=after.channel.name, inline=True)
        embed.add_field(name="始めた人", value=member.display_name, inline=True)
        embed.add_field(name="開始時間", value=now.strftime('%Y/%m/%d %H:%M:%S'), inline=False)
        embed.set_thumbnail(url=member.display_avatar.url) # アイコンを表示

        # @everyone 付きで送信
        await alert_channel.send(content="@everyone", embed=embed)

    # --- ② 通話終了（チャンネルから誰もいなくなった） ---
    elif before.channel is not None and len(before.channel.members) == 0:
        # 開始時間を取得して削除
        start_time = call_start_times.pop(before.channel.id, None)
        
        # 埋め込みメッセージを作成
        embed = discord.Embed(title="通話終了", color=0x4d4dff) # 青色
        embed.add_field(name="チャンネル", value=before.channel.name, inline=False)

        if start_time:
            # 通話時間を計算
            duration = now - start_time
            # 秒以下の細かい数字をカット
            duration_str = str(duration).split('.')[0]
            embed.add_field(name="通話時間", value=duration_str, inline=False)
        else:
            embed.add_field(name="通話時間", value="不明（Bot再起動等のため）", inline=False)

        # メンション無しで送信
        await alert_channel.send(embed=embed)
# ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

# ▼▼▼ ポイント機能コマンド ▼▼▼

@tree.command(name="money", description="所持ポイントを確認")
@app_commands.allowed_installs(guilds=True, users=True)
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

# 管理者IDリスト（必要に応じて書き換えてください）
ADMIN_IDS = [] 

@tree.command(name="add", description="【管理】ポイント付与")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def add(interaction: discord.Interaction, user: discord.User, amount: int):
    # 管理者制限が必要ならコメントアウトを外す
    # if interaction.user.id not in ADMIN_IDS:
    #     await interaction.response.send_message("❌ 権限がありません。", ephemeral=True)
    #     return
    uid = user.id
    user_points[uid] = user_points.get(uid, 1000) + amount
    await interaction.response.send_message(f"✅ {user.mention} に {amount} pt 追加しました。")

@tree.command(name="remove", description="【管理】ポイント没収")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def remove(interaction: discord.Interaction, user: discord.User, amount: int):
    # if interaction.user.id not in ADMIN_IDS:
    #     await interaction.response.send_message("❌ 権限がありません。", ephemeral=True)
    #     return
    uid = user.id
    user_points[uid] = user_points.get(uid, 1000) - amount
    await interaction.response.send_message(f"🔻 {user.mention} から {amount} pt 没収しました。")

# Webサーバーを起動してからBotを起動
keep_alive()
client.run(TOKEN)
