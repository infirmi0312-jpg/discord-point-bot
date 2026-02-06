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

# ★通知を送りたいチャンネルのID（数字のみ）
ALERT_CHANNEL_ID = 1449751244351733831

# ★管理コマンドを使える人のID（必要なら書き換えてください）
ADMIN_IDS = [] 
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
intents.voice_states = True
intents.members = True  # ★ここを追加（メンバー情報を取得するために必須）
intents.message_content = True # ★念のため追加
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# 簡易データベース
user_points = {}
call_start_times = {}

@client.event
async def on_ready():
    await tree.sync()
    print(f"ログインしました: {client.user}", flush=True)
    await client.change_presence(activity=discord.Game(name="/money で所持ポイントを確認"))

# ▼▼▼ 通話お知らせ機能 ▼▼▼
@client.event
async def on_voice_state_update(member, before, after):
    alert_channel = client.get_channel(ALERT_CHANNEL_ID)
    if alert_channel is None:
        return

    jst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(jst)

    # 通話開始
    if after.channel is not None and len(after.channel.members) == 1:
        call_start_times[after.channel.id] = now
        embed = discord.Embed(title="通話開始", color=0xff4d4d)
        embed.add_field(name="チャンネル", value=after.channel.name, inline=True)
        embed.add_field(name="始めた人", value=member.display_name, inline=True)
        embed.add_field(name="開始時間", value=now.strftime('%Y/%m/%d %H:%M:%S'), inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        await alert_channel.send(content="@everyone", embed=embed)

    # 通話終了
    elif before.channel is not None and len(before.channel.members) == 0:
        start_time = call_start_times.pop(before.channel.id, None)
        embed = discord.Embed(title="通話終了", color=0x4d4dff)
        embed.add_field(name="チャンネル", value=before.channel.name, inline=False)
        if start_time:
            duration = now - start_time
            duration_str = str(duration).split('.')[0]
            embed.add_field(name="通話時間", value=duration_str, inline=False)
        else:
            embed.add_field(name="通話時間", value="不明", inline=False)
        await alert_channel.send(embed=embed)

# ▼▼▼ ポイント機能コマンド ▼▼▼

# 【変更点】相手を指定できるようにしました
@tree.command(name="money", description="所持ポイントを確認")
@app_commands.describe(user="確認したい相手（指定しない場合は自分）")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def money(interaction: discord.Interaction, user: discord.User = None):
    # userが指定されていればその人、いなければ自分(interaction.user)を対象にする
    target = user or interaction.user
    
    uid = target.id
    pt = user_points.get(uid, 1000)
    await interaction.response.send_message(f"💰 {target.mention} さんの所持ポイント: {pt} pt")

@tree.command(name="give", description="自分のポイントを相手に渡す")
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

# 【新機能】AさんからBさんへポイントを移動させるコマンド
@tree.command(name="transfer", description="ユーザー間のポイントを移動")
@app_commands.describe(source="没収する人", destination="渡す人", amount="金額")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def transfer(interaction: discord.Interaction, source: discord.User, destination: discord.User, amount: int):
    # 管理者制限が必要ならコメントアウトを外す
    # if interaction.user.id not in ADMIN_IDS:
    #     await interaction.response.send_message("❌ 権限がありません。", ephemeral=True)
    #     return

    src_id = source.id
    dst_id = destination.id
    
    # 元の持ち主のポイントを確認
    src_pt = user_points.get(src_id, 1000)
    user_points[src_id] = src_pt # 初期化用

    if amount <= 0:
        await interaction.response.send_message("❌ 1以上の数値を指定してください。", ephemeral=True)
        return
    
    # 強制移動でも、無い袖は振れないようにする場合（足りなければエラー）
    if src_pt < amount:
        await interaction.response.send_message(f"❌ {source.name} さんのポイントが足りません（所持: {src_pt} pt）", ephemeral=True)
        return

    # 移動処理
    user_points[src_id] -= amount
    user_points[dst_id] = user_points.get(dst_id, 1000) + amount
    
    await interaction.response.send_message(f"🔄 {source.mention} から {destination.mention} へ {amount} pt 移動させました。")

@tree.command(name="add", description="ポイントを付与")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def add(interaction: discord.Interaction, user: discord.User, amount: int):
    # if interaction.user.id not in ADMIN_IDS:
    #     await interaction.response.send_message("❌ 権限がありません。", ephemeral=True)
    #     return
    uid = user.id
    user_points[uid] = user_points.get(uid, 1000) + amount
    await interaction.response.send_message(f"✅ {user.mention} に {amount} pt 追加しました。")

@tree.command(name="remove", description="ポイントを没収")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def remove(interaction: discord.Interaction, user: discord.User, amount: int):
    # if interaction.user.id not in ADMIN_IDS:
    #     await interaction.response.send_message("❌ 権限がありません。", ephemeral=True)
    #     return
    uid = user.id
    user_points[uid] = user_points.get(uid, 1000) - amount
    await interaction.response.send_message(f"🔻 {user.mention} から {amount} pt 没収しました。")

if __name__ == "__main__":
    keep_alive()
    
    # Tokenがない場合のエラーチェック
    if not TOKEN:
        print("エラー: 環境変数 'TOKEN' が読み込めませんでした。", flush=True)
    else:
        try:
            client.run(TOKEN)
        except discord.errors.PrivilegedIntentsRequired:
            print("エラー: Developer Portalで 'Server Members Intent' がONになっていません！", flush=True)
        except discord.errors.LoginFailure:
            print("エラー: Tokenが間違っています。Developer Portalで再発行して環境変数を更新してください。", flush=True)
        except Exception as e:
            print(f"その他のエラーが発生しました: {e}", flush=True)
