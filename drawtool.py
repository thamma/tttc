import curses
import math
from telethon.utils import get_display_name
import emojis
import os
import datetime
import time
import config
import textwrap
from tttcutils import show_stacktrace, debug

import logging
logging.basicConfig(filename='/tmp/tttc.log', level=logging.DEBUG)

class Drawtool():
    def __init__(self, main_view):
        self.client = main_view.client
        self.main_view = main_view
        self.stdscr = main_view.stdscr

        self.chat_ratio = 0.3

        self.H, self.W = self.stdscr.getmaxyx()
        self.recompute_dimensions()
    
        self.chat_rows = 5
        self.chat_offset_fraction = 0.3
        self.single_chat_fraction = 0.3
        self.dialog_fraction = 0.25
        self.show_indices = False

    def recompute_dimensions(self):
        self.min_input_lines = int(0.1 * self.H)
        self.max_input_lines = int(0.3 * self.H)
        try:
            self.input_lines = min(self.max_input_lines, max(len(self._get_input_lines(width = self.W - 4)), self.min_input_lines))
        except:
            show_stacktrace()
        
        self.chats_height = self.H - self.input_lines - 3
        self.chats_width = int(self.W * self.chat_ratio)
        self.chats_num = self.chats_height // 3        

    async def resize(self):
        self.H, self.W = self.stdscr.getmaxyx()
        self.recompute_dimensions()
        await self.redraw()

    def _get_input_lines(self, width = 50, inputs = None):
        if inputs == None:
            inputs = self.main_view.inputs
        # in order to preserve user made linebreaks:
        wrapper = textwrap.TextWrapper()
        wrapper.width = width
        wrapper.replace_whitespace = False
        wrapper.drop_whitespace = False

        #lines = self.main_view.inputs.split("\n")
        lines = inputs.split("\n")
        newlines = []
        for line in lines:
            if line:
                newlines += wrapper.wrap(line) 
            else:
                newlines += [""]
        return newlines

    def _get_cursor_position(self, width = 50):
        lines = self._get_input_lines(width = width)[-self.input_lines:]
        x = 0
        y = 0
        for i in range(self.main_view.inputs_cursor):
            if self.main_view.inputs[i] == "\n":
                x = 0
                y += 1
            else:
                x += 1
            if x > len(lines[y]):
                x = 1
                y += 1
        return x, y

    async def redraw(self):
        self.recompute_dimensions()

        self.stdscr.clear()
        self.draw_chats()
        await self.draw_messages()
        if self.main_view.mode == "search":
            if self.main_view.search_result == []:
                self.stdscr.addstr(self.H - 1, 0, "/" + self.main_view.search_box, self.main_view.colors["error"])
            else:
                self.stdscr.addstr(self.H - 1, 0, "/" + self.main_view.search_box)
        elif self.main_view.mode in ["popup", "popupmessage"]:
            _, question = self.main_view.popup
            text = question + (self.main_view.popup_input or "")
            self.stdscr.addstr(self.H - 1, 0, text)
        elif self.main_view.mode == "vimmode":
            self.stdscr.addstr(self.H - 1, 0, ":" + self.main_view.vimline_box)
        else:
            suffix = f"recording {self.main_view.macro_recording}" if self.main_view.macro_recording else ""
            mode = f"--{self.main_view.mode.upper()}--" if self.main_view.mode != "normal" else ""
            if (self.main_view.mode != "normal"):
                self.stdscr.addstr(self.H - 1, 0, mode + suffix)
        self.stdscr.addstr(self.H - 1, int(self.W * 2/3), self.main_view.command_box[:8])

        # draw inputs if any mode but forwarding
        if self.main_view.mode.startswith("fw"): # list messages being forwarded
            fwtext = []
            for message in self.main_view.forward_messages:

                msgtext = ""
                if message.text:
                    msgtext = message.text if len(message.text) < 20 else f"{message.text[0:18]}..."

                mediatext = ""
                if message.media:
                    mediatext, _ = self.get_media_type(message)

                displaytext = f"[ {msgtext}{' ' if msgtext and mediatext else ''}({mediatext}) ]"

                fwtext.append(displaytext)
            fwtext = "    ".join(fwtext)
            for index, line in enumerate(self._get_input_lines(width = self.W - 4, inputs=fwtext)[-self.input_lines:]):
                self.stdscr.addstr(self.H - self.input_lines - 2 + index, 2, f"{line}")
        else: # draw inputs as usual
            for index, line in enumerate(self._get_input_lines(width = self.W - 4)[-self.input_lines:]):
                self.stdscr.addstr(self.H - self.input_lines - 2 + index, 2, f"{line}")
        
        if self.main_view.mode in ["insert", "edit"]:
            curses.curs_set(1)
            x, y = self._get_cursor_position(width = self.W - 4)
            self.stdscr.move(self.H - self.input_lines - 2 + y, 2 + x)
        elif self.main_view.mode == "search":
            curses.curs_set(1)
            self.stdscr.move(self.H - 1, 1 + len(self.main_view.search_box))
        elif self.main_view.mode == "vimmode":
            curses.curs_set(1)
            self.stdscr.move(self.H - 1, 1 + len(self.main_view.vimline_box))
        elif self.main_view.mode == "popup" and self.main_view.popup_input is not None:
            curses.curs_set(1)
            self.stdscr.move(self.H - 1, len(text))
        else:
            curses.curs_set(0)
        self.stdscr.refresh()

    def format(self, text, attributes = None, width = None, alignment = "left", inner_alignment = "left", truncation = "..."):
        if attributes == None:
            attributes = self.main_view.colors["default"]
        if width == None:
            width = len(text)
        return {
                "text": text,
                "attributes": attributes,
                "width": width,
                "alignment": alignment,
                "inner_alignment": inner_alignment,
                "truncation": truncation
                }

    def _datestring(self, date):
        now = datetime.datetime.now().astimezone()
        today = datetime.date.today()
        if (now - date).total_seconds() < 20*3600:
            out = date.strftime(f"%I:%M %p")
            return out
        if (now - date).total_seconds() < 6*86400:
            return date.strftime("%A")
        return date.strftime("%d.%m.%y")

    def draw_frame(self, yoff, xoff, h, w, chars = "││──┌┐└┘", attributes = 0):
        for i in range(h):
            self.stdscr.addstr(yoff + i, xoff, chars[0], attributes)
        for i in range(h):
            self.stdscr.addstr(yoff + i, xoff + w, chars[1], attributes)
        for i in range(w):
            self.stdscr.addstr(yoff, xoff + i, chars[2], attributes)
        for i in range(w):
            self.stdscr.addstr(yoff + h, xoff + i, chars[3], attributes)
        self.stdscr.addstr(yoff, xoff, chars[4], attributes)
        self.stdscr.addstr(yoff, xoff + w, chars[5], attributes)
        self.stdscr.addstr(yoff + h, xoff, chars[6], attributes)
        self.stdscr.addstr(yoff + h, xoff + w, chars[7], attributes)

    def draw_chats(self):
        selected_chat_index = self.main_view.selected_chat - self.main_view.selected_chat_offset
        offset = self.main_view.selected_chat_offset
        try:
            self.draw_frame(0,0, self.chats_height , self.chats_width)
            index = 0
            y = 1
            chats_to_draw = self.chats_num
            while index < chats_to_draw:
                dialog = self.main_view.dialogs[index + offset]
                if dialog["dialog"].archived:
                    index += 1
                    chats_to_draw += 1
                    continue
                message = dialog["messages"][0] if len(dialog["messages"]) > 0 else dialog["dialog"].message
                message_string = message.text if message.text else "[Non-text object]"
                if self.main_view.text_emojis:
                    message_string = emojis.decode(message_string)
                chat_name = get_display_name(dialog["dialog"].entity)
                if self.main_view.text_emojis:
                    chat_name = emojis.decode(chat_name)

                from_string = get_display_name(message.sender)
                unread = dialog["unread_count"]
                unread_string = f"({unread} new)" if unread else ""
                date = dialog["dialog"].date
                date = date.astimezone()
                date_string = self._datestring(date)
                pinned = "* " if dialog["dialog"].pinned else "  "
                selected = selected_chat_index == index

                self.draw_text(
                        [
                        self.format("o" if dialog["online"] else " ", attributes = self.main_view.colors["secondary"]),
                        self.format(chat_name, attributes = self.main_view.colors["primary"] | curses.A_STANDOUT if selected else curses.A_BOLD, width = int(0.5 * self.chats_width)),
                        self.format(f" {str(index)} " if self.show_indices else "", attributes = self.main_view.colors["standout"]),
                        self.format(unread_string, attributes = self.main_view.colors["error"], alignment = "right"),
                        self.format(date_string, alignment = "right", attributes = self.main_view.colors["primary"]),
                        ],
                    y, 2, maxwidth = self.chats_width - 2)
                self.draw_text(
                        [
                        self.format(f"{from_string}:"),
                        self.format(message_string, width = self.chats_width - len(f"{from_string}: ") - 3)
                        ],
                    y + 1, 2, maxwidth = self.chats_width - 2)
                y += 3
                index += 1
        except Exception:
            show_stacktrace()
    
    def draw_text(self, format_dicts, y_off = 0, x_off = 0, screen = None, maxwidth = None, separator = " "):
        if maxwidth == None:
            maxwidth = sum(format_dict["width"] for format_dict in format_dicts)            
        if screen == None:
            screen = self.stdscr
        left = [ x for x in format_dicts if x["alignment"] == "left" ] 
        right = list(reversed([ x for x in format_dicts if x["alignment"] == "right" ]))
        center = [ x for x in format_dicts if x["alignment"] == "center" ]
        entries = [ (x, "left") for x in left ] + [ (x, "right") for x in right ] + [ (x, "center") for x in center ]
        x_left = 0
        x_right = maxwidth -1
        for (format_dict, alignment) in entries:
            text = format_dict["text"]
            text = text.replace("\n", "")
            attributes = format_dict["attributes"]
            width = format_dict["width"]
            inner_alignment = format_dict["inner_alignment"]
            truncation = format_dict["truncation"]
            # TODO: make this split preferrably at spaces and not show linebreaks
            display_text = text.split("\n")[0]
            if len(display_text) > width:
                if truncation:
                    # TODO: make this split preferrably at spaces and not show linebreaks
                    display_text = display_text[:width - len(truncation)] + truncation
                else:
                    display_text = display_text[:width] 
            rljust = " " * (width - len(display_text))
            
            if alignment == "left":
                if inner_alignment == "left":
                    screen.addstr(y_off, x_off + x_left, display_text, attributes)
                    x_left += len(display_text)
                    if rljust:
                        screen.addstr(y_off, x_off + x_left, rljust)
                    x_left += len(rljust)
                elif inner_alignment == "right":
                    if rljust:
                        screen.addstr(y_off, x_off + x_left, rljust)
                    x_left += len(rljust)
                    screen.addstr(y_off, x_off + x_left, display_text, attributes)
                    x_left += len(display_text)
                if left and format_dict != left[-1]:
                    screen.addstr(y_off, x_off + x_left, separator)
                    x_left += len(separator)
            elif alignment == "right":
                if inner_alignment == "left":
                    x_right -= len(text)
                    self.stdscr.addstr(y_off, x_off + x_right, text, attributes)
                    x_right -= len(rljust)
                    self.stdscr.addstr(y_off, x_off + x_right, rljust)
                elif inner_alignment == "right":
                    x_right -= len(rljust)
                    self.stdscr.addstr(y_off, x_off + x_right, rljust)
                    x_right -= len(text)
                    self.stdscr.addstr(y_off, x_off + x_right, text, attributes)
                if right and format_dict != right[-1]:
                    x_right -= len(separator)
                    self.stdscr.addstr(y_off, x_off + x_right, separator)
            elif alignment == "center":
                self.stdscr.addstr(y_off, maxwidth // 2 - len(display_text) // 2, display_text, attributes)


    def get_media_type(self, message):
        main_view = self.main_view
        if message.media:
            media_type = message.media.to_dict()["_"]
            if media_type == "MessageMediaPhoto":
                media_type = "Photo"
            elif media_type == "MessageMediaDocument":
                atts = message.media.document.attributes
                filename = [ x for x in atts if x.to_dict()["_"] == "DocumentAttributeFilename" ]
                sticker = [ x for x in atts if x.to_dict()["_"] == "DocumentAttributeSticker" ]
                if sticker:
                    stickertext = sticker[0].alt
                    if main_view.text_emojis:
                        stickertext = emojis.decode(stickertext)
                    media_type = f"{stickertext}  Sticker"
                elif filename:
                    filename = filename[0].to_dict()["file_name"]
                    media_type = f"Document ({filename})"
                else:
                    media_type = f"Document ({message.media.document.mime_type})"
            downloaded = " (saved)" if (message.id in main_view.dialogs[main_view.selected_chat]["downloads"]) else ""
            return (media_type, downloaded)
        return (None, None)



    def draw_message(self, main_view, chat_idx):
        messages = main_view.dialogs[main_view.selected_chat]["messages"]
        message = messages[chat_idx]

        maxtextwidth = int(self.single_chat_fraction * self.W) - 2
        lines = []
        if message.text:
            message_lines = message.text.split("\n")
            for message_line in message_lines:
                if main_view.text_emojis:
                    message_line = emojis.decode(message_line)
                if message_line == "":
                    lines += [""]
                else:
                    lines += [
                            message_line[maxtextwidth * i: maxtextwidth*i+maxtextwidth] 
                            for i in range(int(math.ceil(len(message_line)/maxtextwidth)))
                            ]
        if message.media:
            media_type, downloaded = self.get_media_type(message)
            lines += [ f"[{media_type}]{downloaded}" ]


        reply = ""
        if message.is_reply:
            reply_id = message.reply_to_msg_id
            reply = " r?? "
            for idx2, message2 in enumerate(main_view.dialogs[main_view.selected_chat]["messages"]):
                if message2.id == reply_id:
                    reply = f"r{idx2:02d}"
                    break

        from_message = message
        from_user = "You" if message.out else get_display_name(from_message.sender)
        via_user = f"   via   {get_display_name(from_message.forward.sender)}" if message.forward else ""
        user_string = f"{from_user}{via_user}   "
        out = []
        if message.out:
            out.append(f"{chat_idx}   {user_string}{self._datestring(message.date.astimezone())}".rjust(maxtextwidth))
            for idx, text in enumerate(lines):
                out.append(text.rjust(maxtextwidth - 4))
            #out.append(f"{chat_idx}   {message.date.hour}:{message.date.minute:02d}".rjust(maxtextwidth) + ".")
            if message.is_reply:
                out.append(reply)
        else:
            out.append(f"{chat_idx}   {user_string}{self._datestring(message.date.astimezone())}")
            for idx, text in enumerate(lines):
                out.append("    " + text)
            if message.is_reply:
                out.append(reply)
        return (out, message)

    async def load_messages(self, chat_index, amount = 50):
        # assert there are at least amount messages loaded
        main_view = self.main_view
        index = chat_index
        if len(main_view.dialogs[index]["messages"]) < amount :
            logging.info(f"only {len(main_view.dialogs[index]['messages'])} are loaded. lets load {2 * amount}")
            # to keep the amortized times of loading messages constant, double the number loaded every time
            temp =  await main_view.client.get_messages(main_view.dialogs[index]["dialog"], 2 * amount)
            main_view.dialogs[index]["messages"] = [ message for message in temp ]

    async def draw_messages(self, offset = 0):
        main_view = self.main_view

        await self.load_messages(main_view.selected_chat, main_view.message_offset + 50)
        messages = main_view.dialogs[main_view.selected_chat]["messages"]
        max_rows = self.H - self.input_lines - 3 - 1
        lines = []
        chat_count = 0
        while len(lines) < max_rows + offset and chat_count < len(messages):
            text, message = self.draw_message(main_view, chat_count + main_view.message_offset)
            for line in reversed(text):
                lines.append((line, message))
            lines.append(("",message))
            chat_count += 1
            # draw empty line after unread messages
            dialog = self.main_view.dialogs[main_view.selected_chat]
            unread = dialog["unread_count"]
            if (chat_count + main_view.message_offset == unread):
                lines.append((f"Unread Messages", "hlredwide"))
                lines.append(("", "hlred"))

        # draw frame now, so we can draw |- bow drawing characters
        self.draw_frame(0, self.chats_width + 1, self.chats_height, self.W - self.chats_width - 2)

        for i in range(min(len(lines)-offset, max_rows)):
            text, message = lines[i + offset]
            if message == "hlred":
                self.stdscr.addstr(max_rows - i, int(self.W * self.single_chat_fraction) + 2, text, self.main_view.colors["error"])
            elif message == "hlredwide":
                width = int(self.W * (1-self.single_chat_fraction) - 4)
                bar = "─"*(width*2//5 - 4)
                middlelen = self.W - len(bar) * 2 - int(self.W * self.single_chat_fraction)
                text = text.center(middlelen)
                self.stdscr.addstr(max_rows - i, int(self.W * self.single_chat_fraction) + 1, "├"+ bar)
                self.stdscr.addstr(max_rows - i, int(self.W * self.single_chat_fraction) + 2 + len(bar), text, self.main_view.colors["error"])
                self.stdscr.addstr(max_rows - i, int(self.W) - len(bar) - 1, bar + "┤")
            else:
                if message.out:
                    self.stdscr.addstr(max_rows - i, int(self.W * (1-self.single_chat_fraction) - 4) + 2, text)
                else:
                    self.stdscr.addstr(max_rows - i, int(self.W * self.chat_offset_fraction) + 2, text)
