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

        # index corresponds to the index in self.dialogs
        self.selected_chat = 0
        # index offset
        self.selected_chat_offset = 0
            
        self.selected_message = None

        self.mode = "normal"
        self.modestack = []

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

    async def on_message(self, event):
        # move chats with news up
        for idx, dialog in enumerate(self.dialogs):
            if dialog["dialog"].id == event.chat_id:
                # stuff to do upon arriving messages
                newmessage = await self.client.get_messages(dialog["dialog"], 1)
                dialog["messages"].insert(0, newmessage[0])
                if not event.out:
                    dialog["unread_count"] += 1
                front = self.dialogs.pop(idx)
                self.dialogs = [front] + self.dialogs
                break
        # auto adjust relative replys to match shifted message offsets
        if event.chat_id == self.dialogs[self.selected_chat]["dialog"].id:
            if self.inputs.startswith("r"):
                num = self.inputs[1:].split()[0]
                try:
#                    num = int(s[1:].split()[0])
                    number = int(num)
                    msg = self.inputs.replace("r" + num, "r" + str(number+1))
                    self.inputs = msg
                except:
                    pass
        # dont switch the dialoge upon arriving messages
        if idx == self.selected_chat:
            self.selected_chat = 0
        elif idx > self.selected_chat:
            self.selected_chat += 1
        elif idx < self.selected_chat:
            pass
        await self.drawtool.redraw()

    async def textinput(self):
        self.inputs = ""
        with await self.inputevent:
            await self.inputevent.wait()
        if self.fin:
            return ""
        out = self.inputs
        self.inputs = ""
        return out

    async def run(self):
        try:
            chats = await self.client.get_dialogs()
        except sqlite3.OperationalError:
            self.stdscr.addstr("Database is locked. Cannot connect with this session. Aborting")
            self.stdscr.refresh()
            await self.textinput()
            await self.quit()
        self.dialogs = [
                {
                    "dialog": dialog,
                    "unread_count": dialog.unread_count,
                    "online": dialog.entity.status.to_dict()["_"] == "UserStatusOnline" if hasattr(dialog.entity, "status") and dialog.entity.status else None,
                    "online_until": None,
                #    "last_seen": dialog.entity.status.to_dict()["was_online"] if online == False  else None,
                } for dialog in chats ]
        await self.drawtool.redraw()
        self.ready = True
        while True:
            s = await self.textinput()
            if self.fin:
                return
            if s.startswith("r"):
                try:
                    num = int(s[1:].split()[0])
                except:
                    continue
                s = s.replace("r" + str(num) + " ", "")
                reply_msg = self.dialogs[self.selected_chat]["messages"][num]
                s = emojis.encode(s)
                reply = await reply_msg.reply(s)
                await self.on_message(reply)
            elif s.startswith("media"):
                try:
                    num = int(s[5:].split()[0])
                except:
                    continue
                message = self.dialogs[self.selected_chat]["messages"][num]
                if message.media:
                    os.makedirs("/tmp/tttc/", exist_ok=True)
                    path = await self.client.download_media(message.media, "/tmp/tttc/")
                    # TODO mute calls
                    if message.media.photo:
                        sizes = message.media.photo.sizes
                        w, h = sizes[0].w, sizes[0].h
                        # w, h
                        basesize = 1500
                        w3m_command=f"0;1;0;0;{basesize};{int(basesize*h/w)};;;;;{path}\n4;\n3;"
                        W3MIMGDISPLAY="/usr/lib/w3m/w3mimgdisplay"
                        os.system(f"echo -e '{w3m_command}' | {W3MIMGDISPLAY} & disown")
                        await self.textinput()
                    else:
                        subprocess.call(["xdg-open", "{shlex.quote(path)}"], stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL)
                        #os.system(f"(xdg-open {shlex.quote(path)} 2>&1 > /dev/null) & disown")
            else:
                s = emojis.encode(s)
                outgoing_message = await self.dialogs[self.selected_chat]["dialog"].send_message(s)
                await self.on_message(outgoing_message)
            await self.drawtool.redraw()

    def select_next_chat(self):
        # if wrapping not allowed:
        # self.selected_chat = min(self.selected_chat + 1, len(self.dialogs) - 1)
        self.selected_chat = (self.selected_chat + 1) % (len(self.dialogs))
        self.center_selected_chat()

    def select_prev_chat(self):
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

    async def mark_read(self):
        chat = self.dialogs[self.selected_chat]
        dialog = chat["dialog"]
        lastmessage = chat["messages"][0]
        await self.client.send_read_acknowledge(dialog, lastmessage)
        self.dialogs[self.selected_chat]["unread_count"] = 0

    async def show_media(self, num = None):
        if not num:
            return
        message = self.dialogs[self.selected_chat]["messages"][num]
        if message.media:
            os.makedirs("/tmp/tttc/", exist_ok=True)
            # TODO test if file exists, ask for confirmation to replace or download again
            path = await self.client.download_media(message.media, "/tmp/tttc/")
            if hasattr(message.media, "photo") and False:
                sizes = message.media.photo.sizes
                w, h = sizes[0].w, sizes[0].h
                # w, h
                basesize = 300
                w3m_command=f"0;1;0;0;{basesize};{int(basesize*h/w)};;;;;{path}\n4;\n3;"
                W3MIMGDISPLAY="/usr/lib/w3m/w3mimgdisplay"
                echo_sp = subprocess.Popen(["echo", "-e", f"{w3m_command}"], stdout = subprocess.PIPE)
                w3m_sp = subprocess.Popen([f"{W3MIMGDISPLAY}"], stdin = echo_sp.stdout)
            else:
                subprocess.Popen(["xdg-open", f"{path}"], stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL)

    def popup_message(self, question):
        self.modestack.append(self.mode)
        self.mode = "popupmessage"
        async def action_handler(self, key):
            pass
        self.popup = (action_handler, question)

    def spawn_popup(self, action_handler, question):
        # on q press
        self.modestack.append(self.mode)
        self.mode = "popup"
        self.popup = (action_handler, question)

    async def handle_key(self, key, redraw = True):
        if self.mode == "popupmessage":
            self.mode = self.modestack.pop()
        if not self.ready:
            return
        if key == "RESIZE":
            await self.drawtool.resize()
            return
        if self.macro_recording:
            if key != "q":
                self.macro_sequence.append(key)
        if self.mode == "search":
            if key == "ESCAPE" or key == "RETURN":
                self.mode = "normal"
            elif key == "BACKSPACE":
                if self.search_box == "":
                    self.mode = "normal"
                else:
                    self.search_box = self.search_box[0:-1]
                    self.search_chats()
                    self.search_next()
            else:
                self.search_box += key
                self.search_chats()
                self.search_next()
        elif self.mode == "vimmode":
            if key == "ESCAPE":
                self.mode = "normal"
            elif key == "RETURN":
                await self.call_command()
                self.vimline_box = ""
                self.mode = "normal"
            elif key == "BACKSPACE":
                if self.vimline_box == "":
                    self.mode = "normal"
                else:
                    self.vimline_box = self.vimline_box[0:-1]
            else:
                self.vimline_box += key
        elif self.mode == "normal":
            num = None
            try:
                num = int(key)
            except:
                pass
            if num is not None:
                self.command_box += str(num)
                await self.drawtool.redraw()
                return
            elif key == ":":
                self.mode = "vimmode"
                self.vimline_box = ""
            elif key == "RETURN" or key == "y":
                await self.send_message()
            elif key == "Q":
                await self.quit()
            elif key == "q":
                if self.macro_recording == None:
                    # start macro recording
                    async def record_macro(self, key):
                        if "a" < key.lower() < "z":
                            self.macro_recording = key
                            self.popup_message(f"recording into {key}")
                        else:
                            self.popup_message(f"Register must be [a-zA-Z]")

                    self.spawn_popup(record_macro, "Record into which register?")
                else:
                    # end macro recording
                    self.macros[self.macro_recording] = self.macro_sequence
                    self.macro_recording = None
                    self.macro_sequence = []
            elif key == "@":
                # execute macro
                async def ask_macro(self, key):
                    if key in self.macros.keys():
                        macro = self.macros[key]
                        debug(macro)
                        for k in macro:
                            await self.handle_key(k, redraw = False)
                    else:
                        self.popup_message(f"No such macro @{key}")

                self.spawn_popup(ask_macro, "Execute which macro?")
            elif key == "C":
                self.select_prev_chat()
            elif key == "c":
                self.select_next_chat()
            elif key == "E":
                self.text_emojis ^= True
            elif key == "R":
                await self.mark_read()
            elif key == "d":
                if self.command_box:
                    try:
                        n = int(self.command_box)
                    except:
                        return
                    if n >= len(self.dialogs[self.selected_chat]["messages"]):
                        #TODO: alert user
                        self.popup_message("No message by that id.")
                        await self.drawtool.redraw()
                        return
                    async def action_handler(self, key):
                        if key in ["y","Y"]:
                            to_delete = self.dialogs[self.selected_chat]["messages"][n]
                            await to_delete.delete()
                            self.dialogs[self.selected_chat]["messages"].pop(n)
                            self.command_box = ""
                        self.mode = "normal"
                    question = f"Are you really sure you want to delete message {n}? [y/N]"
                    self.spawn_popup(action_handler, question)

                    await self.drawtool.redraw()
            elif key == "e":
                if self.command_box:
                    try:
                        n = int(self.command_box)
                    except:
                        return
                    self.edit_message = self.dialogs[self.selected_chat]["messages"][n]
                    self.mode = "edit"
                    self.inputs = emojis.decode(self.edit_message.text)
                    self.command_box = ""
            elif key == "r":
                if self.command_box:
                    try:
                        n = int(self.command_box)
                    except:
                        return
                    reply_to = self.dialogs[self.selected_chat]["messages"][n]
                    s = emojis.encode(self.inputs)
                    reply = await reply_to.reply(s)
                    await self.on_message(reply)
                    self.command_box = ""
                    self.inputs = ""
            elif key == "m":
                if self.command_box:
                    try:
                        n = int(self.command_box)
                    except:
                        return
                    self.command_box = ""
                    await self.show_media(n)
            elif key == "M":
                self.center_selected_chat()
            elif key == "HOME" or key == "g":
                self.select_chat(0)
            elif key == "END" or key == "G":
                self.select_chat(-1)
            elif key == "i":
                self.mode = "insert"
            elif key == "n":
                self.search_next()
            elif key == "N":
                self.search_prev()
            elif key == "/":
                self.mode = "search"
                self.search_box = ""
            elif key == " ":
                self.drawtool.show_indices ^= True
        elif self.mode == "popup":
            action, _ = self.popup
            # I think this could break
            self.mode = self.modestack.pop()
            await action(self, key)
        elif self.mode == "edit":
            if key == "ESCAPE":
                async def ah(self, key):
                    if key in ["Y", "y", "RETURN"]:
                        edit = await self.edit_message.edit(self.inputs)
                        await self.on_message(edit)
                        # TODO: update message in chat
                        # this on_message call does not work reliably
                        self.mode = "normal"
                    else:
                        self.popup_message("Edit discarded.")
                        self.mode = "normal"
                self.spawn_popup(ah, "Do you want to save the edit? [Y/n]")
            elif key == "LEFT":
                self.insert_move_left()
            elif key == "RIGHT":
                self.insert_move_right()
            elif key == "BACKSPACE":
                self.inputs = self.inputs[0:-1]
            elif key == "RETURN":
                self.inputs += "\n"
            else:
                self.inputs += key
        elif self.mode == "insert":
            if key == "ESCAPE":
                self.mode = "normal"
            elif key == "LEFT":
                self.insert_move_left()
            elif key == "RIGHT":
                self.insert_move_right()
            elif key == "BACKSPACE":
                self.inputs = self.inputs[0:-1]
            elif key == "RETURN":
                self.inputs += "\n"
            else:
                self.inputs += key
        self.command_box = ""
        if redraw:
            await self.drawtool.redraw()

    def insert_move_left(self):
        self.inputs_cursor = max(0, self.cursor - 1)

    def insert_move_right(self):
        self.inputs_cursor = min(len(self.inputs), self.cursor + 1)

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

