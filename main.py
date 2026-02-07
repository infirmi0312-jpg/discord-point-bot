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
ADMIN_IDS = [] # あなたのユーザーIDを入れておくとsyncコマンドが使えます
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

# ▼▼▼ Intentsの設定（ここが重要） ▼▼▼
intents = discord.Intents.default()
intents.voice_states = True # 通話状態の取得に必須
intents.members = True      # ★メンバー名・アイコン取得に必須
intents.message_content = True # メッセージ内容の取得（念のため）

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# 簡易データベース
user_points = {}
call_start_times = {}

@client.event
async def on_ready():
    # ★注意: ここでの tree.sync() は削除しました。
    # 起動のたびに同期すると429エラーになりやすいためです。
    print(f"ログインしました: {client.user}", flush=True)
    await client.change_presence(activity=discord.Game(name="/money で所持ポイントを確認"))

# ★新機能: コマンドを手動で同期するための隠しコマンド
# チャットで「!sync」と打つと同期されます（管理者のみ推奨）
@client.event
async def on_message(message):
    if message.content == "!sync":
        # 必要ならここで ADMIN_IDS チェックを入れてください
        # if message.author.id not in ADMIN_IDS: return
        
        await tree.sync()
        await message.channel.send("コマンドを同期しました！")

# ▼▼▼ 通話お知らせ機能 ▼▼▼
@client.event
async def on_voice_state_update(member, before, after):
    # Bot自身の移動は無視
    if member.bot:
        return

    alert_channel = client.get_channel(ALERT_CHANNEL_ID)
    if alert_channel is None:
        print("エラー: 通知チャンネルが見つかりません")
        return

    jst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(jst)

    # 通話開始（誰もいないチャンネルに誰かが入った）
    if after.channel is not None and len(after.channel.members) == 1:
        call_start_times[after.channel.id] = now
        
        # メンバー情報が正しく取れているか確認
        name = member.display_name if member else "不明なユーザー"
        avatar_url = member.display_avatar.url if member else None

        embed = discord.Embed(title="通話開始", color=0xff4d4d)
        embed.add_field(name="チャンネル", value=after.channel.name, inline=True)
        embed.add_field(name="始めた人", value=name, inline=True)
        embed.add_field(name="開始時間", value=now.strftime('%Y/%m/%d %H:%M:%S'), inline=False)
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        
        try:
            await alert_channel.send(content="@everyone", embed=embed)
        except Exception as e:
            print(f"送信エラー: {e}")

    # 通話終了（チャンネルから誰もいなくなった）
    elif before.channel is not None and len(before.channel.members) == 0:
        start_time = call_start_times.pop(before.channel.id, None)
        embed = discord.Embed(title="通話終了", color=0x4d4dff)
        embed.add_field(name="チャンネル", value=before.channel.name, inline=False)
        
        if start_time:
            duration = now - start_time
            # 秒以下の処理
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            duration_str = f"{hours}時間{minutes}分{seconds}秒" if hours > 0 else f"{minutes}分{seconds}秒"
            
            embed.add_field(name="通話時間", value=duration_str, inline=False)
        else:
            embed.add_field(name="通話時間", value="不明", inline=False)
            
        try:
            await alert_channel.send(embed=embed)
        except Exception as e:
            print(f"送信エラー: {e}")

# --- 以下、ポイント機能コマンド（変更なし） ---
@tree.command(name="money", description="所持ポイントを確認")
@app_commands.describe(user="確認したい相手（指定しない場合は自分）")
async def money(interaction: discord.Interaction, user: discord.User = None):
    target = user or interaction.user
    uid = target.id
    pt = user_points.get(uid, 1000)
    await interaction.response.send_message(f"💰 {target.mention} さんの所持ポイント: {pt} pt")

@tree.command(name="give", description="自分のポイントを相手に渡す")
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

@tree.command(name="transfer", description="ユーザー間のポイントを移動")
@app_commands.describe(source="没収する人", destination="渡す人", amount="金額")
async def transfer(interaction: discord.Interaction, source: discord.User, destination: discord.User, amount: int):
    src_id = source.id
    dst_id = destination.id
    src_pt = user_points.get(src_id, 1000)
    user_points[src_id] = src_pt 

    if amount <= 0:
        await interaction.response.send_message("❌ 1以上の数値を指定してください。", ephemeral=True)
        return
    if src_pt < amount:
        await interaction.response.send_message(f"❌ {source.name} さんのポイントが足りません（所持: {src_pt} pt）", ephemeral=True)
        return

    user_points[src_id] -= amount
    user_points[dst_id] = user_points.get(dst_id, 1000) + amount
    await interaction.response.send_message(f"🔄 {source.mention} から {destination.mention} へ {amount} pt 移動させました。")

@tree.command(name="add", description="ポイントを付与")
async def add(interaction: discord.Interaction, user: discord.User, amount: int):
    uid = user.id
    user_points[uid] = user_points.get(uid, 1000) + amount
    await interaction.response.send_message(f"✅ {user.mention} に {amount} pt 追加しました。")

@tree.command(name="remove", description="ポイントを没収")
async def remove(interaction: discord.Interaction, user: discord.User, amount: int):
    uid = user.id
    user_points[uid] = user_points.get(uid, 1000) - amount
    await interaction.response.send_message(f"🔻 {user.mention} から {amount} pt 没収しました。")

keep_alive()
client.run(TOKEN)
