# -*- coding: utf-8 -*-
from openapi2omg.exceptions.MappingError import MappingError


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
