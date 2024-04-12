import base64
from os import environ
from pathlib import Path
import time

from openai import OpenAI
from telebot import TeleBot
from telebot.types import Message

from . import *

from telegramify_markdown import convert
from telegramify_markdown.customize import markdown_symbol

markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol

CHATGPT_API_KEY = environ.get("OPENAI_API_KEY")
CHATGPT_BASE_URL = environ.get("OPENAI_API_BASE") or "https://api.openai.com/v1"
CHATGPT_MODEL = "gpt-3.5-turbo"
CHATGPT_PRO_MODEL = "gpt-4-turbo"


client = OpenAI(api_key=CHATGPT_API_KEY, base_url=CHATGPT_BASE_URL, timeout=20)


# Global history cache
chatgpt_player_dict = {}
chatgpt_pro_player_dict = {}


def chatgpt_handler(message: Message, bot: TeleBot) -> None:
    """chatgpt : /chatgpt <question>"""
    m = message.text.strip()

    player_message = []
    # restart will lose all TODO
    if str(message.from_user.id) not in chatgpt_player_dict:
        chatgpt_player_dict[str(message.from_user.id)] = (
            player_message  # for the imuutable list
        )
    else:
        player_message = chatgpt_player_dict[str(message.from_user.id)]
    if m.strip() == "clear":
        bot.reply_to(
            message,
            "just clear your chatgpt messages history",
        )
        player_message.clear()
        return

    who = "ChatGPT"
    # show something, make it more responsible
    reply_id = bot_reply_first(message, who, bot)

    player_message.append({"role": "user", "content": m})
    # keep the last 5, every has two ask and answer.
    if len(player_message) > 10:
        player_message = player_message[2:]

    chatgpt_reply_text = ""
    try:
        r = client.chat.completions.create(
            messages=player_message, max_tokens=1024, model=CHATGPT_MODEL
        )
        content = r.choices[0].message.content.encode("utf8").decode()
        if not content:
            chatgpt_reply_text = f"{who} did not answer."
            player_message.pop()
        else:
            chatgpt_reply_text = content
            player_message.append(
                {
                    "role": "assistant",
                    "content": chatgpt_reply_text,
                }
            )

    except Exception as e:
        print(e)
        bot_reply_markdown(reply_id, who, "answer wrong", bot)
        # pop my user
        player_message.pop()
        return

    # reply back as Markdown and fallback to plain text if failed.
    bot_reply_markdown(reply_id, who, chatgpt_reply_text, bot)


def chatgpt_pro_handler(message: Message, bot: TeleBot) -> None:
    """chatgpt_pro : /chatgpt_pro <question>"""
    m = message.text.strip()

    player_message = []
    # restart will lose all TODO
    if str(message.from_user.id) not in chatgpt_player_dict:
        chatgpt_player_dict[str(message.from_user.id)] = (
            player_message  # for the imuutable list
        )
    else:
        player_message = chatgpt_player_dict[str(message.from_user.id)]
    if m.strip() == "clear":
        bot.reply_to(
            message,
            "just clear your chatgpt messages history",
        )
        player_message.clear()
        return

    who = "ChatGPT Pro"
    reply_id = bot_reply_first(message, who, bot)

    player_message.append({"role": "user", "content": m})
    # keep the last 5, every has two ask and answer.
    if len(player_message) > 10:
        player_message = player_message[2:]

    try:
        r = client.chat.completions.create(
            messages=player_message,
            max_tokens=2048,
            model=CHATGPT_PRO_MODEL,
            stream=True,
        )
        s = ""
        start = time.time()
        for chunk in r:
            if chunk.choices[0].delta.content is None:
                break
            s += chunk.choices[0].delta.content
            if time.time() - start > 1.7:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)

        if not bot_reply_markdown(reply_id, who, s, bot):
            # maybe not complete
            # maybe the same message
            player_message.clear()
            return

        player_message.append(
            {
                "role": "assistant",
                "content": convert(s),
            }
        )

    except Exception as e:
        print(e)
        bot_reply_markdown(reply_id, who, "answer wrong", bot)
        player_message.clear()
        return


def chatgpt_photo_handler(message: Message, bot: TeleBot) -> None:
    s = message.caption
    prompt = s.strip()
    who = "ChatGPT Vision"
    # show something, make it more responsible
    reply_id = bot_reply_first(message, who, bot)
    # get the high quaility picture.
    max_size_photo = max(message.photo, key=lambda p: p.file_size)
    file_path = bot.get_file(max_size_photo.file_id).file_path
    downloaded_file = bot.download_file(file_path)
    with open("chatgpt_temp.jpg", "wb") as temp_file:
        temp_file.write(downloaded_file)
    with open("chatgpt_temp.jpg", "rb") as image_file:
        image_data = image_file.read()
    base64_image_data = base64.b64encode(image_data).decode("utf-8")
    try:
        r = client.chat.completions.create(
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image_data}"
                            },
                        },
                    ],
                }
            ],
            model=CHATGPT_PRO_MODEL,
            stream=True,
        )
        s = ""
        start = time.time()
        for chunk in r:
            if chunk.choices[0].delta.content is None:
                break
            s += chunk.choices[0].delta.content
            if time.time() - start > 1.7:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)

        bot_reply_markdown(reply_id, who, s, bot)
    except Exception as e:
        print(e)
        bot_reply_markdown(reply_id, who, "answer wrong", bot)


def register(bot: TeleBot) -> None:
    bot.register_message_handler(chatgpt_handler, commands=["chatgpt"], pass_bot=True)
    bot.register_message_handler(chatgpt_handler, regexp="^chatgpt:", pass_bot=True)
    bot.register_message_handler(
        chatgpt_pro_handler, commands=["chatgpt_pro"], pass_bot=True
    )
    bot.register_message_handler(
        chatgpt_pro_handler, regexp="^chatgpt_pro:", pass_bot=True
    )
    bot.register_message_handler(
        chatgpt_photo_handler,
        content_types=["photo"],
        func=lambda m: m.caption and m.caption.startswith(("chatgpt:", "/chatgpt")),
        pass_bot=True,
    )
