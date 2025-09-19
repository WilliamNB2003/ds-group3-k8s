class Msg:
    src: int
    dst: int # We need a case for broadcast aswell
    type: str # Election, OK, Coordinator, Bootup, BootupResponse, ping
    payload: str # Extra information e.g. election id or leader id

    def __init__(self, src: int, dst: int, type: str, payload: str):
        self.src = src
        self.dst = dst
        self.type = type
        self.payload = payload

    def format(self):
        return f"/{self.src}|{self.dst}|{self.type}|{self.payload}".encode()