# TTTC, the telegram client

TTTC is an unofficial [Telegram](https://telegram.org/) commandline client.
It aims to provide a user experience similar to that of [VIM](https://www.vim.org/).


## Requirements
TTTC uses the `curses` and `telethon` python libraries. Curses is usually shipped with
your python installation, but `telethon` can easily be installed via `pip`.

In order to use TTTC, you will need your own Telegram `api_id` and `api_hash`.
You can read more about how to get them [here](https://core.telegram.org/api/obtaining_api_id).

Once you obtained your own api key and hash, you need to set them as your environment variables
`TTTC_API_ID` and `TTTC_API_HASH`, respectively.

The client can be run with `python3 tttc.py`.