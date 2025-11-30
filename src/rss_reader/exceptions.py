class URLValidationError(Exception):
    def __init__(self, message):
        self.message = message

# TODO: может сделать middleware для поимки ApplicationLogicException, и таким образом упростить работу с ошибками?