from aiofiles import open as aiopen
from aiofiles.os import remove, rename, path as aiopath
from aioshutil import rmtree
from asyncio import (
    create_subprocess_exec,
    create_subprocess_shell,
    gather,
    wait_for,
)
from dotenv import load_dotenv
from io import BytesIO
from os import environ, getcwd
from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.errors import ListenerTimeout, ListenerStopped

from bot import (
    config_dict,
    user_data,
    DATABASE_URL,
    MAX_SPLIT_SIZE,
    DRIVES_IDS,
    DRIVES_NAMES,
    INDEX_URLS,
    aria2,
    GLOBAL_EXTENSION_FILTER,
    Intervals,
    aria2_options,
    aria2c_global,
    IS_PREMIUM_USER,
    task_dict,
    qbit_options,
    qbittorrent_client,
    sabnzbd_client,
    LOGGER,
    bot,
    jd_downloads,
    nzb_options,
    get_nzb_options,
    get_qb_options,
)
from bot.helper.ext_utils.bot_utils import (
    setInterval,
    sync_to_async,
    retry_function,
)
from bot.helper.ext_utils.db_handler import DbManager
from bot.helper.ext_utils.jdownloader_booter import jdownloader
from bot.helper.ext_utils.task_manager import start_from_queued
from bot.helper.mirror_leech_utils.rclone_utils.serve import rclone_serve_booter
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import (
    sendMessage,
    sendFile,
    editMessage,
    update_status_message,
    deleteMessage,
)
from bot.modules.rss import addJob
from bot.modules.torrent_search import initiate_search_tools

START = 0
STATE = "view"
default_values = {
    "DOWNLOAD_DIR": "/usr/src/app/downloads/",
    "LEECH_SPLIT_SIZE": MAX_SPLIT_SIZE,
    "RSS_DELAY": 600,
    "STATUS_UPDATE_INTERVAL": 15,
    "SEARCH_LIMIT": 0,
    "UPSTREAM_BRANCH": "master",
    "DEFAULT_UPLOAD": "gd",
}


async def get_buttons(key=None, edit_type=None):
    buttons = ButtonMaker()
    if key is None:
        buttons.ibutton("Config Variables", "botset var")
        buttons.ibutton("Private Files", "botset private")
        buttons.ibutton("Qbit Settings", "botset qbit")
        buttons.ibutton("Aria2c Settings", "botset aria")
        buttons.ibutton("Sabnzbd Settings", "botset nzb")
        buttons.ibutton("JDownloader Sync", "botset syncjd")
        buttons.ibutton("Close", "botset close")
        msg = "Bot Settings:"
    elif edit_type is not None:
        if edit_type == "botvar":
            msg = ""
            buttons.ibutton("Back", "botset var")
            if key not in ["TELEGRAM_HASH", "TELEGRAM_API", "OWNER_ID", "BOT_TOKEN"]:
                buttons.ibutton("Default", f"botset resetvar {key}")
            buttons.ibutton("Close", "botset close")
            if key in [
                "SUDO_USERS",
                "CMD_SUFFIX",
                "OWNER_ID",
                "USER_SESSION_STRING",
                "TELEGRAM_HASH",
                "TELEGRAM_API",
                "AUTHORIZED_CHATS",
                "DATABASE_URL",
                "BOT_TOKEN",
                "DOWNLOAD_DIR",
            ]:
                msg += "Restart required for this edit to take effect!\n\n"
            msg += f"Send a valid value for {key}. Current value is '{config_dict[key]}'. Timeout: 60 sec"
        elif edit_type == "ariavar":
            buttons.ibutton("Back", "botset aria")
            if key != "newkey":
                buttons.ibutton("Default", f"botset resetaria {key}")
                buttons.ibutton("Empty String", f"botset emptyaria {key}")
            buttons.ibutton("Close", "botset close")
            msg = (
                "Send a key with value. Example: https-proxy-user:value. Timeout: 60 sec"
                if key == "newkey"
                else f"Send a valid value for {key}. Current value is '{aria2_options[key]}'. Timeout: 60 sec"
            )
        elif edit_type == "qbitvar":
            buttons.ibutton("Back", "botset qbit")
            buttons.ibutton("Empty String", f"botset emptyqbit {key}")
            buttons.ibutton("Close", "botset close")
            msg = f"Send a valid value for {key}. Current value is '{qbit_options[key]}'. Timeout: 60 sec"
        elif edit_type == "nzbvar":
            buttons.ibutton("Back", "botset nzb")
            buttons.ibutton("Default", f"botset resetnzb {key}")
            buttons.ibutton("Empty String", f"botset emptynzb {key}")
            buttons.ibutton("Close", "botset close")
            msg = f"Send a valid value for {key}. Current value is '{nzb_options[key]}'.\nIf the value is list then seperate them by space or ,\nExample: .exe,info or .exe .info\nTimeout: 60 sec"
        elif edit_type.startswith("nzbsevar"):
            index = 0 if key == "newser" else int(edit_type.replace("nzbsevar", ""))
            buttons.ibutton("Back", f"botset nzbser{index}")
            if key != "newser":
                buttons.ibutton("Empty", f"botset emptyserkey {index} {key}")
            buttons.ibutton("Close", "botset close")
            if key == "newser":
                msg = "Send one server as dictionary {}, like in config.env without []. Timeout: 60 sec"
            else:
                msg = f"Send a valid value for {key} in server {config_dict['USENET_SERVERS'][index]['name']}. Current value is '{config_dict['USENET_SERVERS'][index][key]}. Timeout: 60 sec"
    elif key == "var":
        for k in list(config_dict.keys())[START : 10 + START]:
            buttons.ibutton(k, f"botset botvar {k}")
        if STATE == "view":
            buttons.ibutton("Edit", "botset edit var")
        else:
            buttons.ibutton("View", "botset view var")
        buttons.ibutton("Back", "botset back")
        buttons.ibutton("Close", "botset close")
        for x in range(0, len(config_dict), 10):
            buttons.ibutton(
                f"{int(x / 10)}", f"botset start var {x}", position="footer"
            )
        msg = f"Config Variables | Page: {int(START / 10)} | State: {STATE}"
    elif key == "private":
        buttons.ibutton("Back", "botset back")
        buttons.ibutton("Close", "botset close")
        msg = """Send private file: config.env, token.pickle, rclone.conf, accounts.zip, list_drives.txt, cookies.txt, .netrc or any other private file!
To delete private file send only the file name as text message.
Note: Changing .netrc will not take effect for aria2c until restart.
Timeout: 60 sec"""
    elif key == "aria":
        for k in list(aria2_options.keys())[START : 10 + START]:
            buttons.ibutton(k, f"botset ariavar {k}")
        if STATE == "view":
            buttons.ibutton("Edit", "botset edit aria")
        else:
            buttons.ibutton("View", "botset view aria")
        buttons.ibutton("Add new key", "botset ariavar newkey")
        buttons.ibutton("Back", "botset back")
        buttons.ibutton("Close", "botset close")
        for x in range(0, len(aria2_options), 10):
            buttons.ibutton(
                f"{int(x / 10)}", f"botset start aria {x}", position="footer"
            )
        msg = f"Aria2c Options | Page: {int(START / 10)} | State: {STATE}"
    elif key == "qbit":
        for k in list(qbit_options.keys())[START : 10 + START]:
            buttons.ibutton(k, f"botset qbitvar {k}")
        if STATE == "view":
            buttons.ibutton("Edit", "botset edit qbit")
        else:
            buttons.ibutton("View", "botset view qbit")
        buttons.ibutton("Sync Qbittorrent", "botset syncqbit")
        buttons.ibutton("Back", "botset back")
        buttons.ibutton("Close", "botset close")
        for x in range(0, len(qbit_options), 10):
            buttons.ibutton(
                f"{int(x / 10)}", f"botset start qbit {x}", position="footer"
            )
        msg = f"Qbittorrent Options | Page: {int(START / 10)} | State: {STATE}"
    elif key == "nzb":
        for k in list(nzb_options.keys())[START : 10 + START]:
            buttons.ibutton(k, f"botset nzbvar {k}")
        if STATE == "view":
            buttons.ibutton("Edit", "botset edit nzb")
        else:
            buttons.ibutton("View", "botset view nzb")
        buttons.ibutton("Servers", "botset nzbserver")
        buttons.ibutton("Sync Sabnzbd", "botset syncnzb")
        buttons.ibutton("Back", "botset back")
        buttons.ibutton("Close", "botset close")
        for x in range(0, len(nzb_options), 10):
            buttons.ibutton(
                f"{int(x / 10)}", f"botset start nzb {x}", position="footer"
            )
        msg = f"Sabnzbd Options | Page: {int(START / 10)} | State: {STATE}"
    elif key == "nzbserver":
        if len(config_dict["USENET_SERVERS"]) > 0:
            for index, k in enumerate(
                config_dict["USENET_SERVERS"][START : 10 + START]
            ):
                buttons.ibutton(k["name"], f"botset nzbser{index}")
        buttons.ibutton("Add New", "botset nzbsevar newser")
        buttons.ibutton("Back", "botset nzb")
        buttons.ibutton("Close", "botset close")
        if len(config_dict["USENET_SERVERS"]) > 10:
            for x in range(0, len(config_dict["USENET_SERVERS"]), 10):
                buttons.ibutton(
                    f"{int(x / 10)}", f"botset start nzbser {x}", position="footer"
                )
        msg = f"Usenet Servers | Page: {int(START / 10)} | State: {STATE}"
    elif key.startswith("nzbser"):
        index = int(key.replace("nzbser", ""))
        for k in list(config_dict["USENET_SERVERS"][index].keys())[START : 10 + START]:
            buttons.ibutton(k, f"botset nzbsevar{index} {k}")
        if STATE == "view":
            buttons.ibutton("Edit", f"botset edit {key}")
        else:
            buttons.ibutton("View", f"botset view {key}")
        buttons.ibutton("Remove Server", f"botset remser {index}")
        buttons.ibutton("Back", "botset nzbserver")
        buttons.ibutton("Close", "botset close")
        if len(config_dict["USENET_SERVERS"][index].keys()) > 10:
            for x in range(0, len(config_dict["USENET_SERVERS"][index]), 10):
                buttons.ibutton(
                    f"{int(x / 10)}", f"botset start {key} {x}", position="footer"
                )
        msg = f"Server Keys | Page: {int(START / 10)} | State: {STATE}"

    button = buttons.build_menu(1) if key is None else buttons.build_menu(2)
    return msg, button


