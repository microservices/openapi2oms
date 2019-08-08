# -*- coding: utf-8 -*-

class OpenAPIActionUtil:

    @staticmethod
    def _gen_action_name(path: str, http_method: str, content: dict):
        # TODO: impl me
        raise Exception('todo')

    @staticmethod
    def generate_action_name(path: str, http_method: str, content: dict):
        if content.get('operationId'):
            return content['operationId']

        return OpenAPIActionUtil._gen_action_name(path, http_method, content)
