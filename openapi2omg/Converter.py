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

    order_consume_http_successful_responses = ['200', '201', '202', '2XX',
                                               '204', 'default']

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

    def _get_argument_type(self, param_spec: dict) -> str:
        schema = param_spec.get('schema')
        content = param_spec.get('content')

        # No need to validate for the presence of both, schema and content,
        # since we know that the spec is valid already.
        if schema:
            return OpenAPIActionUtil.to_omg_type(schema['type'])
        else:  # content.
            raise ConverterError(
                'Using the "content" key to specify parameter serialising '
                'strategy is not supported at this time.')

    def _to_action(self, path: str, method: str, path_spec: dict) -> dict:
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

        arguments = {}

        action_def = {
            'help': path_spec.get('summary'),
            'http': {
                'port': 0,
                'method': method,
                'path': url  # TODO: do we want to introduce something like absolute_url in the OMG for this?
            },
            'arguments': arguments
        }

        self._insert_parameters(arguments, path_spec)
        self._insert_request_body(action_def, arguments, path_spec)
        self._insert_output(action_def, path_spec)

        return action_def

    def _insert_output(self, action_def: dict, path_spec: dict):
        all_responses = path_spec['responses']
        # TODO: create an issue in the OMG to support multiple responses
        # The OMG only supports successful responses right now,
        # so take any 2xx result.

        chosen_response = None

        for code in self.order_consume_http_successful_responses:
            chosen_response = all_responses.get(code)
            if chosen_response:
                break

        if chosen_response is None:
            # OpenAPI mandates at least one response code to be documented,
            # but it doesn't enforce that a successful response must be
            # documented. Default to an empty 2xx.
            # Only mock description, since it's a hard requirement for OpenAPI.
            chosen_response = {'description': 'Auto generated 2xx.'}

        description = chosen_response['description']
        content: dict = chosen_response.get('content', {})

        if not content or len(content) == 0:
            action_def['output'] = {'type': None, 'help': description}
            return

        content_type = self._get_preferred_content_type(content.keys())
        output_type = content[content_type]['schema']['type']

        output_type = OpenAPIActionUtil.to_omg_type(output_type)

        if content_type == 'text/plain':
            output_type = 'string'

        props = {}

        action_def['output'] = {
            'type': output_type,
            'contentType': content_type,
            'properties': props
        }

        if output_type == 'list':
            # TODO: OMG doesn't support describing array schema yet.
            return

        schema = content[content_type].get('schema', {})
        if len(schema.get('properties', {})) > 0:
            self._insert_arguments(props, schema,
                                   include_location=False)

    def _insert_arguments(self, arguments, content_spec,
                          include_location=True):
        for prop_name, prop_spec in content_spec['properties'].items():
            arg_type = OpenAPIActionUtil.to_omg_type(prop_spec['type'])

            arg = {
                'required': prop_spec.get('required', False),
                'type': arg_type,
                'in': 'requestBody'
            }

            if prop_spec.get('description'):
                arg['help'] = prop_spec.get('description')
            
            if not include_location:
                del arg['in']

            # TODO: add support for describing array contents.
            if arg_type == 'object':
                sub_props = {}
                self._insert_arguments(sub_props, prop_spec,
                                       include_location=False)
                arg['properties'] = sub_props
            arguments[prop_name] = arg

    def _get_preferred_content_type(self, possible_content_types) -> str:
        chosen_content_type = list(possible_content_types)[0]

        if len(possible_content_types) > 1 and \
                'application/json' in possible_content_types:
            chosen_content_type = 'application/json'

        return chosen_content_type

    def _insert_request_body(self, action, arguments, path_spec):
        request_body = path_spec.get('requestBody')
        if not request_body:
            return

        content = request_body['content']
        chosen_content_type = self._get_preferred_content_type(content.keys())

        action['http']['contentType'] = chosen_content_type

        content_spec = content[chosen_content_type]['schema']
        if content_spec['type'] == 'object':
            self._insert_arguments(arguments, content_spec)
        else:
            arg = {
                'help': content_spec.get('description'),
                'required': content_spec.get('required', False),
                'type': OpenAPIActionUtil.to_omg_type(content_spec['type']),
                'in': 'requestBody'
            }
            arguments[
                'root'] = arg  # TODO: umm, what to do here? There is no name as

    def _insert_parameters(self, arguments, path_spec):
        for param in path_spec.get('parameters', []):
            arg = {
                'help': param.get('description'),
                'required': param['required'],
                'type': self._get_argument_type(param),
                'in': OpenAPIActionUtil.to_omg_argument_location(param['in'])
            }
            arguments[param['name']] = arg

    def consume_paths(self):
        actions = {}
        self.omg['actions'] = actions

        for path in self.op_spec['paths']:
            for method, content in self.op_spec['paths'][path].items():
                if method not in ['get', 'head', 'post', 'put', 'delete',
                                  'patch']:
                    continue
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
        # No need to consume components, since these contain schemas,
        # and the references to these schemas are automatically traversed by
        # prance's ResolvingParser.
        pass

    def consume_security(self):
        # TODO: need to impl + add to the OMG
        pass

    def consume_tags(self):
        # The OMG has no placeholder for tags, so we do not consume them.
        pass

    def consume_external_docs(self):
        # No need to consume these since the OMG doesn't have/need this.
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
    with io.open('samples/algorithmia.json') as f:
        converter = Converter(json.load(f), properties={
            Properties.SERVER_INDEX: 0
        })
        converter.print()
