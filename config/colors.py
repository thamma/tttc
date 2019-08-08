import curses

colors_256 = {
    "default": (255, -1),
    "default_highlight": (255, 8),
    "primary": (14, -1),
    "secondary": (10, -1),
    "ternary": (11, -1),
    "standout": (0, 3),
    "error": (9, -1),
    "accent": (237, -1)
}
colors_8 = {
    "default": (7, -1),
    "default_highlight": (0, 7),
    "primary": (6, -1),
    "secondary": (2, -1),
    "ternary": (5, -1),
    "standout": (7, 3),
    "error": (1, -1),
    "accent": (7, -1)
}
colors = colors_256 if curses.COLORS >= 256 else colors_8  
def get_colors():
    for (i, (k, v)) in enumerate(colors.items()):
        f, b = v
        curses.init_pair(i+1, f, b); 
    return { k: curses.color_pair(i+1) for (i, (k,v)) in enumerate(colors.items()) } 

