class CodeRegistry:
    def __init__(self):
        self.seen = set()
    def add(self, code):
        key = code.replace("-", "").upper()
        if key in self.seen:
            return False
        self.seen.add(key)
        return True
