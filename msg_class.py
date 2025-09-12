class Msg:
    src: int
    dst: int # We need a case for broadcast aswell
    type: str # Election, OK, Coordinator

    def __init__(self,):
        pass