async def update_buttons(message, key=None, edit_type=None):
    msg, button = await get_buttons(key, edit_type)
    await editMessage(message, msg, button)


async def edit_variable(message, pre_message, key):
    value = message.text
    if value.lower() == "true":
        value = True
    elif value.lower() == "false":
        value = False
        if key == "INCOMPLETE_TASK_NOTIFIER" and DATABASE_URL:
            await DbManager().trunc_table("tasks")
    elif key == "DOWNLOAD_DIR":
        if not value.endswith("/"):
            value += "/"
    elif key in ["LEECH_DUMP_CHAT", "RSS_CHAT"]:
        if value.isdigit() or value.startswith("-"):
            value = int(value)
    elif key == "STATUS_UPDATE_INTERVAL":
        value = int(value)
        if len(task_dict) != 0 and (st := Intervals["status"]):
            for cid, intvl in list(st.items()):
                intvl.cancel()
                Intervals["status"][cid] = setInterval(
                    value, update_status_message, cid
                )
    elif key == "TORRENT_TIMEOUT":
        value = int(value)
        downloads = await sync_to_async(aria2.get_downloads)
        for download in downloads:
            if not download.is_complete:
                try:
                    await sync_to_async(
                        aria2.client.change_option,
                        download.gid,
                        {"bt-stop-timeout": f"{value}"},
                    )
                except Exception as e:
                    LOGGER.error(e)
        aria2_options["bt-stop-timeout"] = f"{value}"
    elif key == "LEECH_SPLIT_SIZE":
        value = min(int(value), MAX_SPLIT_SIZE)
    elif key == "BASE_URL_PORT":
        value = int(value)
        if config_dict["BASE_URL"]:
            await (await create_subprocess_exec("pkill", "-9", "-f", "gunicorn")).wait()
            await create_subprocess_shell(
                f"gunicorn web.wserver:app --bind 0.0.0.0:{value} --worker-class gevent"
            )
    elif key == "EXTENSION_FILTER":
        fx = value.split()
        GLOBAL_EXTENSION_FILTER.clear()
        GLOBAL_EXTENSION_FILTER.extend(["aria2", "!qB"])
        for x in fx:
            x = x.lstrip(".")
            GLOBAL_EXTENSION_FILTER.append(x.strip().lower())
    elif key == "GDRIVE_ID":
        if DRIVES_NAMES and DRIVES_NAMES[0] == "Main":
            DRIVES_IDS[0] = value
        else:
            DRIVES_IDS.insert(0, value)
    elif key == "INDEX_URL":
        if DRIVES_NAMES and DRIVES_NAMES[0] == "Main":
            INDEX_URLS[0] = value
        else:
            INDEX_URLS.insert(0, value)
    elif value.isdigit():
        value = int(value)
    elif value.startswith("[") and value.endswith("]"):
        value = eval(value)
    config_dict[key] = value
    await update_buttons(pre_message, "var")
    await deleteMessage(message)
    if DATABASE_URL:
        await DbManager().update_config({key: value})
    if key in ["SEARCH_PLUGINS", "SEARCH_API_LINK"]:
        await initiate_search_tools()
    elif key in ["QUEUE_ALL", "QUEUE_DOWNLOAD", "QUEUE_UPLOAD"]:
        await start_from_queued()
    elif key in [
        "RCLONE_SERVE_URL",
        "RCLONE_SERVE_PORT",
        "RCLONE_SERVE_USER",
        "RCLONE_SERVE_PASS",
    ]:
        await rclone_serve_booter()
    elif key in ["JD_EMAIL", "JD_PASS"]:
        jdownloader.initiate()
    elif key == "RSS_DELAY":
        addJob()
    elif key == "USET_SERVERS":
        for s in value:
            await sabnzbd_client.set_special_config("servers", s)


