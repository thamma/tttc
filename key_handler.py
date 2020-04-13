from functools import wraps

# Im am very dissatisfied with using a global variable here
handlers = {}

class KeyHandler:

    def __init__(self, main_view):
        self.main_view = main_view
        global handlers
        self.handles = handlers

    async def handle_key(self, key):
        mode = self.main_view.mode
        if ((mode, key) in self.handles):
            await self.handles[(mode, key)](self)

    def handle(mode, key):
        def deco(f):
            global handlers
            handlers[(mode, key)] = f
        return deco
    
    @handle("normal", "c")
    async def _handle_key(self):
        self.main_view.select_next_chat()

    @handle("normal", "C")
    async def _handle_key(self):
        self.main_view.select_prev_chat()


