from functools import wraps
from tttcutils import debug
import emojis

# Im am very dissatisfied with using a global variable here
handlers = {}

class KeyHandler:

    def __init__(self, main_view):
        self.main_view = main_view
        global handlers
        self.handles = handlers

    async def handle_key(self, key):
        mode = self.main_view.mode

        #TODO: this should probably go somewhere else
        if not self.main_view.ready:
            return
        if key == "RESIZE":
            self.main_view.drawtool.resize()
            return
        if self.main_view.mode == "popupmessage":
            self.main_view.modestack.pop()
            await self.main_view.drawtool.redraw()
        if self.main_view.macro_recording:
            if key != "q":
                self.main_view.macro_sequence.append(key)

        if (self.main_view.mode, key) in self.handles:
            await self.handles[(self.main_view.mode, key)](self, key)
        elif (self.main_view.mode, True) in self.handles:
            await self.handles[(self.main_view.mode, True)](self, key)
        else:
            self.command_box = ""
        await self.main_view.drawtool.redraw()

    def handle(mode, key = []):
        def deco(f):
            global handlers
            keys = key if isinstance(key, list) else [ key ]
            for k in keys:
                handlers[(mode, k)] = f
        return deco
    
    @handle("normal", "c")
    async def _handle_key(self, key):
        self.main_view.select_next_chat()

    @handle("normal", "C")
    async def _handle_key(self, key):
        self.main_view.select_prev_chat()

    @handle("search", ["ESCAPE", "RETURN"])
    async def _handle_key(self, key):
        self.main_view.mode = "normal"

    @handle("search", "BACKSPACE")
    async def _handle_key(self, key):
        if self.main_view.search_box == "":
            self.main_view.mode = "normal"
        else:
            self.main_view.search_box = self.search_box[0:-1]
            self.main_view.search_chats()
            self.main_view.search_next()

    @handle("search", True)
    async def _handle_key(self, key):
        self.main_view.search_box += key
        self.main_view.search_chats()
        self.main_view.search_next()

    @handle("vimmode", "ESCAPE")
    async def _handle_key(self, key):
        self.main_view.mode = "normal"

    @handle("vimmode", "RETURN")
    async def _handle_key(self, key):
        await self.main_view.call_command()
        self.main_view.vimline_box = ""
        self.main_view.mode = "normal"

    @handle("vimmode", "BACKSPACE")
    async def _handle_key(self, key):
        if self.main_view.vimline_box == "":
            self.main_view.mode = "normal"
        else:
            self.main_view.vimline_box = self.vimline_box[0:-1]

    @handle("vimmode", True)
    async def _handle_key(self, key):
        self.main_view.vimline_box += key

    @handle("normal", True)
    async def _handle_key(self, key):
        num = None
        try:
            num = int(key)
            if num is not None:
                self.main_view.command_box += str(num)
        except:
            pass
        
    @handle("normal", ":")
    async def _handle_key(self, key):
        self.main_view.mode = "vimmode"
        self.main_view.vimline_box = ""
    
    @handle("normal", ["RETURN", "Y"])
    async def _handle_key(self, key):
        await self.main_view.send_message()


    @handle("normal", "Q")
    async def _handle_key(self, key):
        await self.main_view.quit()
    
    @handle("normal", "q")
    async def _handle_key(self, key):
        if self.main_view.macro_recording == None:
            # start macro recording
            async def record_macro(main_view, key):
                if "a" <= key.lower() <= "z":
                    main_view.macro_recording = key
                    main_view.modestack.pop() # previously popup
                    main_view.popup_message(f"recording into {key}")
                else:
                    main_view.modestack.pop() # previously popup
                    main_view.popup_message(f"Register must be [a-zA-Z]")
                return False # dont let the key be handled normally

            self.main_view.spawn_popup(record_macro, "Record into which register?")
        else:
            self.main_view.popup_message(f"Macro recorded into {self.macro_recording}")
            # end macro recording
            self.main_view.macros[self.macro_recording] = self.macro_sequence
            self.main_view.macro_recording = None
            self.main_view.macro_sequence = []
    
    @handle("normal", "@")
    async def _handle_key(self, key):
        # execute macro
        async def ask_macro(main_view, key):
            main_view.modestack.pop()
            if key in main_view.macros.keys():
                macro = main_view.macros[key]
                for k in macro:
                    await main_view.handle_key(k, redraw = False)
            else:
                main_view.popup_message(f"No such macro @{key}")
            return False
        keys = ", ".join(self.main_view.macros.keys())
        self.main_view.spawn_popup(ask_macro, f"Execute which macro?{f'   ({keys} exist)' if keys else ''}")
    
    @handle("normal", "UP")
    async def _handle_key(self, key):
        self.main_view.message_offset += 1
    
    @handle("normal", "DOWN")
    async def _handle_key(self, key):
        self.main_view.message_offset = max(0, self.message_offset - 1)
    
    @handle("normal", "E")
    async def _handle_key(self, key):
        self.main_view.text_emojis ^= True
    
    @handle("normal", "R")
    async def _handle_key(self, key):
        await self.main_view.mark_read()
    
    @handle("normal", "d")
    async def _handle_key(self, key):
        if self.main_view.command_box:
            try:
                n = int(self.main_view.command_box)
            except:
                return
            if n >= len(self.main_view.dialogs[self.main_view.selected_chat]["messages"]):
                self.main_view.popup_message("No message by that id.")
            async def action_handler(main_view, key):
                if key in ["y","Y"]:
                    to_delete = main_view.dialogs[main_view.selected_chat]["messages"][n]
                    await to_delete.delete()
                    main_view.dialogs[main_view.selected_chat]["messages"].pop(n)
                    main_view.command_box = ""
                main_view.modestack.pop()
                main_view.popup_input = None
            question = f"Are you really sure you want to delete message {n}? [y/N]"
            self.main_view.spawn_popup(action_handler, question)

    
    @handle("normal", "e")
    async def _handle_key(self, key):
        if self.main_view.command_box:
            try:
                n = int(self.main_view.command_box)
            except:
                return
            self.main_view.edit_message = self.main_view.dialogs[self.main_view.selected_chat]["messages"][n]
            self.main_view.mode = "edit"
            self.main_view.inputs = emojis.decode(self.main_view.edit_message.text)
            self.main_view.command_box = ""
    
    
    @handle("normal", "y")
    async def _handle_key(self, key):
        if self.main_view.command_box:
            try:
                n = int(self.main_view.command_box)
            except:
                return
            yank = self.main_view.dialogs[self.selected_chat]["messages"][n].text
            pyperclip.copy(yank)
            self.main_view.command_box = ""
    
    
    @handle("normal", "r")
    async def _handle_key(self, key):
        if self.main_view.command_box:
            try:
                n = int(self.main_view.command_box)
            except:
                return
            reply_to = self.main_view.dialogs[self.selected_chat]["messages"][n]
            s = emojis.encode(self.main_view.inputs)
            reply = await reply_to.reply(s)
            await self.main_view.on_message(reply)
            self.main_view.command_box = ""
            self.main_view.inputs = ""
    
    
    @handle("normal", ["l", "L"])
    async def _handle_key(self, key):
        force = (key == "L")
        if self.main_view.command_box:
            try:
                n = int(self.main_view.command_box)
            except:
                return
            self.main_view.command_box = ""
            await self.main_view.download_attachment(n, force)
    
    
    @handle("normal", "o")
    async def _handle_key(self, key):
        if self.main_view.command_box:
            try:
                n = int(self.main_view.command_box)
            except:
                return
            self.main_view.command_box = ""
            await self.main_view.open_link(n)
    
    @handle("normal", "m")
    async def _handle_key(self, key):
        if self.main_view.command_box:
            try:
                n = int(self.main_view.command_box)
            except:
                return
            self.main_view.command_box = ""
            await self.main_view.show_media(n)

    @handle("normal", "M")
    async def _handle_key(self, key):
        self.main_view.center_selected_chat()
    
    @handle("normal", ["HOME", "g"])
    async def _handle_key(self, key):
        self.main_view.select_chat(0)

    @handle("normal", ["END", "G"])
    async def _handle_key(self, key):
        self.main_view.select_chat(-1)

    @handle("normal", "i")
    async def _handle_key(self, key):
        self.main_view.mode = "insert"

    @handle("normal", "n")
    async def _handle_key(self, key):
        self.main_view.search_next()

    @handle("normal", "N")
    async def _handle_key(self, key):
        self.main_view.search_prev()

    @handle("normal", "/")
    async def _handle_key(self, key):
        self.main_view.mode = "search"
        self.main_view.search_box = ""

    @handle("normal", " ")
    async def _handle_key(self, key):
        self.main_view.drawtool.show_indices ^= True

    @handle("popup", True)
    async def _handle_key(self, key):
        action, _ = self.main_view.popup
        # I think this could break
        await action(self.main_view, key)

    @handle("edit", "ESCAPE")
    async def _handle_key(self, key):
        async def ah(self, key):
            self.modestack.pop() # leave popup mode
            self.modestack.pop() # leave edit mode
            if key in ["Y", "y", "RETURN"]:
                edit = await self.edit_message.edit(self.inputs)
                dialog = self.dialogs[self.selected_chat]
                msg_index = next((index for index, message in enumerate(dialog["messages"]) if message.id == edit.id), None)
                if msg_index != None:
                    dialog["messages"][msg_index] = edit
                else:
                    pass # this is not supposed to happen
            else:
                self.popup_message("Edit discarded.")
            self.inputs = ""
            return False
        self.main_view.spawn_popup(ah, "Do you want to save the edit? [Y/n]")

    @handle("edit", "BACKSPACE")
    async def _handle_key(self, key):
        self.main_view.inputs = self.main_view.inputs[0:-1]

    @handle("edit", "RETURN")
    async def _handle_key(self, key):
        self.main_view.inputs += "\n"

    @handle("edit", True)
    async def _handle_key(self, key):
        self.main_view.inputs += key

    @handle("insert", "ESCAPE")
    async def _handle_key(self, key):
        self.main_view.mode = "normal"

    @handle("insert", "LEFT")
    async def _handle_key(self, key):
        self.main_view.insert_move_left()

    @handle("insert", "RIGHT")
    async def _handle_key(self, key):
        self.main_view.insert_move_right()

    @handle("insert", "BACKSPACE")
    async def _handle_key(self, key):
        self.main_view.inputs = self.main_view.inputs[0:-1]

    @handle("insert", "RETURN")
    async def _handle_key(self, key):
        self.main_view.inputs += "\n"

    @handle("insert", True)
    async def _handle_key(self, key):
        self.main_view.inputs += key

    @handle("insert", "NUM_RETURN")
    async def _handle_key(self, key):
        self.main_view.modestack.pop()
        await self.main_view.send_message()
