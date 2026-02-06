import discord
from discord import app_commands
import os
from flask import Flask
from threading import Thread
import datetime
import sys

# ==========================================
# 設定エリア
# ==========================================
TOKEN = os.getenv("TOKEN")
APP_ID = "1451611154861523024" 
ALERT_CHANNEL_ID = 1449751244351733831
ADMIN_IDS = [] 
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

# ★★★ ここが最重要（アプデ対応） ★★★
intents = discord.Intents.default()
intents.voice_states = True  # 通話状態の取得
intents.members = True       # メンバー情報の取得（これが無いと通知が来ない）
intents.message_content = True # メッセージ内容の取得

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# 簡易データベース
user_points = {}
call_start_times = {}

@client.event
async def on_ready():
    try:
        await tree.sync()
        print(f"✅ ログイン成功: {client.user.name} (ID: {client.user.id})", flush=True)
        print(f"✅ 導入サーバー数: {len(client.guilds)}", flush=True)
        
        # チャンネルが見えているかテスト
        channel = client.get_channel(ALERT_CHANNEL_ID)
        if channel:
            print(f"✅ 通知チャンネル確認OK: {channel.name}", flush=True)
        else:
            print(f"⚠️ エラー: 通知チャンネル(ID: {ALERT_CHANNEL_ID})が見つかりません。Botがそのサーバーにいないか、権限がありません。", flush=True)
            
        await client.change_presence(activity=discord.Game(name="/money で所持ポイントを確認"))
    except Exception as e:
        print(f"❌ 起動時エラー: {e}", flush=True)

# ▼▼▼ 通話お知らせ機能 ▼▼▼
@client.event
async def on_voice_state_update(member, before, after):
    # Bot自身が動いた場合は無視
    if member.bot:
        return

    alert_channel = client.get_channel(ALERT_CHANNEL_ID)
    if alert_channel is None:
        return

    jst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(jst)

    # 通話開始（チャンネルに入った、かつ、そのチャンネルに1人だけ＝最初の1人）
    if after.channel is not None and len(after.channel.members) == 1:
        call_start_times[after.channel.id] = now
        embed = discord.Embed(title="📞 通話開始", color=0xff4d4d)
        embed.add_field(name="チャンネル", value=after.channel.name, inline=True)
        embed.add_field(name="始めた人", value=member.display_name, inline=True)
        embed.add_field(name="開始時間", value=now.strftime('%H:%M'), inline=False)
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)
        
        try:
            await alert_channel.send(content="@everyone", embed=embed)
            print(f"通知送信: {member.display_name} -> {after.channel.name}", flush=True)
        except Exception as e:
            print(f"送信エラー: {e}", flush=True)

    # 通話終了（チャンネルから出た、かつ、誰もいなくなった）
    elif before.channel is not None and len(before.channel.members) == 0:
        start_time = call_start_times.pop(before.channel.id, None)
        embed = discord.Embed(title="🔚 通話終了", color=0x4d4dff)
        embed.add_field(name="チャンネル", value=before.channel.name, inline=False)
        
        if start_time:
            duration = now - start_time
            # 秒数を計算して整形
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours > 0:
                duration_str = f"{hours}時間{minutes}分{seconds}秒"
            else:
                duration_str = f"{minutes}分{seconds}秒"
            embed.add_field(name="通話時間", value=duration_str, inline=False)
        else:
            embed.add_field(name="通話時間", value="不明", inline=False)
            
        await alert_channel.send(embed=embed)

# ▼▼▼ ポイント機能コマンド（変更なし） ▼▼▼
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

if __name__ == "__main__":
    keep_alive()
    if not TOKEN:
        print("❌ エラー: TOKENが設定されていません。", flush=True)
    else:
        try:
            client.run(TOKEN)
        except discord.errors.HTTPException as e:
            if e.status == 429:
                print("⛔ Cloudflare/Discordにより一時的にブロックされています。1時間ほどBotを停止してください。", flush=True)
            else:
                print(f"❌ HTTPエラー: {e}", flush=True)
        except Exception as e:
            print(f"❌ 実行エラー: {e}", flush=True)
