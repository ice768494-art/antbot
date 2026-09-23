import os
import json
import asyncio
import urllib.parse
import logging
import traceback
import humanize
from bot import Bot
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, Forbidden
from pyrogram.enums import ChatAction
from pyrogram import __version__
from helper.helper_func import *



lock = asyncio.Lock()
DATABASE_CHANNEL = -1003133927591
ADMINS = [6299192020]
INDEX_FILE = "index.json"
BOT_USERNAME = "Occoccicfx_bot"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load cache
if os.path.exists(INDEX_FILE):
    with open(INDEX_FILE, "r") as f:
        FILE_INDEX = json.load(f)
else:
    FILE_INDEX = []

# ───────────── INDEX COMMAND ─────────────
@Bot.on_callback_query(filters.regex(r"^index$"))
async def index_files(bot, query: CallbackQuery):
    if lock.locked():
        return await query.message.reply("⏳ Another indexing is in progress. Please wait.")

    last_msg = await bot.ask(
        chat_id=query.message.chat.id,
        text="<blockquote expandable>Now forward the last message from the channel (not as copy).</blockquote>",
        filters=filters.text,
        timeout=60
    )

    try:
        chat_id = (
            last_msg.forward_from_chat.username
            if last_msg.forward_from_chat.username
            else last_msg.forward_from_chat.id
        )
        last_msg_id = last_msg.forward_from_message_id
    except Exception as e:
        return await last_msg.reply(f"❌ Invalid message: {e}")

    status = await query.message.reply("📦 Indexing started...")
    total_files = 0
    new_index = []

    async with lock:
        for i in range(1, last_msg_id + 1):
            try:
                m = await bot.get_messages(chat_id, i)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                continue
            except Exception:
                continue

            if not (m.document or m.video or m.audio):
                continue

            media = m.document or m.video or m.audio
            caption = m.caption or media.file_name or "Untitled File"
            size = round(media.file_size / 1048576, 2)

            new_index.append({"title": f"[{size} MB] {caption}", "id": m.id})
            total_files += 1

            if total_files % 25 == 0:
                await status.edit(f"📄 Indexed {total_files} files...")

    FILE_INDEX.clear()
    FILE_INDEX.extend(new_index)
    with open(INDEX_FILE, "w") as f:
        json.dump(FILE_INDEX, f, indent=2)

    await status.edit(f"✅ Indexed {total_files} files successfully!")
# ───────────── SEARCH COMMAND ─────────────
@Bot.on_message(filters.group & filters.command("search"))
@force_sub
async def search_files(bot, message):
    if len(message.command) < 2:
        return await message.reply("<blockquote>how to use:</blockquote>\n \n Example:\n Usage: `/search <Anime_name> \n /search Attack on Titan`", quote=True)

    query = " ".join(message.command[1:]).lower()
    results = [f for f in FILE_INDEX if query in f["title"].lower()]

    if not results:
        return await message.reply("❌ No results found.", quote=True)

    sent_msg = await send_results_page(bot, message.chat.id, results, query, 0, message.from_user.id, "all", None)

    # Auto delete after 5 minutes
    await asyncio.sleep(300)
    try:
        await sent_msg.delete()
    except:
        pass

# ───────────── DISPLAY RESULTS ─────────────
async def send_results_page(bot, chat_id, results, query, page, user_id, quality_filter, existing_msg):
    PER_PAGE = 7
    start = page * PER_PAGE
    end = start + PER_PAGE

    filtered = results
    if quality_filter != "all":
        filtered = [f for f in results if quality_filter in f["title"].lower()]

    current_results = filtered[start:end]
    total_pages = (len(filtered) - 1) // PER_PAGE + 1 if filtered else 1

    buttons = [
        [InlineKeyboardButton(text=f["title"][:60], callback_data=f"get|{f['id']}|{user_id}")]
        for f in current_results
    ]

    # Add filter buttons
    filter_row = [
        InlineKeyboardButton("480p", callback_data=f"filter|480p|{urllib.parse.quote(query)}|{page}|{user_id}"),
        InlineKeyboardButton("720p", callback_data=f"filter|720p|{urllib.parse.quote(query)}|{page}|{user_id}"),
        InlineKeyboardButton("1080p", callback_data=f"filter|1080p|{urllib.parse.quote(query)}|{page}|{user_id}"),
    ]
    buttons.insert(0, filter_row)

    # Add Send All button
    buttons.insert(1, [InlineKeyboardButton("📤 Send All", callback_data=f"sendall|{page}|{urllib.parse.quote(query)}|{user_id}|{quality_filter}")])

    # Navigation
    nav_buttons = []
    if start > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"page|{page-1}|{urllib.parse.quote(query)}|{user_id}|{quality_filter}"))
    if end < len(filtered):
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"page|{page+1}|{urllib.parse.quote(query)}|{user_id}|{quality_filter}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    text = f"🔍 Results for **{query}** ({quality_filter})\n📄 Page {page+1}/{total_pages}\n📦 Total files: {len(filtered)}\n\n Note:\n\n <blockquote expandable>The Message should be deleted in 5 minutes So kindly asking you to Get file faster</blockquote>"

    markup = InlineKeyboardMarkup(buttons)
    if existing_msg:
        await existing_msg.edit_text(text, reply_markup=markup)
        return existing_msg
    else:
        return await bot.send_message(chat_id, text, reply_markup=markup)

