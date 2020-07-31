from asyncio import Condition
import telethon
from telethon import events
import resources
import os
import curses
from subprocess import call
import drawtool
import emojis
import shlex
import sqlite3
from telethon.utils import get_display_name
import datetime
import re
from tttcutils import debug, show_stacktrace
import subprocess
import pyperclip
from key_handler import KeyHandler

from telethon.tl.functions.messages import ToggleDialogPinRequest


import logging
logging.basicConfig(filename='/tmp/tttc.log') #, level=logging.DEBUG)


class MainView():
    def __init__(self, client, stdscr):
        self.stdscr = stdscr
        self.client = client
        self.inputevent = Condition()
        self.client.add_event_handler(self.on_message, events.NewMessage)
        self.client.add_event_handler(self.on_user_update, events.UserUpdate)
        # TODO
        # self.client.add_event_handler(self.on_read, events.MessageRead)
        self.text_emojis = True

        self.macros = {}
        self.macro_recording = None
        self.macro_sequence = []

        self.popup_input = None
        self.last_saved_location = "/tmp/tttc/"

        # the offset which messages are being displayed.
        # the number corresponds to the lowest message shown on screen as the messages are drawing upwards
        self.message_offset = 0

        self.tab_selection = 0

        self.inputs = ""
        self.inputs_cursor = 0

        self.edit_message = None

        self.popup = None

        self.drawtool = drawtool.Drawtool(self)
        self.fin = False
        from config import colors as colorconfig
        self.colors = colorconfig.get_colors()
        self.ready = False

        self.search_result = None
        self.search_index = None
        self.search_box = ""
        self.vimline_box = ""
        self.command_box = ""

        self._dialogs = []
        self._dialogs_updated = False
        self.num_pinned = 0

        # index corresponds to the index in self.dialogs
        self.selected_chat = 0
        # index offset
        self.selected_chat_offset = 0
            
        self.modestack = ["normal"]

        self.key_handler = KeyHandler(self)

        self.forward_messages = []

    @property
    def dialogs(self):
        if not self._dialogs_updated:
            return self._dialogs
        # filter archived
        self._dialogs = [ dialog for dialog in self._dialogs if not dialog["dialog"].archived ]
        # sort pinned to top
        self._dialogs.sort(key = lambda x: not x["dialog"].pinned)
        self.num_pinned = sum( 1 for dialog in self._dialogs if dialog["dialog"].pinned )
        return self._dialogs

    @dialogs.setter
    def dialogs(self, newdialogs):
        self._dialogs_updated = True
        self._dialogs = newdialogs

    @property
    def mode(self):
        try:
            return self.modestack[-1]
        except IndexError:
            self.modestack = ["normal"]
            return "normal"

    @mode.setter
    def mode(self, newmode):
        # i think we might need this
        if self.modestack == ["normal"] and newmode == "normal":
            return
        self.modestack.append(newmode)

    async def quit(self):
        self.fin = True
        with await self.inputevent:
            self.inputevent.notify()

    async def on_user_update(self, event):
        user_id = event.user_id 
        if event.online != None:
            for dialog in self.dialogs:
                if event.online == True:
                    dialog["online_until"] = event.until
                elif dialog["online_until"]:
                    now = datetime.datetime.now().astimezone()
                    until = dialog["online_until"].astimezone()
                    if (now - until).seconds > 0:
                        dialog["online_until"] = None
                        dialog["online"] = False
                if dialog["dialog"].entity.id == user_id:
                    dialog["online"] = event.online

    async def on_forward(self, n):
        front = self.dialogs.pop(self.selected_chat)
        self.dialogs = [front] + self.dialogs
        self.selected_chat = 0
        dialog = self.dialogs[0]
        newmessages = await self.client.get_messages(dialog["dialog"], n)
        for message in newmessages[::-1]:
            dialog["messages"].insert(0, message)

    async def toggle_pin(self):
        dialog = self.dialogs[self.selected_chat]["dialog"]
        dialog.pinned = not dialog.pinned
        debug(f"{dialog.name} is {dialog.pinned=}")
        out = await self.client(ToggleDialogPinRequest(dialog.input_entity, dialog.pinned))
        debug(f"{out=}")

    async def on_message(self, event):
        # move chats with news up
        for idx, dialog in enumerate(self.dialogs):
            if dialog["dialog"].id == event.chat_id:
                # stuff to do upon arriving messages
                newmessage = await self.client.get_messages(dialog["dialog"], 1)
                dialog["messages"].insert(0, newmessage[0])
                if not event.out:
                    dialog["unread_count"] += 1
                    os.system(f"notify-send -i apps/telegram \"{dialog['dialog'].name}\" \"{newmessage[0].message}\"")
                front = self.dialogs.pop(idx)
                self.dialogs = [front] + self.dialogs
                break
        # dont switch the dialoge upon arriving messages
        if idx == self.selected_chat:
            self.selected_chat = 0
        elif idx > self.selected_chat:
            self.selected_chat += 1
        elif idx < self.selected_chat:
            pass
        await self.drawtool.redraw()

    async def run(self):
        try:
            chats = await self.client.get_dialogs()
        except sqlite3.OperationalError:
            self.stdscr.addstr("Database is locked. Cannot connect with this session. Aborting")
            self.stdscr.refresh()
            await self.quit()
        self.dialogs = [
                {
                    "dialog": dialog,
                    "unread_count": dialog.unread_count,
                    "online": dialog.entity.status.to_dict()["_"] == "UserStatusOnline" if hasattr(dialog.entity, "status") and dialog.entity.status else None,
                    "online_until": None,
                    "downloads": dict(),
                    "messages": []
                #    "last_seen": dialog.entity.status.to_dict()["was_online"] if online == False  else None,
                } for dialog in chats ]
        await self.drawtool.redraw()
        self.ready = True

    def select_next_chat(self):
        self.message_offset = 0
        # if wrapping not allowed:
        # self.selected_chat = min(self.selected_chat + 1, len(self.dialogs) - 1)
        self.selected_chat = (self.selected_chat + 1) % (len(self.dialogs))
        self.center_selected_chat()

    def select_prev_chat(self):
        self.message_offset = 0
        # if wrapping not allowed:
        # self.selected_chat = max(self.selected_chat - 1, 0)
        self.selected_chat = (self.selected_chat - 1) % (len(self.dialogs))
        self.center_selected_chat()

    def center_selected_chat(self):
        if self.selected_chat < self.drawtool.chats_num // 2:
            self.selected_chat_offset = 0
        elif self.selected_chat > len(self.dialogs) - self.drawtool.chats_num // 2:
            self.selected_chat_offset = len(self.dialogs) - self.drawtool.chats_num
        else:
            self.selected_chat_offset = self.selected_chat - self.drawtool.chats_num // 2

    def select_chat(self, index):
        self.message_offset = 0
        if index < -1 or index >= len(self.dialogs):
            return
        if index == -1:
            index = len(self.dialogs) - 1
        while index < self.selected_chat:
            self.select_prev_chat()
        else:
            while index > self.selected_chat:
                self.select_next_chat()

    def is_subsequence(self, xs, ys):
        xs = list(xs)
        for y in ys:
            if xs and xs[0] == y:
                xs.pop(0)
        return not xs
            
    def search_chats(self, query = None):
        if query is None:
            query = self.search_box
        if query is None:
            return # we dont search for ""
        filter_function = self.is_subsequence
        filter_function = lambda x, y: x in y
        self.search_result = [ idx for (idx, dialog) in enumerate(self.dialogs) 
                if filter_function(query.lower(), get_display_name(dialog["dialog"].entity).lower())]
        self.search_index = -1
    
    def search_next(self):
        if not self.search_result:
            return
        if self.search_index == -1:
            import bisect
            self.search_index = bisect.bisect_left(self.search_result, self.selected_chat)
            self.select_chat(self.search_result[self.search_index % len(self.search_result)])
            self.center_selected_chat()
            return
        self.search_index = (self.search_index + 1) % len(self.search_result)
        index = self.search_result[self.search_index]
        self.select_chat(index)
        self.center_selected_chat()

    def search_prev(self):
        if not self.search_result:
           return
        if self.search_index == -1:
            import bisect
            self.search_index = bisect.bisect_right(self.search_result, self.selected_chat)
            self.select_chat(self.search_result[self.search_index])
            self.center_selected_chat()
            return
        self.search_index = (self.search_index - 1) % len(self.search_result)
        self.select_chat(self.search_result[self.search_index % len(self.search_result)])
        self.center_selected_chat()

    async def call_command(self):
        command = self.vimline_box
        if command == "q":
            await self.quit()
        elif command == "pfd":
            m = ""
            for i in range(len(self.inputs)):
                m += self.inputs[i].lower() if i%2==0 else self.inputs[i].lower().swapcase()
            self.inputs = m

    async def send_message(self):
        if not self.inputs:
            return
        s = self.inputs
        s = emojis.encode(s)
        outgoing_message = await self.dialogs[self.selected_chat]["dialog"].send_message(s)
        await self.on_message(outgoing_message)
        await self.mark_read()
        self.center_selected_chat()
        self.inputs = ""
        self.inputs_cursor = 0

    async def mark_read(self):
        chat = self.dialogs[self.selected_chat]
        dialog = chat["dialog"]
        lastmessage = chat["messages"][0]
        await self.client.send_read_acknowledge(dialog, lastmessage)
        self.dialogs[self.selected_chat]["unread_count"] = 0

    async def download_attachment(self, num = None, force = False):
        if num is None:
            return
        message = self.dialogs[self.selected_chat]["messages"][num]

        if message.id in self.dialogs[self.selected_chat]["downloads"] and not force:
            logging.info(self.dialogs[self.selected_chat]["downloads"])
            self.popup_message(f"File was previously downloaded as: {self.dialogs[self.selected_chat]['downloads'][message.id]}. Use the force (to download anyway).")
            return

        self.popup_input = f"{os.path.dirname(self.last_saved_location)}/"

        async def handler(self, key):
            if key == "ESCAPE":
                self.popup_input = None
                return True # done processing the popup
            elif key == "BACKSPACE":
                if self.popup_input == "":
                    pass
                else:
                    self.popup_input = self.popup_input[0:-1]
            elif key == "RETURN":
                # save message
                filename = self.popup_input or '/tmp/tttc/'
                async def cb(recv, maximum):
                    percentage = 100 * recv / maximum
                    downloadtext = f"downloading to {filename}: {percentage:.2f}%"
                    self.popup[1] = downloadtext
                    self.popup_input = None
                    await self.drawtool.redraw()
                    if (percentage == 100):
                        # we auto clear the popup here
                        self.modestack.pop()
                path = await self.client.download_media(message.media, filename, progress_callback = cb)
                if not path:
                    self.popup_message(f"Could not save file. Maybe there is no attachment?")
                    return True
                self.dialogs[self.selected_chat]["downloads"][message.id] = path
                self.last_saved_location = path
                # now we can work with the downloaded file, show it in filesystem
                self.popup_input = None
                self.popup_message(f"Saved as {path}")
                return True
            else:
                self.popup_input += key
            return False
        self.spawn_popup(handler, "Save file anew as: " if force else "Save file as: ")

    async def open_link(self, num = None):
        def httpify(s):
            if s.startswith("http"):
                return s
            return f"https://{s}"
        if num is None:
            return
        message = self.dialogs[self.selected_chat]["messages"][num]
        if message.entities:
            links = [ text for (entity_type, text) in message.get_entities_text() if entity_type.to_dict()["_"] == "MessageEntityUrl" ]
            if len(links) == 1:
                # if there is a unique link to open, open it.
                link = links[0]
                debug(["xdg-open", f"{httpify(link)}"])
                subprocess.Popen(["xdg-open", f"{httpify(link)}"], stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL)
            elif len(links) > 1:
                # user selects which link to open
                self.tab_selection = 0
                async def handler(self, key):
                    if key == "TAB":
                        self.tab_selection = (self.tab_selection + 1) % len(links)
                        self.popup[1] = f"Select link to open (TAB): {links[self.tab_selection]}"
                    elif key == "ESCAPE":
                        self.modestack.pop()
                    elif key == "RETURN":
                        link = links[self.tab_selection]
                        debug(["xdg-open", f"{httpify(link)}"])
                        subprocess.Popen(["xdg-open", f"{httpify(link)}"], stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL)
                        self.modestack.pop()
                self.spawn_popup(handler, f"Select link to open (TAB): {links[self.tab_selection]}")

    async def show_media(self, num = None):
        if num is None:
            return
        message = self.dialogs[self.selected_chat]["messages"][num]
        if message.id not in self.dialogs[self.selected_chat]["downloads"]:
            self.popup_message("No media found for this message. Did you download it?")
            return
        path = self.dialogs[self.selected_chat]["downloads"][message.id]
        subprocess.Popen(["xdg-open", f"{path}"], stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL)

    def popup_message(self, question):
        #self.modestack.append(self.mode)
        self.mode = "popupmessage"
        async def action_handler(self, key):
            return True
        self.popup = [action_handler, question]

    def spawn_popup(self, action_handler, question):
        # on q press
        #self.modestack.append(self.mode)
        self.mode = "popup"
        self.popup = [action_handler, question]

    async def handle_key(self, key, redraw = True):
        await self.key_handler.handle_key(key)
        await self.drawtool.redraw()

    def modify_input(self, key):
            if key == "LEFT":
                self.insert_move_left()
            elif key == "RIGHT":
                self.insert_move_right()
            elif key == "BACKSPACE":
                if self.inputs_cursor != 0:
                    self.inputs = self.inputs[:self.inputs_cursor - 1] + self.inputs[self.inputs_cursor:]
                    self.inputs_cursor -= 1
            elif key == "DEL":
                if self.inputs_cursor != len(self.inputs):
                    self.inputs = self.inputs[:self.inputs_cursor] + self.inputs[self.inputs_cursor + 1:]
            elif key == "RETURN":
                self.inputs += "\n"
                self.inputs_cursor += 1
            elif len(key) == 1:
                input_string = list(self.inputs)
                input_string.insert(self.inputs_cursor, key)
                self.inputs = "".join(input_string)
                self.inputs_cursor += 1
                #self.inputs.insert(self.inputs_cursor, key)

    def insert_move_left(self):
        self.inputs_cursor = max(0, self.inputs_cursor - 1)

    def insert_move_right(self):
        self.inputs_cursor = min(len(self.inputs), self.inputs_cursor + 1)

    async def handle_key_old(self, key):
        if key == "RETURN":
            with await self.inputevent:
                self.inputevent.notify()
        elif key == "":
            chat =  self.dialogs[self.selected_chat]["dialog"]
            last_message = self.dialogs[self.selected_chat]["messages"][0]
            await self.client.send_read_acknowledge(chat, max_id=last_message.id)
            self.dialogs[self.selected_chat]["unread_count"] = 0
        else:
            self.inputs += key
        self.drawtool.redraw()

