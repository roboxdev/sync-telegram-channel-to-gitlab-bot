import os
import logging
import re
from urllib.parse import quote_plus

import requests

from telegram import Bot
from telegram.ext import Dispatcher, Updater, MessageHandler, Filters
from telegram.update import Update

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


BOT_TOKEN = os.environ.get('BOT_TOKEN')
GITLAB_API_TOKEN = os.environ.get('GITLAB_API_TOKEN')
REPOSITORY_BASE_URL = os.environ.get('REPOSITORY_BASE_URL')

CHANNEL_ID = int(os.environ.get('CHANNEL_ID', 0))
OWNER_ID = int(os.environ.get('OWNER_ID', 0))

TG_POST_FILE_PATH = os.environ.get('TG_POST_FILE_PATH', 'content/tgposts/{}/index.md')


def create_or_update_post(data, is_update=False):
    post_id = data.get('post_id')
    title = data.get('title')
    date = data.get('date')

    filepath = TG_POST_FILE_PATH.format(post_id)
    url = '{}/{}'.format(REPOSITORY_BASE_URL, quote_plus(filepath))
    isodate = date.isoformat()

    md_file_template = f'''---
date: '{{date}}'
{"title: '{title}'" if title else ''}
---
'''

    payload = {
        'branch': 'master',
        'content': md_file_template.format(
            date=isodate,
            title=title,
        ),
        'commit_message': '{action} tgpost {post_id}: [{date}]: {title}'.format(
            action='Create new' if not is_update else 'Update',
            post_id=post_id,
            date=isodate,
            title=title,
        ),
    }

    headers = {
        'Authorization': 'Bearer {}'.format(GITLAB_API_TOKEN),
    }

    response = requests.request(
        method='PUT' if is_update else 'POST',
        url=url,
        json=payload,
        headers=headers,
    )


def chat_message_handler(update, context):
    try:
        is_update = bool(update.edited_channel_post)
        message = update.effective_message
        date = message.date
        post_id = message.message_id
        message_text = message.text_markdown
        title = ''

        match = re.match(r'^\*(?P<title>.+?)\*', message_text)
        if match:
            title = match.groupdict()['title']
        create_or_update_post(
            data={
                'post_id': post_id,
                'title': title,
                'date': date,
            },
            is_update=is_update,
        )
        if not match:
            raise AttributeError('Title is missing')
    except BaseException as e:
        context.bot.send_message(
            chat_id=OWNER_ID,
            text='{}\n{}'.format(update.effective_message.link, str(e)),
        )


def set_handlers(dispatcher):
    message_filters = Filters.chat(chat_id=CHANNEL_ID)
    message_handler = MessageHandler(
        filters=message_filters,
        callback=chat_message_handler,
    )
    dispatcher.add_handler(message_handler)


def setup_dispatcher(token):
    bot = Bot(token)
    dispatcher = Dispatcher(bot, None, workers=0, use_context=True)
    set_handlers(dispatcher)
    return dispatcher


def main(request):
    if request.method == 'POST':
        dispatcher = setup_dispatcher(token=BOT_TOKEN)
        update = Update.de_json(request.get_json(force=True), dispatcher.bot)
        dispatcher.process_update(update)
    return 'ok'


if __name__ == '__main__':
    # DEBUG ONLY
    updater = Updater(token=BOT_TOKEN, use_context=True)
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
    if WEBHOOK_URL:
        updater.bot.set_webhook(os.environ.get('WEBHOOK_URL'))
    else:
        set_handlers(updater.dispatcher)
        updater.start_polling()