async def edit_aria(message, pre_message, key):
    value = message.text
    if key == "newkey":
        key, value = [x.strip() for x in value.split(":", 1)]
    elif value.lower() == "true":
        value = "true"
    elif value.lower() == "false":
        value = "false"
    if key in aria2c_global:
        await sync_to_async(aria2.set_global_options, {key: value})
    else:
        downloads = await sync_to_async(aria2.get_downloads)
        for download in downloads:
            if not download.is_complete:
                try:
                    await sync_to_async(
                        aria2.client.change_option, download.gid, {key: value}
                    )
                except Exception as e:
                    LOGGER.error(e)
    aria2_options[key] = value
    await update_buttons(pre_message, "aria")
    await deleteMessage(message)
    if DATABASE_URL:
        await DbManager().update_aria2(key, value)


async def edit_qbit(message, pre_message, key):
    value = message.text
    if value.lower() == "true":
        value = True
    elif value.lower() == "false":
        value = False
    elif key == "max_ratio":
        value = float(value)
    elif value.isdigit():
        value = int(value)
    await sync_to_async(qbittorrent_client.app_set_preferences, {key: value})
    qbit_options[key] = value
    await update_buttons(pre_message, "qbit")
    await deleteMessage(message)
    if DATABASE_URL:
        await DbManager().update_qbittorrent(key, value)


async def edit_nzb(message, pre_message, key):
    value = message.text
    if value.isdigit():
        value = int(value)
    elif value.startswith("[") and value.endswith("]"):
        value = ",".join(eval(value))
    res = await sabnzbd_client.set_config("misc", key, value)
    nzb_options[key] = res["config"]["misc"][key]
    await update_buttons(pre_message, "nzb")
    await deleteMessage(message)
    if DATABASE_URL:
        await DbManager().update_nzb_config()


async def edit_nzb_server(message, pre_message, key, index=0):
    value = message.text
    if value.startswith("{") and value.endswith("}"):
        if key == "newser":
            try:
                value = eval(value)
            except:
                await sendMessage(message, "Invalid dict format!")
                await update_buttons(pre_message, "nzbserver")
                return
            res = await sabnzbd_client.add_server(value)
            if not res["config"]["servers"][0]["host"]:
                await sendMessage(message, "Invalid server!")
                await update_buttons(pre_message, "nzbserver")
                return
            config_dict["USENET_SERVERS"].append(value)
            await update_buttons(pre_message, "nzbserver")
    elif key != "newser":
        if value.isdigit():
            value = int(value)
        res = await sabnzbd_client.add_server(
            {"name": config_dict["USENET_SERVERS"][index]["name"], key: value}
        )
        if res["config"]["servers"][0][key] == "":
            await sendMessage(message, "Invalid value")
            return
        config_dict["USENET_SERVERS"][index][key] = value
        await update_buttons(pre_message, f"nzbser{index}")
    await deleteMessage(message)
    if DATABASE_URL:
        await DbManager().update_config(
            {"USENET_SERVERS": config_dict["USENET_SERVERS"]}
        )


async def sync_jdownloader():
    if not DATABASE_URL or jdownloader.device is None:
        return
    try:
        await wait_for(retry_function(jdownloader.update_devices), timeout=10)
    except:
        is_connected = await jdownloader.jdconnect()
        if not is_connected:
            LOGGER.error(jdownloader.error)
            return
        isDeviceConnected = await jdownloader.connectToDevice()
        if not isDeviceConnected:
            LOGGER.error(jdownloader.error)
            return
    await jdownloader.device.system.exit_jd()
    if await aiopath.exists("cfg.zip"):
        await remove("cfg.zip")
    is_connected = await jdownloader.jdconnect()
    if not is_connected:
        LOGGER.error(jdownloader.error)
        return
    isDeviceConnected = await jdownloader.connectToDevice()
    if not isDeviceConnected:
        LOGGER.error(jdownloader.error)
    await (
        await create_subprocess_exec("7z", "a", "cfg.zip", "/JDownloader/cfg")
    ).wait()
    await DbManager().update_private_file("cfg.zip")


async def update_private_file(message, pre_message):
    if not message.media and (file_name := message.text):
        fn = file_name.rsplit(".zip", 1)[0]
        if await aiopath.isfile(fn) and file_name != "config.env":
            await remove(fn)
        if fn == "accounts":
            if await aiopath.exists("accounts"):
                await rmtree("accounts", ignore_errors=True)
            if await aiopath.exists("rclone_sa"):
                await rmtree("rclone_sa", ignore_errors=True)
            config_dict["USE_SERVICE_ACCOUNTS"] = False
            if DATABASE_URL:
                await DbManager().update_config({"USE_SERVICE_ACCOUNTS": False})
        elif file_name in [".netrc", "netrc"]:
            await (await create_subprocess_exec("touch", ".netrc")).wait()
            await (await create_subprocess_exec("chmod", "600", ".netrc")).wait()
            await (await create_subprocess_exec("cp", ".netrc", "/root/.netrc")).wait()
        await deleteMessage(message)
    elif doc := message.document:
        file_name = doc.file_name
        await message.download(file_name=f"{getcwd()}/{file_name}")
        if file_name == "accounts.zip":
            if await aiopath.exists("accounts"):
                await rmtree("accounts", ignore_errors=True)
            if await aiopath.exists("rclone_sa"):
                await rmtree("rclone_sa", ignore_errors=True)
            await (
                await create_subprocess_exec(
                    "7z", "x", "-o.", "-aoa", "accounts.zip", "accounts/*.json"
                )
            ).wait()
            await (
                await create_subprocess_exec("chmod", "-R", "777", "accounts")
            ).wait()
        elif file_name == "list_drives.txt":
            DRIVES_IDS.clear()
            DRIVES_NAMES.clear()
            INDEX_URLS.clear()
            if GDRIVE_ID := config_dict["GDRIVE_ID"]:
                DRIVES_NAMES.append("Main")
                DRIVES_IDS.append(GDRIVE_ID)
                INDEX_URLS.append(config_dict["INDEX_URL"])
            async with aiopen("list_drives.txt", "r+") as f:
                lines = await f.readlines()
                for line in lines:
                    temp = line.strip().split()
                    DRIVES_IDS.append(temp[1])
                    DRIVES_NAMES.append(temp[0].replace("_", " "))
                    if len(temp) > 2:
                        INDEX_URLS.append(temp[2])
                    else:
                        INDEX_URLS.append("")
        elif file_name in [".netrc", "netrc"]:
            if file_name == "netrc":
                await rename("netrc", ".netrc")
                file_name = ".netrc"
            await (await create_subprocess_exec("chmod", "600", ".netrc")).wait()
            await (await create_subprocess_exec("cp", ".netrc", "/root/.netrc")).wait()
        elif file_name == "config.env":
            load_dotenv("config.env", override=True)
            await load_config()
        if "@github.com" in config_dict["UPSTREAM_REPO"]:
            buttons = ButtonMaker()
            msg = "Push to UPSTREAM_REPO ?"
            buttons.ibutton("Yes!", f"botset push {file_name}")
            buttons.ibutton("No", "botset close")
            await sendMessage(message, msg, buttons.build_menu(2))
        else:
            await deleteMessage(message)
    if file_name == "rclone.conf":
        await rclone_serve_booter()
    await update_buttons(pre_message)
    if DATABASE_URL:
        await DbManager().update_private_file(file_name)
    if await aiopath.exists("accounts.zip"):
        await remove("accounts.zip")