# ───────────── PAGE NAVIGATION ─────────────
@Bot.on_callback_query(filters.regex(r"^page\|"))
async def page_callback(bot, query: CallbackQuery):
    try:
        _, page, query_text, user_id, quality_filter = query.data.split("|", 4)
        if str(query.from_user.id) != str(user_id):
            return await query.answer("⚠️ Not your results!", show_alert=True)

        results = [f for f in FILE_INDEX if urllib.parse.unquote(query_text) in f["title"].lower()]
        await send_results_page(bot, query.message.chat.id, results, urllib.parse.unquote(query_text),
                                int(page), user_id, quality_filter, query.message)
    except Exception as e:
        logger.error(traceback.format_exc())
        await query.answer("⚠️ Error while navigating.", show_alert=True)

# ───────────── QUALITY FILTER ─────────────
@Bot.on_callback_query(filters.regex(r"^filter\|"))
async def filter_callback(bot, query: CallbackQuery):
    try:
        _, quality, query_text, page, user_id = query.data.split("|", 4)
        if str(query.from_user.id) != str(user_id):
            return await query.answer("⚠️ Not your results!", show_alert=True)

        results = [f for f in FILE_INDEX if urllib.parse.unquote(query_text) in f["title"].lower()]
        await send_results_page(bot, query.message.chat.id, results, urllib.parse.unquote(query_text),
                                int(page), user_id, quality, query.message)
    except Exception as e:
        logger.error(traceback.format_exc())
        await query.answer("⚠️ Error while filtering.", show_alert=True)


# ───────────── SEND SINGLE FILE ─────────────
@Client.on_callback_query(filters.regex(r"^get\|"))
async def send_file(bot, query: CallbackQuery):
    try:
        _, msg_id, user_id = query.data.split("|")
        if str(query.from_user.id) != str(user_id):
            return await query.answer("⚠️ Not your result!", show_alert=True)

        await bot.send_chat_action(query.from_user.id, ChatAction.UPLOAD_DOCUMENT)

        # Try sending message with floodwait handling
        try:
            msg = await bot.copy_message(
                chat_id=query.from_user.id,
                from_chat_id=DATABASE_CHANNEL,
                message_id=int(msg_id)
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            msg = await bot.copy_message(
                chat_id=query.from_user.id,
                from_chat_id=DATABASE_CHANNEL,
                message_id=int(msg_id)
            )

        await query.answer("📤 File Sent to your DM!", show_alert=True)

        # Auto delete after given time
        if bot.auto_del > 0:
            enter = f"start get_{msg_id}"
            info_msg = await bot.send_message(
                query.from_user.id,
                f"<blockquote expandable>⚠️ This file will auto-delete in {humanize.naturaldelta(bot.auto_del)}. Forward it to your Saved Messages!</blockquote>"
            )
            asyncio.create_task(delete_files([msg], bot, info_msg, enter))

    except Forbidden:
        await query.answer(f"📩 Start the bot first!\n👉 t.me/{BOT_USERNAME}", show_alert=True)
    except Exception as e:
        print(traceback.format_exc())
        await query.answer(f"❌ Error: {e}", show_alert=True)


# ───────────── SEND ALL FILES ─────────────
@Client.on_callback_query(filters.regex(r"^sendall\|"))
async def send_all(bot, query: CallbackQuery):
    try:
        _, page, query_text, user_id, quality_filter = query.data.split("|", 4)
        if str(query.from_user.id) != str(user_id):
            return await query.answer("⚠️ Not your results!", show_alert=True)

        results = [
            f for f in FILE_INDEX
            if urllib.parse.unquote(query_text).lower() in f["title"].lower()
        ]
        if quality_filter != "all":
            results = [f for f in results if quality_filter.lower() in f["title"].lower()]

        PER_PAGE = 7
        start = int(page) * PER_PAGE
        end = start + PER_PAGE
        selected = results[start:end]

        sent_msgs = []
        for f in selected:
            try:
                msg = await bot.copy_message(
                    chat_id=query.from_user.id,
                    from_chat_id=DATABASE_CHANNEL,
                    message_id=f["id"]
                )
                sent_msgs.append(msg)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                msg = await bot.copy_message(
                    chat_id=query.from_user.id,
                    from_chat_id=DATABASE_CHANNEL,
                    message_id=f["id"]
                )
                sent_msgs.append(msg)
            except Exception as e:
                logger.warning(f"Failed to send message {f['id']}: {e}")
                continue

        await query.answer(f"📦 Sent {len(sent_msgs)} {quality_filter} files!", show_alert=True)

        # Auto delete handling
        if bot.auto_del > 0 and sent_msgs:
            enter = f"start {query_text}-{quality_filter}"
            info_msg = await bot.send_message(
                query.from_user.id,
                f"<blockquote expandable>⚠️These files will auto-delete in {humanize.naturaldelta(bot.auto_del)}. Forward them to Saved Messages!</blockquote>"
            )
            asyncio.create_task(delete_files(sent_msgs, bot, info_msg, enter))

    except Forbidden:
        await query.answer(f"📩 Start bot first!\n👉 t.me/{BOT_USERNAME}", show_alert=True)
    except Exception as e:
        logger.error(traceback.format_exc())
        await query.answer(f"❌ Error: {e}", show_alert=True)
