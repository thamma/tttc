from asyncio import Condition
import telethon 
import resources 
import curses
from tttcutils import debug, show_stacktrace

def bla(scr):
    lines = resources.tttc_logo
    tttw,ttth = len(lines[4]), len(lines)
    w, h = curses.COLS, curses.LINES
    yoff = h//2 - ttth//2
    xoff = w//2 - tttw//2
    for a in range(len(lines)):
        scr.addstr(yoff + a, xoff, lines[a])
    scr.refresh()

class AuthView():
    def __init__(self, client, stdscr):
        self.stdscr = stdscr
        self.client = client
        self.inputevent = Condition()
        self.inputs = ""
        self.w, self.h = curses.COLS, curses.LINES
        self.fin = False
        self.showinput = True


    async def textinput(self):
        self.stdscr.addstr("\n> ")
        self.stdscr.refresh()
        self.inputs = ""
        with await self.inputevent:
            await self.inputevent.wait()
        out = self.inputs
        self.inputs = ""
        self.stdscr.addstr("\n")
        self.stdscr.refresh()
        return out

    async def run(self):
        await self.client.connect()
        self.stdscr.addstr("connected")
        self.auth = await self.client.is_user_authorized()
        bla(self.stdscr)
        if not self.auth:
            while True:
                self.stdscr.addstr("Please enter your phone number: ")
                self.stdscr.refresh()
                self.phone = await self.textinput()
                try:
                    response = await self.client.send_code_request(self.phone.replace("+","00").replace(" ",""))
                    if not response.phone_registered:
                        self.stdscr.addstr("This phone number is not registered in telegram. ")
                        self.stdscr.refresh()
                    else:
                        break
                except telethon.errors.rpcerrorlist.FloodWaitError as err:
                    self.stdscr.addstr(f"The telegram servers blocked you for too many retries ({err.seconds}s remaining). ")
                    self.stdscr.refresh()
                except Exception as e: 
                    self.stdscr.addstr("Incorrect phone number. ")
                    self.stdscr.refresh()
            self.stdscr.addstr("Now authentificate with the code telegram sent to you.")
            self.stdscr.refresh()
            while True:
                try:
                    self.code = await self.textinput()
                    await self.client.sign_in(self.phone.replace("+","00").replace(" ",""), self.code)
                except telethon.errors.rpcerrorlist.PhoneCodeInvalidError:
                    self.stdscr.addstr("The authentification code was wrong. Please try again.")
                    self.stdscr.refresh()
                except telethon.errors.SessionPasswordNeededError:
                    self.showinput = False
                    self.stdscr.addstr("A 2FA password is required to log in.")
                    self.stdscr.refresh()
                    while True:
                        self.passwd = await self.textinput()
                        try:
                            await self.client.sign_in(password=self.passwd)
                        except telethon.errors.PasswordHashInvalidError:
                            self.stdscr.addstr("Incorrect password. Try again.")
                            self.stdscr.refresh()
        self.stdscr.addstr("Authentification successfull. Please wait until the client has finished loading.")
        self.stdscr.refresh()

    async def handle_key(self, key):
        if key == "RETURN":
            with await self.inputevent:
                self.inputevent.notify()
        elif key == "BACKSPACE":
            self.inputs = self.inputs[0:-1]
        else:
            self.inputs += key
        if self.showinput:
            self.stdscr.addstr(20, 50, self.inputs)
        else:
            self.stdscr.addstr(20, 50, "*"*len(self.inputs))
        self.stdscr.clrtoeol()
        self.stdscr.refresh()