async def event_handler(client, query, document=False):
    event_filter = filters.text | filters.document if document else filters.text
    return await client.listen(
        chat_id=query.message.chat.id,
        user_id=query.from_user.id,
        filters=event_filter,
        timeout=60,
    )


async def edit_bot_settings(client, query):
    message = query.message
    await client.stop_listening(chat_id=message.chat.id, user_id=query.from_user.id)
    data = query.data.split()
    if data[1] == "close":
        await query.answer()
        await deleteMessage(message.reply_to_message)
        await deleteMessage(message)
    elif data[1] == "back":
        await query.answer()
        globals()["START"] = 0
        await update_buttons(message, None)
    elif data[1] == "syncjd":
        if not config_dict["JD_EMAIL"] or not config_dict["JD_PASS"]:
            await query.answer(
                "No Email or Password provided!",
                show_alert=True,
            )
            return
        if jd_downloads:
            await query.answer(
                "You can't sync settings while using jdownloader!",
                show_alert=True,
            )
            return
        await query.answer(
            "Syncronization Started. JDownloader will get restarted. It takes up to 5 sec!",
            show_alert=True,
        )
        await sync_jdownloader()
    elif data[1] in ["var", "aria", "qbit", "nzb", "nzbserver"] or data[1].startswith(
        "nzbser"
    ):
        if data[1] == "nzbserver":
            globals()["START"] = 0
        await query.answer()
        await update_buttons(message, data[1])
    elif data[1] == "resetvar":
        await query.answer()
        value = ""
        if data[2] in default_values:
            value = default_values[data[2]]
            if (
                data[2] == "STATUS_UPDATE_INTERVAL"
                and len(task_dict) != 0
                and (st := Intervals["status"])
            ):
                for key, intvl in list(st.items()):
                    intvl.cancel()
                    Intervals["status"][key] = setInterval(
                        value, update_status_message, key
                    )
        elif data[2] == "EXTENSION_FILTER":
            GLOBAL_EXTENSION_FILTER.clear()
            GLOBAL_EXTENSION_FILTER.extend(["aria2", "!qB"])
        elif data[2] == "TORRENT_TIMEOUT":
            downloads = await sync_to_async(aria2.get_downloads)
            for download in downloads:
                if not download.is_complete:
                    try:
                        await sync_to_async(
                            aria2.client.change_option,
                            download.gid,
                            {"bt-stop-timeout": "0"},
                        )
                    except Exception as e:
                        LOGGER.error(e)
            aria2_options["bt-stop-timeout"] = "0"
            if DATABASE_URL:
                await DbManager().update_aria2("bt-stop-timeout", "0")
        elif data[2] == "BASE_URL":
            await (await create_subprocess_exec("pkill", "-9", "-f", "gunicorn")).wait()
        elif data[2] == "BASE_URL_PORT":
            value = 80
            if config_dict["BASE_URL"]:
                await (
                    await create_subprocess_exec("pkill", "-9", "-f", "gunicorn")
                ).wait()
                await create_subprocess_shell(
                    "gunicorn web.wserver:app --bind 0.0.0.0:80 --worker-class gevent"
                )
        elif data[2] == "GDRIVE_ID":
            if DRIVES_NAMES and DRIVES_NAMES[0] == "Main":
                DRIVES_NAMES.pop(0)
                DRIVES_IDS.pop(0)
                INDEX_URLS.pop(0)
        elif data[2] == "INDEX_URL":
            if DRIVES_NAMES and DRIVES_NAMES[0] == "Main":
                INDEX_URLS[0] = ""
        elif data[2] == "INCOMPLETE_TASK_NOTIFIER" and DATABASE_URL:
            await DbManager().trunc_table("tasks")
        elif data[2] in ["JD_EMAIL", "JD_PASS"]:
            jdownloader.device = None
            jdownloader.error = "JDownloader Credentials not provided!"
            await create_subprocess_exec("pkill", "-9", "-f", "java")
        elif data[2] == "USENET_SERVERS":
            for s in config_dict["USENET_SERVERS"]:
                await sabnzbd_client.delete_config("servers", s["name"])
        config_dict[data[2]] = value
        await update_buttons(message, "var")
        if DATABASE_URL:
            await DbManager().update_config({data[2]: value})
        if data[2] in ["SEARCH_PLUGINS", "SEARCH_API_LINK"]:
            await initiate_search_tools()
        elif data[2] in ["QUEUE_ALL", "QUEUE_DOWNLOAD", "QUEUE_UPLOAD"]:
            await start_from_queued()
        elif data[2] in [
            "RCLONE_SERVE_URL",
            "RCLONE_SERVE_PORT",
            "RCLONE_SERVE_USER",
            "RCLONE_SERVE_PASS",
        ]:
            await rclone_serve_booter()
    elif data[1] == "resetaria":
        aria2_defaults = await sync_to_async(aria2.client.get_global_option)
        if aria2_defaults[data[2]] == aria2_options[data[2]]:
            await query.answer("Value already same as you added in aria.sh!")
            return
        await query.answer()
        value = aria2_defaults[data[2]]
        aria2_options[data[2]] = value
        await update_buttons(message, "aria")
        downloads = await sync_to_async(aria2.get_downloads)
        for download in downloads:
            if not download.is_complete:
                try:
                    await sync_to_async(
                        aria2.client.change_option, download.gid, {data[2]: value}
                    )
                except Exception as e:
                    LOGGER.error(e)
        if DATABASE_URL:
            await DbManager().update_aria2(data[2], value)
    elif data[1] == "resetnzb":
        await query.answer()
        res = await sabnzbd_client.set_config_default(data[2])
        nzb_options[data[2]] = res["config"]["misc"][data[2]]
        await update_buttons(message, "nzb")
        if DATABASE_URL:
            await DbManager().update_nzb_config()
    elif data[1] == "syncnzb":
        await query.answer(
            "Syncronization Started. It takes up to 2 sec!", show_alert=True
        )
        await get_nzb_options()
        if DATABASE_URL:
            await DbManager().update_nzb_config()
    elif data[1] == "syncqbit":
        await query.answer(
            "Syncronization Started. It takes up to 2 sec!", show_alert=True
        )
        await get_qb_options()
        if DATABASE_URL:
            await DbManager().save_qbit_settings()
    elif data[1] == "emptyaria":
        await query.answer()
        aria2_options[data[2]] = ""
        await update_buttons(message, "aria")
        downloads = await sync_to_async(aria2.get_downloads)
        for download in downloads:
            if not download.is_complete:
                try:
                    await sync_to_async(
                        aria2.client.change_option, download.gid, {data[2]: ""}
                    )
                except Exception as e:
                    LOGGER.error(e)
        if DATABASE_URL:
            await DbManager().update_aria2(data[2], "")
    elif data[1] == "emptyqbit":
        await query.answer()
        await sync_to_async(qbittorrent_client.app_set_preferences, {data[2]: value})
        qbit_options[data[2]] = ""
        await update_buttons(message, "qbit")
        if DATABASE_URL:
            await DbManager().update_qbittorrent(data[2], "")
    elif data[1] == "emptynzb":
        await query.answer()
        res = await sabnzbd_client.set_config("misc", data[2], "")
        nzb_options[data[2]] = res["config"]["misc"][data[2]]
        await update_buttons(message, "nzb")
        if DATABASE_URL:
            await DbManager().update_nzb_config()
    elif data[1] == "remser":
        index = int(data[2])
        await sabnzbd_client.delete_config(
            "servers", config_dict["USENET_SERVERS"][index]["name"]
        )
        del config_dict["USENET_SERVERS"][index]
        await update_buttons(message, "nzbserver")
        if DATABASE_URL:
            await DbManager().update_config(
                {"USENET_SERVERS": config_dict["USENET_SERVERS"]}
            )
    elif data[1] == "private":
        await query.answer()
        await update_buttons(message, data[1])
        try:
            event = await event_handler(client, query, True)
        except ListenerTimeout:
            await update_buttons(message)
        except ListenerStopped:
            pass
        else:
            await update_private_file(event, message)
    elif data[1] == "botvar" and STATE == "edit":
        await query.answer()
        await update_buttons(message, data[2], data[1])
        try:
            event = await event_handler(client, query)
        except ListenerTimeout:
            await update_buttons(message, "var")
        except ListenerStopped:
            pass
        else:
            await edit_variable(event, message, data[2])
    elif data[1] == "botvar" and STATE == "view":
        value = f"{config_dict[data[2]]}"
        if len(value) > 200:
            await query.answer()
            with BytesIO(str.encode(value)) as out_file:
                out_file.name = f"{data[2]}.txt"
                await sendFile(message, out_file)
            return
        elif value == "":
            value = None
        await query.answer(f"{value}", show_alert=True)
    elif data[1] == "ariavar" and (STATE == "edit" or data[2] == "newkey"):
        await query.answer()
        await update_buttons(message, data[2], data[1])
        try:
            event = await event_handler(client, query)
        except ListenerTimeout:
            await update_buttons(message, "aria")
        except ListenerStopped:
            pass
        else:
            await edit_aria(event, message, data[2])
    elif data[1] == "ariavar" and STATE == "view":
        value = f"{aria2_options[data[2]]}"
        if len(value) > 200:
            await query.answer()
            with BytesIO(str.encode(value)) as out_file:
                out_file.name = f"{data[2]}.txt"
                await sendFile(message, out_file)
            return
        elif value == "":
            value = None
        await query.answer(f"{value}", show_alert=True)
    elif data[1] == "qbitvar" and STATE == "edit":
        await query.answer()
        await update_buttons(message, data[2], data[1])
        try:
            event = await event_handler(client, query)
        except ListenerTimeout:
            await update_buttons(message, "qbit")
        except ListenerStopped:
            pass
        else:
            await edit_qbit(event, message, data[2])
    elif data[1] == "qbitvar" and STATE == "view":
        value = f"{qbit_options[data[2]]}"
        if len(value) > 200:
            await query.answer()
            with BytesIO(str.encode(value)) as out_file:
                out_file.name = f"{data[2]}.txt"
                await sendFile(message, out_file)
            return
        elif value == "":
            value = None
        await query.answer(f"{value}", show_alert=True)
    elif data[1] == "nzbvar" and STATE == "edit":
        await query.answer()
        await update_buttons(message, data[2], data[1])
        try:
            event = await event_handler(client, query)
        except ListenerTimeout:
            await update_buttons(message, "nzb")
        except ListenerStopped:
            pass
        else:
            await edit_nzb(event, message, data[2])
    elif data[1] == "nzbvar" and STATE == "view":
        value = f"{nzb_options[data[2]]}"
        if len(value) > 200:
            await query.answer()
            with BytesIO(str.encode(value)) as out_file:
                out_file.name = f"{data[2]}.txt"
                await sendFile(message, out_file)
            return
        elif value == "":
            value = None
        await query.answer(f"{value}", show_alert=True)
    elif data[1] == "emptyserkey":
        await query.answer()
        await update_buttons(message, f"nzbser{data[2]}")
        index = int(data[2])
        res = await sabnzbd_client.add_server(
            {"name": config_dict["USENET_SERVERS"][index]["name"], data[3]: ""}
        )
        config_dict["USENET_SERVERS"][index][data[3]] = res["config"]["servers"][0][
            data[3]
        ]
        if DATABASE_URL:
            await DbManager().update_config(
                {"USENET_SERVERS": config_dict["USENET_SERVERS"]}
            )
    elif data[1].startswith("nzbsevar") and (STATE == "edit" or data[2] == "newser"):
        index = 0 if data[2] == "newser" else int(data[1].replace("nzbsevar", ""))
        await query.answer()
        await update_buttons(message, data[2], data[1])
        try:
            event = await event_handler(client, query)
        except ListenerTimeout:
            await update_buttons(message, data[1])
        except ListenerStopped:
            pass
        else:
            await edit_nzb_server(event, message, data[2], index)
    elif data[1].startswith("nzbsevar") and STATE == "view":
        index = int(data[1].replace("nzbsevar", ""))
        value = f"{config_dict['USENET_SERVERS'][index][data[2]]}"
        if len(value) > 200:
            await query.answer()
            with BytesIO(str.encode(value)) as out_file:
                out_file.name = f"{data[2]}.txt"
                await sendFile(message, out_file)
            return
        elif value == "":
            value = None
        await query.answer(f"{value}", show_alert=True)
    elif data[1] == "edit":
        await query.answer()
        globals()["STATE"] = "edit"
        await update_buttons(message, data[2])
    elif data[1] == "view":
        await query.answer()
        globals()["STATE"] = "view"
        await update_buttons(message, data[2])
    elif data[1] == "start":
        await query.answer()
        if START != int(data[3]):
            globals()["START"] = int(data[3])
            await update_buttons(message, data[2])
    elif data[1] == "push":
        await query.answer()
        filename = data[2].rsplit(".zip", 1)[0]
        if await aiopath.exists(filename):
            await (
                await create_subprocess_shell(
                    f"git add -f {filename} \
                                                    && git commit -sm botsettings -q \
                                                    && git push origin {config_dict['UPSTREAM_BRANCH']} -qf"
                )
            ).wait()
        else:
            await (
                await create_subprocess_shell(
                    f"git rm -r --cached {filename} \
                                                    && git commit -sm botsettings -q \
                                                    && git push origin {config_dict['UPSTREAM_BRANCH']} -qf"
                )
            ).wait()
        await deleteMessage(message.reply_to_message)
        await deleteMessage(message)


