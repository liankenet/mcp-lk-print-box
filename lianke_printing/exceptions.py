class LiankePrintingException(Exception):
    def __init__(self, code: int | None, msg: str, client=None, request=None, response=None):
        """
        :param code: Error code
        :param msg: Error message
        """
        self.code = code
        self.msg = msg
        self.client = client
        self.request = request
        self.response = response

    def __str__(self):
        s = f"Error code: {self.code}, message: {self.msg}"
        return s

    def __repr__(self):
        _repr = f"{self.__class__.__name__}({self.code}, {self.msg})"
        return _repr
