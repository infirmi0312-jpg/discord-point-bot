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
APP_ID = "1451611154861523024" 
ALERT_CHANNEL_ID = 1449751244351733831
# ==========================================

# --- Webサーバー機能 ---
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

# ▼▼▼ Intentsの設定 ▼▼▼
intents = discord.Intents.default()
intents.voice_states = True
intents.members = True      # メンバー情報の取得に必須
intents.message_content = True 

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# 簡易データベース
user_points = {}
call_start_times = {}

@client.event
async def on_ready():
    # ★重要: ここにあった await tree.sync() は削除しました！
    print(f"ログインしました: {client.user}", flush=True)
    await client.change_presence(activity=discord.Game(name="/money で所持ポイントを確認"))

# ★救済措置: コマンドが反映されない時だけ使う「同期コマンド」
@client.event
async def on_message(message):
    if message.content == "!sync":
        try:
            await tree.sync()
            await message.channel.send("✅ コマンドを同期しました！")
            print("コマンド同期完了")
        except Exception as e:
            await message.channel.send(f"❌ 同期エラー: {e}")

# ▼▼▼ 通話お知らせ機能 ▼▼▼
@client.event
async def on_voice_state_update(member, before, after):
    if member.bot: return

    alert_channel = client.get_channel(ALERT_CHANNEL_ID)
    if not alert_channel: return

    jst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(jst)

    # 通話開始
    if after.channel is not None and len(after.channel.members) == 1:
        call_start_times[after.channel.id] = now
        
        embed = discord.Embed(title="通話開始", color=0xff4d4d)
        embed.add_field(name="チャンネル", value=after.channel.name, inline=True)
        embed.add_field(name="始めた人", value=member.display_name, inline=True)
        embed.add_field(name="開始時間", value=now.strftime('%Y/%m/%d %H:%M:%S'), inline=False)
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)
        
        try:
            await alert_channel.send(content="@everyone", embed=embed)
        except:
            pass

    # 通話終了
    elif before.channel is not None and len(before.channel.members) == 0:
        start_time = call_start_times.pop(before.channel.id, None)
        embed = discord.Embed(title="通話終了", color=0x4d4dff)
        embed.add_field(name="チャンネル", value=before.channel.name, inline=False)
        
        if start_time:
            duration = now - start_time
            total_seconds = int(duration.total_seconds())
            m, s = divmod(total_seconds, 60)
            h, m = divmod(m, 60)
            time_str = f"{h}時間{m}分{s}秒" if h else f"{m}分{s}秒"
            embed.add_field(name="通話時間", value=time_str, inline=False)
        else:
            embed.add_field(name="通話時間", value="不明", inline=False)
            
        try:
            await alert_channel.send(embed=embed)
        except:
            pass

# --- ポイント機能（省略せずそのまま使えます） ---
@tree.command(name="money", description="所持ポイントを確認")
async def money(interaction: discord.Interaction, user: discord.User = None):
    target = user or interaction.user
    pt = user_points.get(target.id, 1000)
    await interaction.response.send_message(f"💰 {target.mention} さんの所持ポイント: {pt} pt")

@tree.command(name="give", description="送金")
async def give(interaction: discord.Interaction, user: discord.User, amount: int):
    sender_id = interaction.user.id
    receiver_id = user.id
    sender_pt = user_points.get(sender_id, 1000)
    if amount <= 0 or sender_pt < amount:
        await interaction.response.send_message("❌ 金額が無効か不足しています", ephemeral=True)
        return
    user_points[sender_id] = sender_pt - amount
    user_points[receiver_id] = user_points.get(receiver_id, 1000) + amount
    await interaction.response.send_message(f"💸 {amount} pt 送金しました")

# (他のコマンドもそのままでOK)

if __name__ == "__main__":
    keep_alive()
    client.run(TOKEN)
