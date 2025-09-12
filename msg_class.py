class Msg:
    src: int
    dst: int # We need a case for broadcast aswell
    type: str # Election, OK, Coordinator, Bootup, BootupResponse
    payload: str # Extra information e.g. election id or leader id

    def __init__(self, type: str, src: int, dst: int, ):
        pass

    def send(self):
        return f"/{self.src}|{self.dst}|{self.type}|{self.payload}".encode()