async def bot_settings(client, message):
    await client.stop_listening(chat_id=message.chat.id, user_id=message.from_user.id)
    msg, button = await get_buttons()
    globals()["START"] = 0
    await sendMessage(message, msg, button)


async def load_config():
    BOT_TOKEN = environ.get("BOT_TOKEN", "")
    if len(BOT_TOKEN) == 0:
        BOT_TOKEN = config_dict["BOT_TOKEN"]

    TELEGRAM_API = environ.get("TELEGRAM_API", "")
    if len(TELEGRAM_API) == 0:
        TELEGRAM_API = config_dict["TELEGRAM_API"]
    else:
        TELEGRAM_API = int(TELEGRAM_API)

    TELEGRAM_HASH = environ.get("TELEGRAM_HASH", "")
    if len(TELEGRAM_HASH) == 0:
        TELEGRAM_HASH = config_dict["TELEGRAM_HASH"]

    OWNER_ID = environ.get("OWNER_ID", "")
    OWNER_ID = config_dict["OWNER_ID"] if len(OWNER_ID) == 0 else int(OWNER_ID)

    DATABASE_URL = environ.get("DATABASE_URL", "")
    if len(DATABASE_URL) == 0:
        DATABASE_URL = ""

    DOWNLOAD_DIR = environ.get("DOWNLOAD_DIR", "")
    if len(DOWNLOAD_DIR) == 0:
        DOWNLOAD_DIR = "/usr/src/app/downloads/"
    elif not DOWNLOAD_DIR.endswith("/"):
        DOWNLOAD_DIR = f"{DOWNLOAD_DIR}/"

    GDRIVE_ID = environ.get("GDRIVE_ID", "")
    if len(GDRIVE_ID) == 0:
        GDRIVE_ID = ""

    RCLONE_PATH = environ.get("RCLONE_PATH", "")
    if len(RCLONE_PATH) == 0:
        RCLONE_PATH = ""

    DEFAULT_UPLOAD = environ.get("DEFAULT_UPLOAD", "")
    if DEFAULT_UPLOAD != "rc":
        DEFAULT_UPLOAD = "gd"

    RCLONE_FLAGS = environ.get("RCLONE_FLAGS", "")
    if len(RCLONE_FLAGS) == 0:
        RCLONE_FLAGS = ""

    AUTHORIZED_CHATS = environ.get("AUTHORIZED_CHATS", "")
    if len(AUTHORIZED_CHATS) != 0:
        aid = AUTHORIZED_CHATS.split()
        for id_ in aid:
            user_data[int(id_.strip())] = {"is_auth": True}

    SUDO_USERS = environ.get("SUDO_USERS", "")
    if len(SUDO_USERS) != 0:
        aid = SUDO_USERS.split()
        for id_ in aid:
            user_data[int(id_.strip())] = {"is_sudo": True}

    EXTENSION_FILTER = environ.get("EXTENSION_FILTER", "")
    if len(EXTENSION_FILTER) > 0:
        fx = EXTENSION_FILTER.split()
        GLOBAL_EXTENSION_FILTER.clear()
        GLOBAL_EXTENSION_FILTER.extend(["aria2", "!qB"])
        for x in fx:
            if x.strip().startswith("."):
                x = x.lstrip(".")
            GLOBAL_EXTENSION_FILTER.append(x.strip().lower())

    JD_EMAIL = environ.get("JD_EMAIL", "")
    JD_PASS = environ.get("JD_PASS", "")
    if len(JD_EMAIL) == 0 or len(JD_PASS) == 0:
        JD_EMAIL = ""
        JD_PASS = ""

    USENET_SERVERS = environ.get("USENET_SERVERS", "")
    try:
        if len(USENET_SERVERS) == 0:
            USENET_SERVERS = []
        elif (us := eval(USENET_SERVERS)) and not us[0].get("host"):
            USENET_SERVERS = []
        else:
            USENET_SERVERS = eval(USENET_SERVERS)
    except:
        LOGGER.error(f"Wrong USENET_SERVERS format: {USENET_SERVERS}")
        USENET_SERVERS = []

    FILELION_API = environ.get("FILELION_API", "")
    if len(FILELION_API) == 0:
        FILELION_API = ""

    STREAMWISH_API = environ.get("STREAMWISH_API", "")
    if len(STREAMWISH_API) == 0:
        STREAMWISH_API = ""

    INDEX_URL = environ.get("INDEX_URL", "").rstrip("/")
    if len(INDEX_URL) == 0:
        INDEX_URL = ""

    SEARCH_API_LINK = environ.get("SEARCH_API_LINK", "").rstrip("/")
    if len(SEARCH_API_LINK) == 0:
        SEARCH_API_LINK = ""

    LEECH_FILENAME_PREFIX = environ.get("LEECH_FILENAME_PREFIX", "")
    if len(LEECH_FILENAME_PREFIX) == 0:
        LEECH_FILENAME_PREFIX = ""

    SEARCH_PLUGINS = environ.get("SEARCH_PLUGINS", "")
    if len(SEARCH_PLUGINS) == 0:
        SEARCH_PLUGINS = ""
    else:
        try:
            SEARCH_PLUGINS = eval(SEARCH_PLUGINS)
        except:
            LOGGER.error(f"Wrong SEARCH_PLUGINS fornat {SEARCH_PLUGINS}")
            SEARCH_PLUGINS = ""

    MAX_SPLIT_SIZE = 4194304000 if IS_PREMIUM_USER else 2097152000

    LEECH_SPLIT_SIZE = environ.get("LEECH_SPLIT_SIZE", "")
    if len(LEECH_SPLIT_SIZE) == 0 or int(LEECH_SPLIT_SIZE) > MAX_SPLIT_SIZE:
        LEECH_SPLIT_SIZE = MAX_SPLIT_SIZE
    else:
        LEECH_SPLIT_SIZE = int(LEECH_SPLIT_SIZE)

    STATUS_UPDATE_INTERVAL = environ.get("STATUS_UPDATE_INTERVAL", "")
    if len(STATUS_UPDATE_INTERVAL) == 0:
        STATUS_UPDATE_INTERVAL = 15
    else:
        STATUS_UPDATE_INTERVAL = int(STATUS_UPDATE_INTERVAL)
    if len(task_dict) != 0 and (st := Intervals["status"]):
        for key, intvl in list(st.items()):
            intvl.cancel()
            Intervals["status"][key] = setInterval(
                STATUS_UPDATE_INTERVAL, update_status_message, key
            )

    YT_DLP_OPTIONS = environ.get("YT_DLP_OPTIONS", "")
    if len(YT_DLP_OPTIONS) == 0:
        YT_DLP_OPTIONS = ""

    SEARCH_LIMIT = environ.get("SEARCH_LIMIT", "")
    SEARCH_LIMIT = 0 if len(SEARCH_LIMIT) == 0 else int(SEARCH_LIMIT)

    LEECH_DUMP_CHAT = environ.get("LEECH_DUMP_CHAT", "")
    LEECH_DUMP_CHAT = "" if len(LEECH_DUMP_CHAT) == 0 else LEECH_DUMP_CHAT
    if LEECH_DUMP_CHAT.isdigit() or LEECH_DUMP_CHAT.startswith("-"):
        LEECH_DUMP_CHAT = int(LEECH_DUMP_CHAT)

    STATUS_LIMIT = environ.get("STATUS_LIMIT", "")
    STATUS_LIMIT = 4 if len(STATUS_LIMIT) == 0 else int(STATUS_LIMIT)

    RSS_CHAT = environ.get("RSS_CHAT", "")
    RSS_CHAT = "" if len(RSS_CHAT) == 0 else RSS_CHAT
    if RSS_CHAT.isdigit() or RSS_CHAT.startswith("-"):
        RSS_CHAT = int(RSS_CHAT)

    RSS_DELAY = environ.get("RSS_DELAY", "")
    RSS_DELAY = 600 if len(RSS_DELAY) == 0 else int(RSS_DELAY)

    CMD_SUFFIX = environ.get("CMD_SUFFIX", "")

    USER_SESSION_STRING = environ.get("USER_SESSION_STRING", "")

    TORRENT_TIMEOUT = environ.get("TORRENT_TIMEOUT", "")
    downloads = aria2.get_downloads()
    if len(TORRENT_TIMEOUT) == 0:
        for download in downloads:
            if not download.is_complete:
                try:
                    await sync_to_async(
                        aria2.client.change_option,
                        download.gid,
                        {"bt-stop-timeout": "0"},
                    )
                except Exception as e:
                    LOGGER.error(e)
        aria2_options["bt-stop-timeout"] = "0"
        if DATABASE_URL:
            await DbManager().update_aria2("bt-stop-timeout", "0")
        TORRENT_TIMEOUT = ""
    else:
        for download in downloads:
            if not download.is_complete:
                try:
                    await sync_to_async(
                        aria2.client.change_option,
                        download.gid,
                        {"bt-stop-timeout": TORRENT_TIMEOUT},
                    )
                except Exception as e:
                    LOGGER.error(e)
        aria2_options["bt-stop-timeout"] = TORRENT_TIMEOUT
        if DATABASE_URL:
            await DbManager().update_aria2("bt-stop-timeout", TORRENT_TIMEOUT)
        TORRENT_TIMEOUT = int(TORRENT_TIMEOUT)

    QUEUE_ALL = environ.get("QUEUE_ALL", "")
    QUEUE_ALL = "" if len(QUEUE_ALL) == 0 else int(QUEUE_ALL)

    QUEUE_DOWNLOAD = environ.get("QUEUE_DOWNLOAD", "")
    QUEUE_DOWNLOAD = "" if len(QUEUE_DOWNLOAD) == 0 else int(QUEUE_DOWNLOAD)

    QUEUE_UPLOAD = environ.get("QUEUE_UPLOAD", "")
    QUEUE_UPLOAD = "" if len(QUEUE_UPLOAD) == 0 else int(QUEUE_UPLOAD)

    INCOMPLETE_TASK_NOTIFIER = environ.get("INCOMPLETE_TASK_NOTIFIER", "")
    INCOMPLETE_TASK_NOTIFIER = INCOMPLETE_TASK_NOTIFIER.lower() == "true"
    if not INCOMPLETE_TASK_NOTIFIER and DATABASE_URL:
        await DbManager().trunc_table("tasks")

    STOP_DUPLICATE = environ.get("STOP_DUPLICATE", "")
    STOP_DUPLICATE = STOP_DUPLICATE.lower() == "true"

    IS_TEAM_DRIVE = environ.get("IS_TEAM_DRIVE", "")
    IS_TEAM_DRIVE = IS_TEAM_DRIVE.lower() == "true"

    USE_SERVICE_ACCOUNTS = environ.get("USE_SERVICE_ACCOUNTS", "")
    USE_SERVICE_ACCOUNTS = USE_SERVICE_ACCOUNTS.lower() == "true"

    WEB_PINCODE = environ.get("WEB_PINCODE", "")
    WEB_PINCODE = WEB_PINCODE.lower() == "true"

    AS_DOCUMENT = environ.get("AS_DOCUMENT", "")
    AS_DOCUMENT = AS_DOCUMENT.lower() == "true"

    EQUAL_SPLITS = environ.get("EQUAL_SPLITS", "")
    EQUAL_SPLITS = EQUAL_SPLITS.lower() == "true"

    MEDIA_GROUP = environ.get("MEDIA_GROUP", "")
    MEDIA_GROUP = MEDIA_GROUP.lower() == "true"

    USER_TRANSMISSION = environ.get("USER_TRANSMISSION", "")
    USER_TRANSMISSION = USER_TRANSMISSION.lower() == "true" and IS_PREMIUM_USER

    BASE_URL_PORT = environ.get("BASE_URL_PORT", "")
    BASE_URL_PORT = 80 if len(BASE_URL_PORT) == 0 else int(BASE_URL_PORT)

    RCLONE_SERVE_URL = environ.get("RCLONE_SERVE_URL", "")
    if len(RCLONE_SERVE_URL) == 0:
        RCLONE_SERVE_URL = ""

    RCLONE_SERVE_PORT = environ.get("RCLONE_SERVE_PORT", "")
    RCLONE_SERVE_PORT = 8080 if len(RCLONE_SERVE_PORT) == 0 else int(RCLONE_SERVE_PORT)

    RCLONE_SERVE_USER = environ.get("RCLONE_SERVE_USER", "")
    if len(RCLONE_SERVE_USER) == 0:
        RCLONE_SERVE_USER = ""

    RCLONE_SERVE_PASS = environ.get("RCLONE_SERVE_PASS", "")
    if len(RCLONE_SERVE_PASS) == 0:
        RCLONE_SERVE_PASS = ""

    NAME_SUBSTITUTE = environ.get("NAME_SUBSTITUTE", "")
    NAME_SUBSTITUTE = "" if len(NAME_SUBSTITUTE) == 0 else NAME_SUBSTITUTE

    MIXED_LEECH = environ.get("MIXED_LEECH", "")
    MIXED_LEECH = MIXED_LEECH.lower() == "true" and IS_PREMIUM_USER

    await (await create_subprocess_exec("pkill", "-9", "-f", "gunicorn")).wait()
    BASE_URL = environ.get("BASE_URL", "").rstrip("/")
    if len(BASE_URL) == 0:
        BASE_URL = ""
    else:
        await create_subprocess_shell(
            f"gunicorn web.wserver:app --bind 0.0.0.0:{BASE_URL_PORT} --worker-class gevent"
        )

    UPSTREAM_REPO = environ.get("UPSTREAM_REPO", "")
    if len(UPSTREAM_REPO) == 0:
        UPSTREAM_REPO = ""

    UPSTREAM_BRANCH = environ.get("UPSTREAM_BRANCH", "")
    if len(UPSTREAM_BRANCH) == 0:
        UPSTREAM_BRANCH = "master"

    DRIVES_IDS.clear()
    DRIVES_NAMES.clear()
    INDEX_URLS.clear()

    if GDRIVE_ID:
        DRIVES_NAMES.append("Main")
        DRIVES_IDS.append(GDRIVE_ID)
        INDEX_URLS.append(INDEX_URL)

    if await aiopath.exists("list_drives.txt"):
        async with aiopen("list_drives.txt", "r+") as f:
            lines = await f.readlines()
            for line in lines:
                temp = line.strip().split()
                DRIVES_IDS.append(temp[1])
                DRIVES_NAMES.append(temp[0].replace("_", " "))
                if len(temp) > 2:
                    INDEX_URLS.append(temp[2])
                else:
                    INDEX_URLS.append("")

    config_dict.update(
        {
            "AS_DOCUMENT": AS_DOCUMENT,
            "AUTHORIZED_CHATS": AUTHORIZED_CHATS,
            "BASE_URL": BASE_URL,
            "BASE_URL_PORT": BASE_URL_PORT,
            "BOT_TOKEN": BOT_TOKEN,
            "CMD_SUFFIX": CMD_SUFFIX,
            "DATABASE_URL": DATABASE_URL,
            "DEFAULT_UPLOAD": DEFAULT_UPLOAD,
            "DOWNLOAD_DIR": DOWNLOAD_DIR,
            "EQUAL_SPLITS": EQUAL_SPLITS,
            "EXTENSION_FILTER": EXTENSION_FILTER,
            "FILELION_API": FILELION_API,
            "GDRIVE_ID": GDRIVE_ID,
            "INCOMPLETE_TASK_NOTIFIER": INCOMPLETE_TASK_NOTIFIER,
            "INDEX_URL": INDEX_URL,
            "IS_TEAM_DRIVE": IS_TEAM_DRIVE,
            "JD_EMAIL": JD_EMAIL,
            "JD_PASS": JD_PASS,
            "LEECH_DUMP_CHAT": LEECH_DUMP_CHAT,
            "LEECH_FILENAME_PREFIX": LEECH_FILENAME_PREFIX,
            "LEECH_SPLIT_SIZE": LEECH_SPLIT_SIZE,
            "MEDIA_GROUP": MEDIA_GROUP,
            "MIXED_LEECH": MIXED_LEECH,
            "NAME_SUBSTITUTE": NAME_SUBSTITUTE,
            "OWNER_ID": OWNER_ID,
            "QUEUE_ALL": QUEUE_ALL,
            "QUEUE_DOWNLOAD": QUEUE_DOWNLOAD,
            "QUEUE_UPLOAD": QUEUE_UPLOAD,
            "RCLONE_FLAGS": RCLONE_FLAGS,
            "RCLONE_PATH": RCLONE_PATH,
            "RCLONE_SERVE_URL": RCLONE_SERVE_URL,
            "RCLONE_SERVE_USER": RCLONE_SERVE_USER,
            "RCLONE_SERVE_PASS": RCLONE_SERVE_PASS,
            "RCLONE_SERVE_PORT": RCLONE_SERVE_PORT,
            "RSS_CHAT": RSS_CHAT,
            "RSS_DELAY": RSS_DELAY,
            "SEARCH_API_LINK": SEARCH_API_LINK,
            "SEARCH_LIMIT": SEARCH_LIMIT,
            "SEARCH_PLUGINS": SEARCH_PLUGINS,
            "STATUS_LIMIT": STATUS_LIMIT,
            "STATUS_UPDATE_INTERVAL": STATUS_UPDATE_INTERVAL,
            "STOP_DUPLICATE": STOP_DUPLICATE,
            "STREAMWISH_API": STREAMWISH_API,
            "SUDO_USERS": SUDO_USERS,
            "TELEGRAM_API": TELEGRAM_API,
            "TELEGRAM_HASH": TELEGRAM_HASH,
            "TORRENT_TIMEOUT": TORRENT_TIMEOUT,
            "USER_TRANSMISSION": USER_TRANSMISSION,
            "UPSTREAM_REPO": UPSTREAM_REPO,
            "UPSTREAM_BRANCH": UPSTREAM_BRANCH,
            "USENET_SERVERS": USENET_SERVERS,
            "USER_SESSION_STRING": USER_SESSION_STRING,
            "USE_SERVICE_ACCOUNTS": USE_SERVICE_ACCOUNTS,
            "WEB_PINCODE": WEB_PINCODE,
            "YT_DLP_OPTIONS": YT_DLP_OPTIONS,
        }
    )

    if DATABASE_URL:
        await DbManager().update_config(config_dict)
    await gather(initiate_search_tools(), start_from_queued(), rclone_serve_booter())
    addJob()


bot.add_handler(
    MessageHandler(
        bot_settings, filters=filters.command(BotCommands.BotSetCommand, case_sensitive=True) & CustomFilters.sudo
    )
)
bot.add_handler(
    CallbackQueryHandler(
        edit_bot_settings, filters=filters.regex("^botset") & CustomFilters.sudo
    )
)
