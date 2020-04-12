#!/bin/python

from authview import AuthView
from functools import partial
from mainview import MainView
from queue import Queue
from telethon import TelegramClient
from telethon import events
from time import sleep
import argparse
import asyncio
import commandline
import concurrent
import curses
import resources
import sys
import os
from tttcutils import debug, show_stacktrace
import tttcutils

class Display:
    def __init__(self, loop):
        self.loop = loop
        api_id, api_hash = tttcutils.assert_environment()
        self.client = TelegramClient(tttcutils.sessionfile(), api_id, api_hash, loop=self.loop)


    def __enter__(self):
        self.stdscr = curses.initscr()
        curses.start_color()
        curses.use_default_colors()
        for i in range(curses.COLORS):
            curses.init_pair(i, i, -1); 
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

    async def main(self):
        tasks = [
                self.run(),
                self.get_ch()
                ]
        await asyncio.wait(tasks)
        

    async def run(self):
        self.view = AuthView(self.client, self.stdscr)
        await self.view.run()
        self.view = MainView(self.client, self.stdscr)
        await self.view.run()

    async def get_ch(self):
        while True:
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            a = await self.loop.run_in_executor(pool, self.stdscr.get_wch)
            out = resources.key_mapping.get(a, str(a))
            if self.view:
                await self.view.handle_key(out)
                if self.view.fin:
                    return


if commandline.handle():
    exit()
elif __name__ == '__main__':
    loop = asyncio.get_event_loop()
    os.environ.setdefault('ESCDELAY', '25')
    with Display(loop) as display:
        loop.run_until_complete(display.main())
