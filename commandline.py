import argparse
import sys
import commandline
import re
import curses
from telethon import sync, TelegramClient
import os
import tttcutils


def handle():
    parser = argparse.ArgumentParser(description="Run with no arguments to start interactive mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Be verbose")  
    parser.add_argument("--colortest", action="store_true", help="Test the used curses color pallet")

    contacts = parser.add_argument_group("contacts")
    contacts.add_argument("--list", "-l", action="store_true", help="List available dialogs with chat ids")
    contacts.add_argument("--startswith", "-s", metavar="S",
            help="Search for a contact starting with S (case sensitive). Can be used with messaging options if result is unique.")
    contacts.add_argument("--contains", "-c", metavar="C", 
            help="Search for a contact containing S (case sensitive). Can be used with messaging options if result is unique.")
    contacts.add_argument("--matches", "-x", metavar="M", 
            help="Search for a contact matching regular expression M. Can be used with messaging options if result is unique.")

    messaging = parser.add_argument_group("messaging")
    messaging.add_argument("--me", action="store_true", help="Send the message to yourself")
    messaging.add_argument("--target", "-t", metavar="chatid", type=int, help="Send the message to the given chat")
    messaging.add_argument("--message", "--msg", "-m", help="Provide a message.")
    messaging.add_argument("--stdin", "-i", action="store_true", help="Read a message from stdin.")
    parsed = parser.parse_args()
    global debug
    if parsed.verbose:
        def debug(*args, **kwargs):
            print(*args, **kwargs)
    else:
        def debug(*args, **kwargs):
            pass

    interactive = len(sys.argv) == 1
    if interactive:
        return False
    elif parsed.colortest:
        with ColorSample() as c:
            c.show()
        return True
    else:
        api_id, api_hash = tttcutils.assert_environment()
        client = TelegramClient(tttcutils.sessionfile(), api_id, api_hash)
        debug("Connecting...", file=sys.stderr)
        client.connect()
        debug("Connected.", file=sys.stderr)
        if not client.is_user_authorized():
            print("Please use the interactive client first to authorize and create a tttc.session file. Aborting.", file=sys.stderr)
            exit(1)
        debug("Client is authorized.", file=sys.stderr)
        if parsed.startswith or parsed.list or parsed.matches or parsed.contains:
            global chats
            debug("Fetching chats...", file=sys.stderr)
            chats = client.get_dialogs()

        filtered = chats if parsed.list else filter_chats((parsed.startswith, parsed.contains, parsed.matches))
        unique = None
        if filtered:
            if len(filtered) == 0:
                print("No matching chats found.")
            elif len(filtered) > 1:
                for result in reversed(filtered):
                    print(str(result.id).rjust(16) + " "*4 + result.name)
            else:
                if not (parsed.message or parsed.stdin):
                    for result in reversed(filtered):
                        print(str(result.id).rjust(16) + " "*4 + result.name)                 
                    exit()
                unique = filtered[0].id
        if not (parsed.message or parsed.stdin):
            exit() # we are done here
        
        recipient = unique or parsed.target
        if not recipient and parsed.me:
            recipient = client.get_me().id
        if not recipient:
            if len(filtered) > 1:
               print("Recipient ambiguous. Aborting.")
            else:
                print("No recipient provided.")
            exit()
        #try:
        #    pass
        #    #recipient = client.get_input_entity(recipient)
        #    #client.get_entity(recipient)
        #except ValueError:
        #    print("Illegal entity id. Aborting.", file=sys.stderr)
        #    exit(1)

        if parsed.message or parsed.stdin:
            send_message(client, recipient, message=parsed.message)
        return True

def send_message(client, chat_id, message):
    #print(f"call to {client} {chat_id} {message}")
    try:
        recipient = client.get_input_entity(chat_id)
    except ValueError:
        print("Could not find the entity for this entity id. Aborting.", file=sys.stderr)
        exit(1)
    debug("Chat exists. Sending message.", file=sys.stderr)
    if message is None:
        debug("No message specified. Reading from stdin.", file=sys.stderr)
        message = "".join([line for line in sys.stdin])
    if message.strip() == "":
        print("The message must not be empty.", file=sys.stderr)
        exit()
    client.send_message(chat_id, message)

def filter_chats(filt):
    if filt == (None, None, None):
        return None
    starts, contains, matches = filt
    if starts:
        return [ chat for chat in chats if chat.name.startswith(starts) ]
    elif contains:
        return [ chat for chat in chats if contains in chat.name ]
    else:
        reg = re.compile(matches)
        return [ chat for chat in chats if reg.match(chat.name) ]
    
class ColorSample:
    def __init__(self):
        pass

    def __enter__(self):
        self.stdscr = curses.initscr()
        curses.start_color()
        curses.use_default_colors()
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(1)
        self.stdscr.refresh()
        return self

    def __exit__(self, *args):
        curses.nocbreak()
        self.stdscr.keypad(0)
        curses.echo()
        curses.endwin()
        return False

    def show(self):
        self.stdscr.addstr("These are all the colors your terminal supports (and their codes):\n")
        for i in range(curses.COLORS): 
            curses.init_pair(i, i, -1); 
            self.stdscr.addstr(f" {i} ", curses.color_pair(i))
            self.stdscr.addstr(f" {i} ", curses.A_STANDOUT |  curses.color_pair(i))
        self.stdscr.addstr("\n\n")
        self.stdscr.addstr("Press any key to continue.")
        self.stdscr.getch()
        self.stdscr.refresh()
        self.stdscr.clear()
        self.stdscr.addstr("TTTC uses these colors. Refer to the previous page for their color codes. You can adjust them in the config:\n", curses.color_pair(0))
        from config import colors
        for (i, (k, v)) in enumerate(colors.colors.items()):
            f, b = v
            curses.init_pair(i+1, f, b); 
            self.stdscr.addstr(f"{k.ljust(25)} {v}\n", curses.color_pair(i+1))
            self.stdscr.refresh()
        self.stdscr.refresh()
        self.stdscr.getch()
