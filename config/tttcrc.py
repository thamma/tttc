# Colors
# How much space should the contacts area use?
split_ratio = 0.3
# set to None for transparency
background = None
primary = curses.COLOR_CYAN
highlight = curses.COLOR_RED

# General
bootscreen_duration = 0.4
contacts_scroll_offset = 0
messages_scroll_offset = 0

## Contacts
pinned_group = True
pinned_symbol = ""
# indicate the amount of unread messages next to the contacts name
new_messages = True

# characters to indicate chat type
symbol_read = "✔"
symbol_channel = "C"
symbol_group = "G"
symbol_supergroup = "S"
symbol_private = "P"

time_today = "%I:%M %p"
# 6 days to prevent confusion with last weeks <this weekday>
# ie if today is monday "Mon" would refer to last weeks monday instead of today. change to 7*86400 if you're fine with that
time_lastweek = "%a"
lastweek = 6*86400
# anything that's not withing lastweek is considered longtimeago
time_longtimeago = "%d.%m.%y"

## Messages
message_edited = "edited"
message_forwarded = "<author> via <from>"
# when author and from match
message_forwarded_self = "via <author>"

# Keys
tttc_quit = "q"
vimline_open = ":"
contacts_search = "/"
contacts_top = "gg"
contacts_bottom = "G"
contacts_next = "c"
contacts_prev = "C"

# mind the escape sequence
messages_search = "\\"
messages_compose = "m"
# use xdg-open to open file/image
messages_visual_link = "l"
messages_visual_open = "o"
messages_visual_reply = "r"
messages_visual_next = "n"
messages_visual_prev = "N"
messages_visual_toggle_select = "space"
messages_visual_forward = "w"

compose_send = "y"
compose_edit = "e"
# add a file to the message, the message itself then becomes the caption
compose_file = "f"
# add image to the message, the message itself then becomes the caption
compose_image = "i"
# after having composed a message you can still select it as a reply to another message
compose_select_reply ="r"
