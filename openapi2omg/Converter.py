# -*- coding: utf-8 -*-
from collections import namedtuple
import io
import json
import typing

from prance import ResolvingParser
from urllib.parse import urlparse

from openapi2omg import Properties
from openapi2omg.exceptions.ConverterError import ConverterError
from openapi2omg.utils.OpenAPIActionUtil import OpenAPIActionUtil

MappingPhase = namedtuple('MappingPhase', ['key', 'required', 'function'])


class Converter:
    """
    Implements an OpenAPI 3.0.2 converter. See
    https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md
    """

    phases: typing.List[MappingPhase] = None

    omg: dict = {'omg': 1, 'source': 'openapi'}

    http_base_url: str = ''

    def __init__(self, contents: dict, properties: dict):
        self.contents = contents
        self.phases = [
            MappingPhase('openapi', True, self.consume_version),
            MappingPhase('info', True, self.consume_info),
            MappingPhase('servers', False, self.consume_servers),
            MappingPhase('paths', True, self.consume_paths),
            MappingPhase('components', False, self.consume_components),
            MappingPhase('security', False, self.consume_security),
            MappingPhase('tags', False, self.consume_tags),
            MappingPhase('externalDocs', False, self.consume_external_docs)
        ]

        self.resolved_spec = ResolvingParser(
            spec_string=json.dumps(self.contents))

        if not properties:
            properties = {}

        self.properties = properties

        self.op_spec = self.resolved_spec.specification

    def consume_version(self):
        if self.op_spec['openapi'][0] != '3':
            raise ConverterError('Only OpenAPI version 3 is supported')

        self.omg['fromOpenAPIVersion'] = self.op_spec['openapi']

    def consume_info(self):
        op_info = self.op_spec['info']
        self.omg['info'] = {
            'version': op_info['version'],
            'title': op_info['title'],
            'description': op_info.get('description', ''),
            'license': {
                'name': op_info.get('license', {}).get('name', ''),
                'url': op_info.get('license', {}).get('url', '')
            }
        }

        self.omg['contact'] = {
            'name': self.op_spec.get('contact', {}).get('name', ''),
            'url': self.op_spec.get('contact', {}).get('url', ''),
            'email': self.op_spec.get('contact', {}).get('email', '')
        }

    def _to_action(self, path: str, method: str, content: dict) -> dict:
        base_url = self.http_base_url

        servers_for_this_path = self.op_spec['paths'][path].get('servers', {})
        if len(servers_for_this_path) > 0:
            if len(servers_for_this_path) > 1:
                raise ConverterError(
                    f'Multiple server endpoints were found for the '
                    f'path "{path}". Only zero or one entries are supported.')
            base_url = servers_for_this_path[0]['url']

        url = f'{base_url}{path}'

        parsed_url = urlparse(url)
        if parsed_url.scheme != 'http' and parsed_url.scheme != 'https':
            raise ConverterError(
                f'The URL for the path "{path}" is invalid. '
                f'Derived value is "{url}" (must have http(s) as the scheme)')

        action_def = {
            'help': '',  # TODO:
            'http': {
                'port': 0,
                'method': method,
                'path': url  # TODO: do we want to introduce something like absolute_url in the OMG for this?
            }
        }
        
        return action_def

    def consume_paths(self):
        actions = {}
        self.omg['actions'] = actions

        for path in self.op_spec['paths']:
            for method, content in self.op_spec['paths'][path].items():
                action_name = OpenAPIActionUtil.generate_action_name(
                    path, method, content)
                actions[action_name] = self._to_action(path, method, content)

    def consume_servers(self):
        servers = self.op_spec.get('servers', {})
        if len(servers) > 1 and \
                self.properties.get(Properties.SERVER_INDEX, -1) == -1:
            raise ConverterError(
                f'The property {Properties.SERVER_INDEX} must be set when '
                f'the OpenAPI spec contains more than 1 server. '
                f'Found {len(servers)} entries.')

        server_index = self.properties.get(Properties.SERVER_INDEX, 0)
        if server_index > len(servers) - 1:
            raise ConverterError(f'Invalid value set for property '
                                 f'{Properties.SERVER_INDEX}. '
                                 f'Min: 0, max: {len(servers) - 1}, '
                                 f'got: {server_index}')

        if len(servers) > 0:
            selected_server = servers[server_index]
            self.http_base_url = selected_server['url']
            if len(selected_server.get('variables', {})) > 0:
                raise ConverterError(
                    'Variables in the server object '
                    'are not supported at this time.')

    def consume_components(self):
        pass

    def consume_security(self):
        pass

    def consume_tags(self):
        pass

    def consume_external_docs(self):
        pass

    def convert(self) -> dict:
        for phase in self.phases:
            part = self.resolved_spec.specification.get(phase.key)
            if phase.required and part is None:
                raise ConverterError(
                    f'OpenAPI field {phase.key} not found in the root')

            if part is not None:
                phase.function()

        return self.omg

    def print(self):
        print(json.dumps(self.convert(), indent=True))


if __name__ == '__main__':
    with io.open('samples/petstore.json') as f:
        converter = Converter(json.load(f), properties={
            Properties.SERVER_INDEX: 0
        })
        converter.print()