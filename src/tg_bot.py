import os
import asyncio
from dataclasses import dataclass
from urllib.parse import unquote, parse_qs
import prettytable as pt


from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, filters, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler

from pb_client import TorrentDetails
from pb_orchestrator import PBMonitor, PBSearcher, MonitorSetting

from transmission_client import Torrent

MONITOR_TYPE, SEARCH_QUERY, SEASON_AND_EPISODE, SIZE_LIMIT, SILENT = range(5)


@dataclass
class Storage:
    saved_search_results: list[TorrentDetails]


item_chosen: str or None
active_torrent: str or None


class TgBotRunner:
    def __init__(self, tg_client, torrent_client, torrent_searcher, monitors_orchestrator, tg_user_whitelist=None):
        self.tg_client = tg_client
        self.torrent_client = torrent_client
        self.torrent_searcher = torrent_searcher
        self.monitors_orchestrator = monitors_orchestrator
        self.tg_user_whitelist = tg_user_whitelist or []
        self._storage = Storage([None] * 50)

        # TODO: refactor with filters in command handlers
        auth_handler = MessageHandler(
            filters.TEXT & ~filters.User(self.tg_user_whitelist), self.auth_failed)
        start_handler = CommandHandler('start', self.start)
        cancel_handler = CommandHandler('cancel', self.cancel)
        search_handler = CommandHandler('search', self.search_pb)
        search_handler_shortcut = CommandHandler('s', self.search_pb)
        downloads_status_handler = CommandHandler(
            'downloads', self.get_recent_downloads)
        downloads_status_handler_shortcut = CommandHandler(
            'd', self.get_recent_downloads)
        view_monitors_handler = CommandHandler(
            "list_monitors", self.view_monitors)
        view_monitors_handler_shortcut = CommandHandler(
            "lm", self.view_monitors)
        run_monitors_handler = CommandHandler(
            "run_monitors", self.run_user_monitors)
        run_monitors_handler_shortcut = CommandHandler(
            "rm", self.run_user_monitors)

        conv_new_monitor_handler = ConversationHandler(
            entry_points=[CommandHandler(
                "add_monitor", self.add_monitor), CommandHandler("am", self.add_monitor)],
            states={
                MONITOR_TYPE: [MessageHandler(filters.Regex("^Movie|Show$"), self.set_monitor_search_query)],
                SEARCH_QUERY: [MessageHandler(filters.TEXT, self.set_monitor_silent)],
                SILENT: [MessageHandler(filters.TEXT, self.get_season_and_episode)],
                SEASON_AND_EPISODE: [MessageHandler(filters.TEXT, self.set_size_limit)],
                SIZE_LIMIT: [MessageHandler(filters.TEXT, self.generate_torrent_monitor)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_conversation)]
        )

        magnet_link_handler = MessageHandler(filters.Regex(
            r'magnet:\?xt=.*') & (~filters.COMMAND), self.accept_magnet_link)
        file_torrent_handler = MessageHandler(
            filters.Document.FileExtension("torrent"), self.save_torrent_file)
        unknown_file_handler = MessageHandler(
            filters.Document.ALL, self.unknown_file)
        unknown_handler = MessageHandler(filters.TEXT, self.unknown_command)

        self.tg_client.add_handler(auth_handler)
        self.tg_client.add_handler(start_handler)
        self.tg_client.add_handler(cancel_handler)
        self.tg_client.add_handler(search_handler)
        self.tg_client.add_handler(search_handler_shortcut)
        self.tg_client.add_handler(downloads_status_handler)
        self.tg_client.add_handler(downloads_status_handler_shortcut)
        self.tg_client.add_handler(conv_new_monitor_handler)
        self.tg_client.add_handler(view_monitors_handler)
        self.tg_client.add_handler(view_monitors_handler_shortcut)
        self.tg_client.add_handler(run_monitors_handler)
        self.tg_client.add_handler(run_monitors_handler_shortcut)
        self.tg_client.add_handler(magnet_link_handler)
        self.tg_client.add_handler(file_torrent_handler)
        self.tg_client.add_handler(CallbackQueryHandler(
            self.callback_full_name, pattern="full_name="))
        self.tg_client.add_handler(CallbackQueryHandler(
            self.callback_mag_link, pattern="mag_link="))
        self.tg_client.add_handler(CallbackQueryHandler(
            self.callback_monitor_full_name, pattern="monitor_full_name="))
        self.tg_client.add_handler(CallbackQueryHandler(
            self.callback_monitor_delete, pattern="monitor_delete="))
        self.tg_client.add_handler(CallbackQueryHandler(
            self.callback_download_type, pattern="download_type"))
        self.tg_client.add_handler(CallbackQueryHandler(
            self.cancel, pattern="cancel"))

        self.tg_client.add_handler(unknown_handler)
        self.tg_client.add_handler(unknown_file_handler)

    @property
    def item_chosen(self):
        try:
            return next(
                filter(lambda i: i.info_hash == self._storage.item_chosen, self._storage.saved_search_results))
        except StopIteration:
            return

    @item_chosen.setter
    def item_chosen(self, item: TorrentDetails):
        self._storage.item_chosen = item.info_hash

    @property
    def active_torrent(self):
        return self._storage.active_torrent

    @active_torrent.setter
    def active_torrent(self, link):
        self._storage.active_torrent = link

    @property
    def saved_search_results(self):
        return self._storage.saved_search_results

    @saved_search_results.setter
    def saved_search_results(self, results: list):
        self._storage.saved_search_results = results + \
            self._storage.saved_search_results[:-len(results)]

    @staticmethod
    def get_param_value(val): return val[val.find("=") + 1:]

    @staticmethod
    def get_name_from_magnet(magnet): return parse_qs(
        unquote(magnet))["dn"].pop()

    def send_message(self, chat_id, text, parse_mode="html"):
        asyncio.get_event_loop().run_until_complete(
            self.tg_client.bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode))

    def get_search_result(self, hash: str):
        try:
            return next(filter(lambda item: item.info_hash == hash, self.saved_search_results))
        except StopIteration:
            return

    def get_active_monitor(self, update: Update) -> MonitorSetting:
        query = update.callback_query
        monitor_index = self.get_param_value(query.data)
        user_monitors = self.monitors_orchestrator.get_user_monitors(
            update.effective_chat.id)
        active_monitor = user_monitors[int(monitor_index)]
        return active_monitor

    def run_search_jobs(self, job_owner_id: int):
        search_results = self.monitors_orchestrator.run_search_jobs(
            job_owner_id)
        for found_item in search_results:
            download_type = "show" if type(
                found_item.job_settings.searcher) == PBMonitor else "movie"
            magnet_link = self.torrent_searcher.generate_magnet_link(
                found_item.result)
            self.torrent_client.add_download(magnet_link, download_type)

    def clear_storage(self):
        self._storage.item_chosen = None
        self._storage.active_torrent = None

    @staticmethod
    def generate_search_results_keyboard(results: list[TorrentDetails], search_query: str) -> list[list[InlineKeyboardButton]]:
        outer_array = []
        for result in results:
            outer_array.append([InlineKeyboardButton(
                result.name, callback_data=f"full_name={result.info_hash}")])
            outer_array.append([InlineKeyboardButton(f"{result.size_gb:.2f}Gb, {result.seeds}S", url=result.link),
                                InlineKeyboardButton("????", callback_data=f"mag_link={result.info_hash}")])
        search_page_link = "https://thepiratebay.org/search.php?q=" + search_query
        outer_array += [[InlineKeyboardButton(
            "Search results page", url=search_page_link)]]
        return outer_array

    @staticmethod
    def generate_progress_table(torrents: list[Torrent]) -> str:
        table = pt.PrettyTable(["name", "size", "status", "progress",])
        table.align["name"] = "l"
        table.align["size"] = "l"
        table.max_table_width = 70
        table.max_width["name"] = 40
        [table.add_row((torrent.name, f"{torrent.size_when_done / (8**10):.2f}Gb",
                        torrent.status, f"{torrent.progress}%")) for torrent in torrents]
        return str(table)

    # Handler functions
        # flow handlers
    @staticmethod
    async def verify_download_type(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_postfix=None):
        callback_id = "download_type"
        if callback_postfix:
            callback_id += f"_{callback_postfix}"
        keyboard = [[InlineKeyboardButton("Movies", callback_data=f"{callback_id}=movie"), InlineKeyboardButton("Shows", callback_data=f"{callback_id}=show"), InlineKeyboardButton("Videos", callback_data=f"{callback_id}=video"),], [
            InlineKeyboardButton("Other", callback_data=f"{callback_id}=other"), InlineKeyboardButton("?????? Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Where should it be downloaded?", reply_markup=reply_markup)

        # command handlers
    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Heya!")

    async def search_pb(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        search_query = ' '.join(context.args)
        if not search_query:
            return await context.bot.send_message(chat_id=update.effective_chat.id,
                                                  text="You need to use this command with search query, like <i>/search Game of thrones s03</i>", parse_mode="html")
        search_results = self.torrent_searcher.search_torrent(search_query)[:5]
        if not search_results:
            return await context.bot.send_message(chat_id=update.effective_chat.id, text="couldn't find anything")
        self.saved_search_results = search_results
        text = "here's a top results i've found:"
        results_keyboard = self.generate_search_results_keyboard(
            search_results, search_query)
        reply_markup = InlineKeyboardMarkup(results_keyboard)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)

    async def generate_torrent_monitor(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        try:
            context.user_data["size_limit"] = int(text)
        except ValueError:
            pass
        orchestrator_params = {
            "is_serial": context.user_data["monitor_type"] == "show",
            "silent": context.user_data["notify"] == "no",
            "query": context.user_data["search_query"],
            "owner_id": update.effective_chat.id
        }
        if orchestrator_params["is_serial"]:
            orchestrator_params["season"] = context.user_data["season"]
            orchestrator_params["episode_number"] = context.user_data["episode_number"]
            orchestrator_params["size_limit"] = context.user_data.get(
                "size_limit", 0)
        self.monitors_orchestrator.add_monitor_job_from_dict(
            orchestrator_params)
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Added monitor job", reply_markup=ReplyKeyboardRemove())

        self.run_search_jobs(update.effective_chat.id)
        return ConversationHandler.END

    async def run_user_monitors(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.run_search_jobs(update.effective_chat.id)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="ran all monitors")

    async def add_monitor(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        search_query = ' '.join(context.args)
        if search_query:
            # todo: also check if should be silent
            context.user_data["notify"] = "yes"
            context.user_data["monitor_type"] = "movie"
            context.user_data["search_query"] = search_query
            return await self.generate_torrent_monitor(update, context)
        keyboard = [["Movie", "Show"]]
        await update.message.reply_text("What are we looking for? (Movie/Show)", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))

        return MONITOR_TYPE

    async def set_monitor_search_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        content_type = update.message.text.lower()
        context.user_data["monitor_type"] = content_type
        await update.message.reply_text(f"What's the name of the {content_type}?", reply_markup=ReplyKeyboardRemove())

        return SEARCH_QUERY

    async def set_monitor_silent(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        context.user_data["search_query"] = text
        keyboard = ReplyKeyboardMarkup([[
            "Yes", "No"]], one_time_keyboard=True)
        await update.message.reply_text("Should i notify you when i find it?", reply_markup=keyboard)

        return SILENT

    async def get_season_and_episode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # TODO: move before silent setting
        text = update.message.text
        context.user_data["notify"] = text.lower()
        if context.user_data["monitor_type"] == "movie":
            return await self.generate_torrent_monitor(update, context)
        await update.message.reply_text("What season and episode should i start with? Answer with format SS-EE")
        return SEASON_AND_EPISODE

    async def set_size_limit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            season, episode = update.message.text.split("-")
            context.user_data["season"] = int(season)
            context.user_data["episode_number"] = int(episode)
            await update.message.reply_text("Is there a size limit for each episode (in Gb)? Answer 'No' for no size limit", reply_markup=ReplyKeyboardMarkup([["No"]], one_time_keyboard=True))
            return SIZE_LIMIT
        except ValueError:
            await update.message.reply_text(
                "Can't understand it. Please, pay attention to the format")
            await self.get_season_and_episode(update, context)

    async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("Canceled", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    async def view_monitors(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_monitors: MonitorSetting = self.monitors_orchestrator.get_user_monitors(
            update.effective_chat.id)
        keyboard = [[InlineKeyboardButton(str(user_monitor.searcher), callback_data=f"monitor_full_name={index}"), InlineKeyboardButton("???????", callback_data=f"monitor_delete={index}")]
                    for index, user_monitor in enumerate(user_monitors)]
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f'Here are your active monitors:', reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="html")

    @ staticmethod
    async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I didn't understand that command.")

        # callback handlers
    async def callback_full_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        item_hash = self.get_param_value(update.callback_query.data)
        full_name = self.get_search_result(item_hash).name
        await update.callback_query.answer(full_name)

    async def callback_mag_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        item_hash = self.get_param_value(update.callback_query.data)
        self.item_chosen = self.get_search_result(item_hash)
        await self.verify_download_type(update, context, "search")

    async def callback_download_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        download_type = self.get_param_value(query.data)
        if query.data.startswith("download_type_search"):
            magnet_link = self.torrent_searcher.generate_magnet_link(
                self.item_chosen)
            added_download = self.torrent_client.add_download(
                magnet_link, download_type)
            try:
                download_name = added_download.name
                await query.edit_message_text(text=f"Download job added\nPath: <b>{self.torrent_client.download_paths[download_type]}/{download_name}</b>", parse_mode="html")
            except AttributeError:
                await query.edit_message_text(text=f"Error getting name of the download")
            finally:
                await query.answer()

        elif query.data.startswith("download_type_maglink"):
            magnet_link = self.active_torrent
            added_download = self.torrent_client.add_download(
                magnet_link, download_type)
            try:
                download_name = added_download.name
                await query.edit_message_text(text=f"Download job added\nPath: <b>{self.torrent_client.download_paths[download_type]}/{download_name}</b>", parse_mode="html")
            except AttributeError:
                await query.edit_message_text(text=f"Error getting name of the download")
            finally:
                await query.answer()

        elif query.data.startswith("download_type_file"):
            added_download = self.torrent_client.download_from_file(
                self.active_torrent, download_type)
            try:
                download_name = added_download.name
                await query.edit_message_text(text=f"Download job added\nPath: <b>{self.torrent_client.download_paths[download_type]}/{download_name}</b>", parse_mode="html")
            except AttributeError:
                await query.edit_message_text(text=f"Error getting name of the download")
            finally:
                await query.answer()

        self.clear_storage()

    async def callback_monitor_full_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        active_monitor = self.get_active_monitor(update)
        await update.callback_query.answer(str(active_monitor.searcher))

    async def callback_monitor_delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        active_monitor = self.get_active_monitor(update)
        self.monitors_orchestrator.delete_monitor_job(active_monitor)
        await update.callback_query.answer("Deleted")
        await self.view_monitors(update, context)

    async def get_recent_downloads(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        pending_downloads = self.torrent_client.get_recent_downloads()
        if not pending_downloads:
            return await context.bot.send_message(chat_id=update.effective_chat.id, text="no pending downloads at the moment")
        output_table = self.generate_progress_table(pending_downloads)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f'<pre>{output_table}</pre>', parse_mode="html")

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.clear_storage()
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Canceled", reply_markup=ReplyKeyboardRemove())

        # text / file handlers
    async def accept_magnet_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.active_torrent = update.message.text
        await self.verify_download_type(update, context, "maglink")

    async def save_torrent_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        file = await context.bot.get_file(update.message.document)
        save_path = os.path.join(
            os.getcwd(), "data", "torrent-files", update.message.document.file_name)
        await file.download_to_drive(save_path)
        self.active_torrent = save_path
        await self.verify_download_type(update, context, "file")

    @staticmethod
    async def unknown_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="that doesn't look like a file i can work with")

    @staticmethod
    async def auth_failed(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="do i know you?")
