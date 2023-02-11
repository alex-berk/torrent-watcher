import os
from dotenv import load_dotenv
from urllib.parse import unquote, parse_qs
import prettytable as pt


from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, filters, CommandHandler, MessageHandler, CallbackQueryHandler

from pbclient import TorrentDetails, PBSearcher

from transmission_client import TransmissionClient, download_paths, Torrent
from transmission_rpc import error as transmission_error

load_dotenv()


class SessionStorage:
    pass


storage = SessionStorage()

try:
    transmission = TransmissionClient(
        os.getenv("TRANSMISSION_HOST"), download_paths)
except transmission_error.TransmissionConnectError:
    raise "can't connect to the host"

searcher = PBSearcher()

users_whitelist = [int(uid) for uid in os.getenv("ALLOWED_TG_IDS").split(",")]


def get_param_value(val): return val[val.find("=") + 1:]


def get_name_from_magnet(magnet): return parse_qs(unquote(magnet))["dn"].pop()


def generate_search_results_keyboard(results: list[TorrentDetails]):
    outer_array = []
    for index, result in enumerate(results):
        outer_array.append([InlineKeyboardButton(
            result.name, callback_data=f"full_name={index}")])
        outer_array.append([InlineKeyboardButton(f"{result.size_gb:.2f}Gb, {result.seeds}S", url=result.link),
                            InlineKeyboardButton("📥", callback_data=f"mag_link={index}")])
    return outer_array


def generate_progress_table(torrents: list[Torrent]) -> str:
    table = pt.PrettyTable(["name", "size", "status", "progress",])
    table.align["name"] = "l"
    table.align["size"] = "l"
    table.max_table_width = 70
    table.max_width["name"] = 40
    [table.add_row((torrent.name, f"{torrent.size_when_done / (8**10):.2f}Gb",
                   torrent.status, f"{torrent.progress}%")) for torrent in torrents]
    return str(table)


async def verify_download(update: Update, context: ContextTypes.DEFAULT_TYPE, from_search_results=False):
    callback_id = "download_type"
    if from_search_results:
        callback_id += "_search"
    keyboard = [[InlineKeyboardButton("Movies", callback_data=f"{callback_id}=movie"), InlineKeyboardButton("Shows", callback_data=f"{callback_id}=show"), InlineKeyboardButton("Videos", callback_data=f"{callback_id}=video"),], [
        InlineKeyboardButton("Other", callback_data=f"{callback_id}=other"), InlineKeyboardButton("⭕️ Cancel", callback_data="cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(text="Where should it be downloaded?", reply_markup=reply_markup)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Heya!", parse_mode='html')


async def callback_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    item_index = get_param_value(update.callback_query.data)
    full_name = storage.search_results[int(item_index)].name
    await update.callback_query.answer(full_name)


async def callback_mag_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    item_index = get_param_value(update.callback_query.data)
    storage.item_chosen = storage.search_results[int(item_index)]
    await verify_download(update, context, True)


async def callback_download_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    download_type = get_param_value(query.data)
    if query.data.startswith("download_type_search"):
        magnet_link = searcher.generate_magnet_link(
            storage.item_chosen)
        download_name = storage.item_chosen.name
    else:
        magnet_link = storage.magnet_link
        download_name = get_name_from_magnet(magnet_link)

    try:
        transmission.add_download(magnet_link, download_type)
        await query.answer()
        await query.edit_message_text(text=f"Download job added\nPath: <b>{transmission.download_paths[download_type]}/{download_name}</b>", parse_mode="html")
    except Exception as e:
        print(e)
        await query.answer("There was a problem adding the download job")
    storage.item_chosen = ""
    storage.search_results = []


async def accept_magnet_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.magnet_link = update.message.text
    await verify_download(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.magnet_link = ""
    storage.item_chosen = ""
    await update.callback_query.edit_message_text("Canceled")


async def search_pb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_query = ' '.join(context.args)
    if not search_query:
        return await context.bot.send_message(chat_id=update.effective_chat.id,
                                              text="You need to use this command with search query, lile <i>/search Game of thrones s03</i>")
    search_results = searcher.search_torrent(search_query)
    if not search_results:
        return await context.bot.send_message(chat_id=update.effective_chat.id, text="couldn't find anything")
    storage.search_results = search_results
    text = "here's a top results i've found:"
    results_keyboard = generate_search_results_keyboard(search_results[:5])
    reply_markup = InlineKeyboardMarkup(results_keyboard)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)


async def save_torrent_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await context.bot.get_file(update.message.document)
    await file.download_to_drive(os.path.join("tg_downloads", update.message.document.file_name))
    # TODO: send download job
    await context.bot.send_message(chat_id=update.effective_chat.id, text="let's pretend i've saved it")


async def get_pending_downloads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending_downloads = transmission.get_pending_downloads()
    if not pending_downloads:
        return await context.bot.send_message(chat_id=update.effective_chat.id, text="no pending downloads at the moment")
    output_table = generate_progress_table(pending_downloads)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f'<pre>{output_table}</pre>', parse_mode="html")


async def auth_failed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="do i know you?")


async def unknown_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="that doesn't look like a file i can work with")


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I didn't understand that command.")

application = ApplicationBuilder().token(os.getenv("TG_BOT_TOKEN")).build()

auth_handler = MessageHandler(
    filters.TEXT & ~filters.User(users_whitelist), auth_failed)
start_handler = CommandHandler('start', start)
search_handler = CommandHandler('search', search_pb)
search_handler_shortcut = CommandHandler('s', search_pb)
downloads_status_handler = CommandHandler('downloads', get_pending_downloads)
downloads_status_handler_shortcut = CommandHandler('d', get_pending_downloads)
magnet_link_handler = MessageHandler(filters.Regex(
    r'magnet:\?xt=.*') & (~filters.COMMAND), accept_magnet_link)
file_torrent_handler = MessageHandler(
    filters.Document.FileExtension("torrent"), save_torrent_file)
unknown_file_handler = MessageHandler(
    filters.Document.ALL, unknown_file)
unknown_handler = MessageHandler(filters.TEXT, unknown_command)

application.add_handler(auth_handler)
application.add_handler(start_handler)
application.add_handler(search_handler)
application.add_handler(search_handler_shortcut)
application.add_handler(downloads_status_handler)
application.add_handler(downloads_status_handler_shortcut)
application.add_handler(magnet_link_handler)
application.add_handler(file_torrent_handler)
application.add_handler(CallbackQueryHandler(
    callback_full_name, pattern="full_name="))
application.add_handler(CallbackQueryHandler(
    callback_mag_link, pattern="mag_link="))
application.add_handler(CallbackQueryHandler(
    callback_download_type, pattern="download_type"))
application.add_handler(CallbackQueryHandler(
    cancel, pattern="cancel"))


application.add_handler(unknown_handler)
application.add_handler(unknown_file_handler)

if __name__ == '__main__':
    application.run_polling()
