import os
import random
import sqlite3
import asyncio
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands


# ==================================================
# 基本設定
# ==================================================

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="t",
    intents=intents,
    help_command=None
)


# ==================================================
# データベース
# ==================================================

db = sqlite3.connect("taka_games.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 0,
    last_daily TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bot_admins (
    user_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS announcement_admins (
    user_id INTEGER PRIMARY KEY
)
""")

db.commit()


# ==================================================
# コイン
# ==================================================

def get_coins(user_id):
    cursor.execute(
        "SELECT coins FROM users WHERE user_id = ?",
        (user_id,)
    )

    result = cursor.fetchone()

    if result is None:
        cursor.execute(
            "INSERT INTO users (user_id, coins, last_daily) VALUES (?, ?, ?)",
            (user_id, 0, None)
        )
        db.commit()
        return 0

    return result[0]


def add_coins(user_id, amount):
    get_coins(user_id)

    cursor.execute(
        "UPDATE users SET coins = coins + ? WHERE user_id = ?",
        (amount, user_id)
    )

    db.commit()


# ==================================================
# 権限
# ==================================================

def is_bot_admin(user_id):
    cursor.execute(
        "SELECT user_id FROM bot_admins WHERE user_id = ?",
        (user_id,)
    )

    return cursor.fetchone() is not None


def is_announcement_admin(user_id):
    cursor.execute(
        "SELECT user_id FROM announcement_admins WHERE user_id = ?",
        (user_id,)
    )

    return cursor.fetchone() is not None


# ==================================================
# 起動
# ==================================================

@bot.event
async def on_ready():
    print(f"ログイン完了: {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"スラッシュコマンド登録完了: {len(synced)}個")
    except Exception as e:
        print(f"スラッシュコマンド登録エラー: {e}")


# ==================================================
# 初回管理者
# t管理者 @ユーザー
# 1回だけ使用可能
# ==================================================

@bot.command(name="管理者")
async def first_admin(ctx, member: discord.Member = None):

    cursor.execute("SELECT COUNT(*) FROM bot_admins")
    count = cursor.fetchone()[0]

    if count > 0:
        await ctx.send(
            "❌ 初回管理者設定はすでに使用されています。"
        )
        return

    if member is None:
        await ctx.send(
            "❌ 使用方法：`t管理者 @ユーザー`"
        )
        return

    cursor.execute(
        "INSERT INTO bot_admins (user_id) VALUES (?)",
        (member.id,)
    )

    db.commit()

    await ctx.send(
        f"👑 {member.mention} をBot管理者に設定しました。\n"
        "🔒 初回管理者設定は使用済みになりました。"
    )


# ==================================================
# tコイン投げ
# ==================================================

@bot.command(name="コイン投げ")
async def coin(ctx):
    result = random.choice(["表", "裏"])

    await ctx.send(
        "🪙 **コイン投げ**\n"
        f"結果：**{result}**"
    )


# ==================================================
# tじゃんけん
# ==================================================

@bot.command(name="じゃんけん")
async def janken(ctx, hand=None):

    choices = ["グー", "チョキ", "パー"]

    if hand not in choices:
        await ctx.send(
            "❌ 使用方法：`tじゃんけん グー`"
        )
        return

    bot_hand = random.choice(choices)

    if hand == bot_hand:
        result = "🤝 あいこ！"

    elif (
        (hand == "グー" and bot_hand == "チョキ")
        or
        (hand == "チョキ" and bot_hand == "パー")
        or
        (hand == "パー" and bot_hand == "グー")
    ):
        result = "🎉 あなたの勝ち！"

    else:
        result = "😢 あなたの負け！"

    await ctx.send(
        f"あなた：**{hand}**\n"
        f"Taka Games：**{bot_hand}**\n\n"
        f"{result}"
    )


# ==================================================
# tサイコロ
# ==================================================

@bot.command(name="サイコロ")
async def dice(ctx):

    result = random.randint(1, 6)

    await ctx.send(
        f"🎲 サイコロの結果：**{result}**"
    )


# ==================================================
# tおみくじ
# ==================================================

@bot.command(name="おみくじ")
async def omikuji(ctx):

    result = random.choice([
        "大吉 🌟",
        "中吉 ✨",
        "小吉 🍀",
        "吉 👍",
        "末吉 🙂"
    ])

    await ctx.send(
        "⛩️ **おみくじ結果**\n"
        f"**{result}**"
    )


# ==================================================
# t残高
# ==================================================

@bot.command(name="残高")
async def balance(ctx):

    amount = get_coins(ctx.author.id)

    await ctx.send(
        f"💰 {ctx.author.mention} の残高："
        f"**{amount}コイン**"
    )


# ==================================================
# tお金確認
# ==================================================

@bot.command(name="お金確認")
async def check_money(ctx, member: discord.Member = None):

    member = member or ctx.author
    amount = get_coins(member.id)

    await ctx.send(
        f"💰 {member.mention} の残高："
        f"**{amount}コイン**"
    )


# ==================================================
# tデイリー
# 24時間に1回
# ==================================================

@bot.command(name="デイリー")
async def daily(ctx):

    user_id = ctx.author.id

    cursor.execute(
        "SELECT last_daily FROM users WHERE user_id = ?",
        (user_id,)
    )

    result = cursor.fetchone()

    now = datetime.now(timezone.utc)

    if result and result[0]:
        last_daily = datetime.fromisoformat(result[0])

        if now - last_daily < timedelta(hours=24):
            remaining = timedelta(hours=24) - (now - last_daily)
            hours = int(remaining.total_seconds() // 3600)
            minutes = int(
                (remaining.total_seconds() % 3600) // 60
            )

            await ctx.send(
                f"⏰ デイリーはまだ受け取れません。\n"
                f"次回まで：約 **{hours}時間{minutes}分**"
            )
            return

    add_coins(user_id, 100)

    cursor.execute(
        "UPDATE users SET last_daily = ? WHERE user_id = ?",
        (now.isoformat(), user_id)
    )

    db.commit()

    await ctx.send(
        "🎁 **デイリー報酬**\n"
        "100コインを獲得しました！\n"
        f"💰 現在：**{get_coins(user_id)}コイン**"
    )


# ==================================================
# tランキング
# ==================================================

@bot.command(name="ランキング")
async def ranking(ctx):

    cursor.execute(
        "SELECT user_id, coins FROM users "
        "ORDER BY coins DESC LIMIT 10"
    )

    results = cursor.fetchall()

    if not results:
        await ctx.send(
            "📊 まだランキングデータがありません。"
        )
        return

    text = "🏆 **コインランキング**\n\n"

    for i, (user_id, amount) in enumerate(results, 1):
        text += (
            f"**{i}位** <@{user_id}> "
            f"💰 {amount}コイン\n"
        )

    await ctx.send(text)


# ==================================================
# アナウンス送信処理
# ==================================================

async def send_announcement(
    channels,
    content,
    sender,
    delay
):

    message_text = (
        "# 📢 **アナウンスが届きました**\n\n"
        f"**{content}**\n\n"
        f"-# 送信者：{sender.mention}"
    )

    async def send_one(channel):

        try:
            message = await channel.send(message_text)

            if delay > 0:
                await asyncio.sleep(delay)

            await message.delete()

        except discord.Forbidden:
            print(
                f"権限不足: #{channel.name}"
            )

        except discord.HTTPException as e:
            print(
                f"送信エラー: {e}"
            )

    await asyncio.gather(
        *(send_one(channel) for channel in channels)
    )


# ==================================================
# tアナウンス
# ==================================================

@bot.command(name="アナウンス")
async def prefix_announcement(ctx, delay: int = None, *args):

    if not (
        is_bot_admin(ctx.author.id)
        or is_announcement_admin(ctx.author.id)
    ):
        await ctx.send(
            "❌ アナウンス権限がありません。"
        )
        return

    if delay is None:
        await ctx.send(
            "❌ 使用方法：\n"
            "`tアナウンス 10 #お知らせ 内容`"
        )
        return

    if delay < 0:
        await ctx.send(
            "❌ 削除までの秒数は0以上にしてください。"
        )
        return

    channels = [
        channel
        for channel in ctx.message.channel_mentions
        if isinstance(channel, discord.TextChannel)
    ]

    if not channels:
        await ctx.send(
            "❌ 送信先チャンネルを指定してください。"
        )
        return

    content_parts = []

    for arg in args:
        if not arg.startswith("<#"):
            content_parts.append(arg)

    content = " ".join(content_parts).strip()

    if not content:
        await ctx.send(
            "❌ アナウンス内容を入力してください。"
        )
        return

    await send_announcement(
        channels,
        content,
        ctx.author,
        delay
    )


# ==================================================
# /announce
# /アナウンスの代わり
# ==================================================

@bot.tree.command(
    name="announce",
    description="アナウンスを送信します"
)
@app_commands.describe(
    content="アナウンス内容",
    channel1="送信先チャンネル1",
    channel2="送信先チャンネル2",
    channel3="送信先チャンネル3",
    delay="削除までの秒数"
)
async def slash_announcement(
    interaction: discord.Interaction,
    content: str,
    channel1: discord.TextChannel,
    delay: int,
    channel2: discord.TextChannel = None,
    channel3: discord.TextChannel = None
):

    if not (
        is_bot_admin(interaction.user.id)
        or is_announcement_admin(interaction.user.id)
    ):
        await interaction.response.send_message(
            "❌ アナウンス権限がありません。",
            ephemeral=True
        )
        return

    if delay < 0:
        await interaction.response.send_message(
            "❌ 秒数は0以上にしてください。",
            ephemeral=True
        )
        return

    channels = [channel1]

    if channel2 is not None:
        channels.append(channel2)

    if channel3 is not None:
        channels.append(channel3)

    await interaction.response.send_message(
        "📢 アナウンスを送信しました。",
        ephemeral=True
    )

    await send_announcement(
        channels,
        content,
        interaction.user,
        delay
    )


# ==================================================
# /bot-admin-add
# Bot管理者付与
# ==================================================

@bot.tree.command(
    name="bot-admin-add",
    description="Bot管理者を追加します"
)
@app_commands.describe(
    member="Bot管理者にするユーザー"
)
async def bot_admin_add(
    interaction: discord.Interaction,
    member: discord.Member
):

    if not is_bot_admin(interaction.user.id):
        await interaction.response.send_message(
            "❌ Bot管理者のみ使用できます。",
            ephemeral=True
        )
        return

    cursor.execute(
        "INSERT OR IGNORE INTO bot_admins (user_id) VALUES (?)",
        (member.id,)
    )

    db.commit()

    await interaction.response.send_message(
        f"👑 {member.mention} をBot管理者に追加しました。"
    )


# ==================================================
# /bot-admin-remove
# ==================================================

@bot.tree.command(
    name="bot-admin-remove",
    description="Bot管理者を削除します"
)
@app_commands.describe(
    member="Bot管理者から外すユーザー"
)
async def bot_admin_remove(
    interaction: discord.Interaction,
    member: discord.Member
):

    if not is_bot_admin(interaction.user.id):
        await interaction.response.send_message(
            "❌ Bot管理者のみ使用できます。",
            ephemeral=True
        )
        return

    cursor.execute(
        "DELETE FROM bot_admins WHERE user_id = ?",
        (member.id,)
    )

    db.commit()

    await interaction.response.send_message(
        f"👑 {member.mention} のBot管理者権限を削除しました。"
    )


# ==================================================
# /announcement-admin-add
# ==================================================

@bot.tree.command(
    name="announcement-admin-add",
    description="アナウンス権限を付与します"
)
@app_commands.describe(
    member="アナウンス権限を付与するユーザー"
)
async def announcement_admin_add(
    interaction: discord.Interaction,
    member: discord.Member
):

    if not is_bot_admin(interaction.user.id):
        await interaction.response.send_message(
            "❌ Bot管理者のみ使用できます。",
            ephemeral=True
        )
        return

    cursor.execute(
        "INSERT OR IGNORE INTO announcement_admins "
        "(user_id) VALUES (?)",
        (member.id,)
    )

    db.commit()

    await interaction.response.send_message(
        f"📣 {member.mention} にアナウンス権限を付与しました。"
    )


# ==================================================
# /announcement-admin-remove
# ==================================================

@bot.tree.command(
    name="announcement-admin-remove",
    description="アナウンス権限を削除します"
)
@app_commands.describe(
    member="アナウンス権限を削除するユーザー"
)
async def announcement_admin_remove(
    interaction: discord.Interaction,
    member: discord.Member
):

    if not is_bot_admin(interaction.user.id):
        await interaction.response.send_message(
            "❌ Bot管理者のみ使用できます。",
            ephemeral=True
        )
        return

    cursor.execute(
        "DELETE FROM announcement_admins WHERE user_id = ?",
        (member.id,)
    )

    db.commit()

    await interaction.response.send_message(
        f"📣 {member.mention} のアナウンス権限を削除しました。"
    )


# ==================================================
# /money-add
# ==================================================

@bot.tree.command(
    name="money-add",
    description="ユーザーにコインを追加します"
)
@app_commands.describe(
    member="コインを追加するユーザー",
    amount="追加するコイン数"
)
async def money_add(
    interaction: discord.Interaction,
    member: discord.Member,
    amount: int
):

    if not is_bot_admin(interaction.user.id):
        await interaction.response.send_message(
            "❌ Bot管理者のみ使用できます。",
            ephemeral=True
        )
        return

    if amount <= 0:
        await interaction.response.send_message(
            "❌ 1以上を指定してください。",
            ephemeral=True
        )
        return

    add_coins(member.id, amount)

    await interaction.response.send_message(
        f"💰 {member.mention} に"
        f" **{amount}コイン**追加しました。"
    )


# ==================================================
# tコマンド一覧
# ==================================================

@bot.command(name="コマンド一覧")
async def command_list(ctx):

    await ctx.send(
        "# 🎮 **Taka Games コマンド一覧**\n\n"

        "## 🎮 ゲーム\n"
        "`tコイン投げ`\n"
        "`tじゃんけん グー/チョキ/パー`\n"
        "`tサイコロ`\n"
        "`tおみくじ`\n\n"

        "## 💰 コイン\n"
        "`t残高`\n"
        "`tお金確認 @ユーザー`\n"
        "`tデイリー`\n"
        "`tランキング`\n\n"

        "## 📢 アナウンス\n"
        "`tアナウンス 10 #チャンネル 内容`\n"
        "`/announce`\n\n"

        "## 👑 Bot管理者専用\n"
        "`/bot-admin-add`\n"
        "`/bot-admin-remove`\n"
        "`/announcement-admin-add`\n"
        "`/announcement-admin-remove`\n"
        "`/money-add`\n\n"

        "## 🔐 初回設定\n"
        "`t管理者 @ユーザー`\n"
        "※初回の1回のみ使用できます。"
    )


# ==================================================
# エラー処理
# ==================================================

@bot.event
async def on_command_error(ctx, error):

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            "❌ 必要な項目が足りません。"
        )

    elif isinstance(error, commands.MemberNotFound):
        await ctx.send(
            "❌ ユーザーが見つかりません。"
        )

    elif isinstance(error, commands.BadArgument):
        await ctx.send(
            "❌ 入力内容を確認してください。"
        )

    elif isinstance(error, commands.CommandNotFound):
        pass

    else:
        print(f"エラー: {error}")


# ==================================================
# 起動
# ==================================================

if not TOKEN:
    print("❌ DISCORD_TOKEN が設定されていません。")
else:
    bot.run(TOKEN)