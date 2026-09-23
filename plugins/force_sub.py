from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from helper.helper_func import is_bot_admin
import os , asyncio 

async def fsub(client, query):
    msg = f"""<blockquote>**Force Subscription Settings:**</blockquote>
**Force Subscribe Channel IDs:** `{ {a for a in client.fsub_dict.keys()} }`

__Use the appropriate button below to add or remove a force subscription channel based on your needs!__
"""
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton('ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ', 'add_fsub'), InlineKeyboardButton('ʀᴇᴍᴏᴠᴇ ᴄʜᴀɴɴᴇʟ', 'rm_fsub')],
        [InlineKeyboardButton('◂ ʙᴀᴄᴋ', 'settings')]]
    )
    await query.message.edit_text(msg, reply_markup=reply_markup)
    return

@Client.on_callback_query(filters.regex('^add_fsub$'))
async def add_fsub(client: Client, query: CallbackQuery):
    await query.answer()
    ask_channel_info = await client.ask(query.from_user.id, "Send channel id(negative integer value), request boolean(yes/no/true/false), timers(integer without decimal)(to enable it keep it greator than 0 otherwise the invite link will not have any timer to invalidate it) seperated by a space in the next 60 seconds!\n<blockquote expandable>Eg: `-10089479289 yes 5`\n\n__It means `-10089479289` is the force sub channel id, `yes` means to enable request it means the link will be request link and only after user sends request to the channel bot will work for that user even if you do not accept his request or user is not a member, `5` means timer in minutes aftetr 5 minutes the invite link will be expired.__</blockquote>", filters=filters.text, timeout=60)
    try:
        channel_info = ask_channel_info.text.split()
        channel_id, request, timer = channel_info
        channel_id = int(channel_id)
        if channel_id in client.fsub_dict.keys():
            return await ask_channel_info.reply("**This channel id already exists in force sub list, remove it to change it's configuration!!**")
        val, res = await is_bot_admin(client, channel_id)
        if not val:
            return await ask_channel_info.reply(f"**Error:** `{res}`")
        if request.lower() in ('true', 'on', 'yes'):
            request = True
        elif request.lower() in ('false', 'off', 'no'):
            request = False
        else:
            raise Exception("Invalid request value or type.")
        if timer.isdigit():
            timer = int(timer)
        else:
            raise Exception("Timer is not a valid integer.")
        chat = await client.get_chat(channel_id)
        name = chat.title
        if timer > 0:
            client.fsub_dict[channel_id] = [name, None, request, timer]
        else:
            chat_link = await client.create_chat_invite_link(channel_id, creates_join_request=request)
            link = chat_link.invite_link
            client.fsub_dict[channel_id] = [name, link, request, timer]
        await fsub(client, query)
        return await ask_channel_info.reply(f"__Channel with name: `{name.strip()}` is added as a force sub channel!!__")
    except Exception as e:
        return await ask_channel_info.reply(f"**Error:** `{e}`")
    
@Client.on_callback_query(filters.regex('^rm_fsub$'))
async def rm_fsub(client: Client, query: CallbackQuery):
    await query.answer()
    ask_channel_info = await client.ask(query.from_user.id, "Send channel id(negative integer value) in the next 60 seconds!", filters=filters.text, timeout=60)
    try:
        channel_id = int(ask_channel_info.text)
        if channel_id not in client.fsub_dict.keys():
            return await ask_channel_info.reply("**This channel id is not in force sub list!**")
        
        client.fsub_dict.pop(channel_id)
        await fsub(client, query)
        return await ask_channel_info.reply(f"__Channel with id: `{channel_id}` has been removed as a force sub channel!!__")
    except Exception as e:

        return await ask_channel_info.reply(f"**Error:** `{e}`")






@Client.on_callback_query(filters.regex("^manage_users$"))
async def manage_users_callback(client, query: CallbackQuery):
    """Ask admin for a channel ID, show users, and allow deletion."""
    
    channel = await client.ask(
        chat_id=query.message.chat.id,
        text="<blockquote expandable>Send The Channel id You want to check Users .</blockquote>",
        filters=filters.text,
        timeout=60
    )
    
    try:
        channel_id=int(channel.text)
        

        # Fetch users for the channel
        users = await client.mongodb.get_channel_users(channel_id)

        if not users:
            return await query.message.edit_text(
                f"📭 No users found in database for channel ID `{channel_id}`."
            )

        # Try to get channel name
        try:
            chat = await client.get_chat(channel_id)
            channel_name = chat.title
        except Exception:
            channel_name = "Unknown Channel"

        total = len(users)
        text = (
            f"📊 <b>Channel:</b> {channel_name}\n"
            f"<b>ID:</b> <code>{channel_id}</code>\n"
            f"<b>Total Users:</b> <code>{total}</code>\n\n"
            f"⚠️ Do you want to delete all users from this channel?"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm Delete", callback_data=f"confirm_clear|{channel_id}")],
            [InlineKeyboardButton('◂ ʙᴀᴄᴋ', 'settings')]
        ])

        await query.message.edit_text(text, reply_markup=keyboard)

    except asyncio.TimeoutError:
        await query.message.edit_text("⏳ Timeout! You didn’t reply in time.")
    except ValueError:
        await query.message.edit_text("❌ Invalid input! Please send a valid numeric Channel ID.")
    except Exception as e:
        await query.message.edit_text(f"⚠️ Error: {e}")
        client.LOGGER(__name__, client.name).warning(e)


# ───────────────────────────────────────────────
# CONFIRM DELETE HANDLER
# ───────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^confirm_clear\|"))
async def confirm_clear_callback(client, query: CallbackQuery):
    try:
        _, channel_id = query.data.split("|")
        channel_id = int(channel_id)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton('◂ ʙᴀᴄᴋ', 'settings')]
            ])
        await client.mongodb.channel_data.delete_one({"_id": channel_id})
        await query.message.edit_text(
            f"<blockquote expandable>🗑️ All users for channel ID `{channel_id}` have been deleted successfully!</blockquote>",reply_markup=keyboard
        )
    except Exception as e:
        await query.message.edit_text(f"❌ Error: {e}")
        client.LOGGER(__name__, client.name).warning(e)




