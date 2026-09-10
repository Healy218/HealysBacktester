"""Telegram overflow notices and opt-in summaries, scoped to the configured chat."""
from datetime import datetime, timezone
import os
import time
import requests


class BotAPI:
    def __init__(self):
        self.chat = str(os.environ['TELEGRAM_CHAT_ID'])
        self._base = 'https://api.telegram.org/bot' + os.environ['TELEGRAM_BOT_TOKEN'] + '/'

    def call(self, method, **payload):
        try:
            response = requests.post(self._base+method,json=payload,timeout=20)
            result = response.json()
            if response.status_code != 200 or result.get('ok') is not True:
                raise ValueError('API rejected request')
            return result['result']
        except (requests.RequestException, ValueError, KeyError):
            raise RuntimeError(f'Telegram {method} failed') from None


def publish_notices(queue, api):
    with queue.connect() as db:
        batches = db.execute("""SELECT DISTINCT batch FROM candidates WHERE status='suppressed_rank'
            AND batch NOT IN (SELECT batch FROM notices)
            AND batch NOT IN (SELECT batch FROM candidates WHERE status IN ('selected','expired'))""").fetchall()
    for record in batches:
        batch = record['batch']
        with queue.connect() as db:
            count = db.execute("SELECT COUNT(*) FROM candidates WHERE batch=? AND status='suppressed_rank'",(batch,)).fetchone()[0]
        stamp = datetime.fromtimestamp(batch,timezone.utc).strftime('%b %d %H:%M UTC')
        text = (f'These are the top 5 by model probability. There are {count} more alerts from the last set of bars '
                f'({stamp}). See more?\nTap below or reply yes for a summary of the rest.')
        result = api.call('sendMessage',chat_id=api.chat,text=text,
                          reply_markup={'inline_keyboard':[[{'text':'Yes — show the rest','callback_data':f'alerts:{batch}'}]]})
        with queue.connect() as db:
            db.execute('INSERT OR IGNORE INTO notices VALUES (?,?)',(batch,result['message_id']))


def requested_batch(queue, update, chat):
    callback = update.get('callback_query')
    message = callback.get('message',{}) if callback else update.get('message',{})
    if str(message.get('chat',{}).get('id')) != str(chat):
        return None
    with queue.connect() as db:
        if callback:
            data = callback.get('data','')
            if not data.startswith('alerts:') or not data[7:].isdigit():
                return None
            row = db.execute('SELECT batch FROM notices WHERE batch=? AND message_id=?',
                             (int(data[7:]),message.get('message_id'))).fetchone()
        elif message.get('text','').strip().lower() in ('yes','yes please'):
            reply = message.get('reply_to_message',{}).get('message_id')
            if reply is not None:
                row = db.execute('SELECT batch FROM notices WHERE message_id=?',(reply,)).fetchone()
            else:
                row = db.execute('SELECT batch FROM notices WHERE batch>=? ORDER BY batch DESC LIMIT 1',
                                 (message.get('date',time.time())-86400,)).fetchone()
        else:
            return None
    return row['batch'] if row else None


def summary_parts(queue, batch):
    with queue.connect() as db:
        rows = db.execute("SELECT * FROM candidates WHERE batch=? AND status IN ('suppressed_rank','suppressed_late') ORDER BY score DESC,key ASC",(batch,)).fetchall()
    stamp = datetime.fromtimestamp(batch,timezone.utc).strftime('%b %d %H:%M UTC')
    header = f'Remaining alerts — bars closed {stamp}\n'
    parts, text = [], header
    for i,row in enumerate(rows,6):
        line = f"{i}. {row['summary'][:300]} | {row['score']:.1%}\n"
        if len(text)+len(line)>3500:
            parts.append(text);text=header+'(continued)\n'
        text += line
    if text != header or not parts:
        parts.append(text if rows else header+'No additional alerts recorded.')
    return parts


def poll_replies(queue, api):
    with queue.connect() as db:
        db.execute('INSERT OR IGNORE INTO reply_state VALUES (?,?)',('enabled_at',str(int(time.time()))))
        since = int(db.execute("SELECT value FROM reply_state WHERE key='enabled_at'").fetchone()[0])
        row = db.execute("SELECT value FROM reply_state WHERE key='offset'").fetchone()
        offset = int(row[0]) if row else 0
    updates = api.call('getUpdates',offset=offset,timeout=0,allowed_updates=['message','callback_query'])
    for update in updates:
        message = update.get('message',{})
        stale = bool(message and message.get('date', 0) < since)
        from nn_meta.live.taken_trades import handle
        trade_response = None if stale else handle(queue, update, api.chat)
        if trade_response is not None:
            callback = update.get('callback_query')
            if callback:
                try:
                    api.call('answerCallbackQuery', callback_query_id=callback['id'], text='Request received')
                except RuntimeError:
                    pass
            for part, start in enumerate(range(0, len(trade_response), 3500)):
                with queue.connect() as db:
                    done = db.execute('SELECT 1 FROM reply_parts WHERE update_id=? AND part=?', (update['update_id'], part)).fetchone()
                if not done:
                    api.call('sendMessage', chat_id=api.chat, text=trade_response[start:start+3500])
                    with queue.connect() as db:
                        db.execute('INSERT OR IGNORE INTO reply_parts VALUES (?,?)', (update['update_id'], part))
        batch = None if stale or trade_response is not None else requested_batch(queue,update,api.chat)
        if batch is not None:
            callback = update.get('callback_query')
            if callback:
                try:
                    api.call('answerCallbackQuery',callback_query_id=callback['id'],text='Showing the remaining alerts')
                except RuntimeError:
                    # Telegram click acknowledgements expire sooner than a cron
                    # polling interval. A failed spinner acknowledgement must
                    # never prevent the requested summary or block later updates.
                    pass
            for i,text in enumerate(summary_parts(queue,batch)):
                with queue.connect() as db:
                    done = db.execute('SELECT 1 FROM reply_parts WHERE update_id=? AND part=?',(update['update_id'],i)).fetchone()
                if not done:
                    api.call('sendMessage',chat_id=api.chat,text=text)
                    with queue.connect() as db:
                        db.execute('INSERT OR IGNORE INTO reply_parts VALUES (?,?)',(update['update_id'],i))
        with queue.connect() as db:
            db.execute('INSERT OR REPLACE INTO reply_state VALUES (?,?)',('offset',str(update['update_id']+1)))
