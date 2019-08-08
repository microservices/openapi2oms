# -*- coding: utf-8 -*-


class ConverterError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
