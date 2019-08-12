# -*- coding: utf-8 -*-
import re

from openapi2omg.exceptions.MappingError import MappingError


class OpenAPIActionUtil:
    PATTERN_WORD = re.compile(r'[a-z{}A-Z0-9]*')
    PATTERN_SANITIZE = re.compile(r'((?![a-zA-Z0-9]).)')

    @staticmethod
    def _gen_action_name(path: str, http_method: str, content: dict):
        res = OpenAPIActionUtil.PATTERN_WORD.finditer(path)
        action_name = http_method
        first_param_encountered = False
        for part in res:
            word = part.group()
            if word == '':
                continue

            if word.startswith('{'):
                ext = 'By'
                if first_param_encountered:
                    ext = 'And'

                append = ext + word[1:-1].capitalize()
                first_param_encountered = True
            else:
                append = word.capitalize()

            action_name += OpenAPIActionUtil._sanitize(append)

        return action_name

    @staticmethod
    def _sanitize(string: str) -> str:
        return re.sub(OpenAPIActionUtil.PATTERN_SANITIZE, '', string)

    @staticmethod
    def generate_action_name(path: str, http_method: str, content: dict):
        if content.get('operationId'):
            return content['operationId']

        return OpenAPIActionUtil._gen_action_name(path, http_method, content)

    _types = {
        'integer': 'int',
        'number': 'number',
        'string': 'string',
        'boolean': 'boolean',
        'array': 'list',
        'object': 'object'
    }

    @staticmethod
    def to_omg_type(openapi_type: str):
        omg_type = OpenAPIActionUtil._types.get(openapi_type)

        if omg_type is None:
            raise MappingError(f'The OpenAPI type {openapi_type} '
                               f'could not be mapped to an OMG type.')

        return omg_type

    _locations = {
        'query': 'query',
        'path': 'path',
        'header': 'header'  # TODO: add support for this in the OMG spec
    }

    @staticmethod
    def to_omg_argument_location(openapi_location: str):
        omg_location = OpenAPIActionUtil._locations.get(openapi_location)

        if omg_location is None:
            raise MappingError(
                f'The OpenAPI parameter location {openapi_location} '
                f'could not be mapped to an OMG parameter location.')

        return omg_location
