# -*- coding: utf-8 -*-
"""
Parsers accept linter output and return file paths and all of the violations in that file.
"""
import collections
import json
import os
import re

from .violations import Violation


class BaseLintParser(object):

    def parse_violations(self, output):
        raise NotImplementedError


class LineRegexParser(BaseLintParser):
    """
    A parser that runs a regular expression on each line of the output to return violations.
    The regex should match the following capture groups:

        - path
        - line
        - column
        - code
        - message
    """

    def __init__(self, regex):
        self.regex = regex

    def parse_violations(self, output):
        violations = collections.defaultdict(list)

        line_regex = re.compile(self.regex)

        # Collect all the issues into a dict where the keys are the file paths and the values are a
        # list of the issues in that file.
        for line in output.strip().splitlines():
            clean_line = line.strip()

            match = line_regex.match(clean_line)

            if not match:
                continue

            path = os.path.normpath(match.group('path'))

            violation = Violation(
                line=int(match.group('line')),
                column=int(match.group('column')),
                code=match.group('code'),
                message=match.group('message')
            )

            violations[path].append(violation)

        return violations


class PylintJSONParser(BaseLintParser):
    """
    Pylint JSON format:

        [
            {
                "type": "convention",
                "module": "lintly.backends.base",
                "obj": "BaseGitBackend.post_status",
                "line": 54,
                "column": 4,
                "path": "lintly/backends/base.py",
                "symbol": "missing-docstring",
                "message": "Missing method docstring",
                "message-id": "C0111"
            }
        ]
    """

    def parse_violations(self, output):
        # Sometimes pylint will output "No config file found, using default configuration".
        # This handles that case by removing that line.
        if output and output.startswith('No config'):
            output = '\n'.join(output.splitlines()[1:])

        json_data = json.loads(output)

        violations = collections.defaultdict(list)

        for violation_json in json_data:
            violation = Violation(
                line=violation_json['line'],
                column=violation_json['column'],
                code='{} ({})'.format(violation_json['message-id'], violation_json['symbol']),
                message=violation_json['message']
            )

            path = os.path.normpath(violation_json['path'])
            violations[path].append(violation)

        return violations


class ESLintParser(BaseLintParser):

    def parse_violations(self, output):
        violations = collections.defaultdict(list)

        current_file = None

        # Collect all the issues into a dict where the keys are the file paths and the values are a
        # list of the issues in that file.
        for line in output.strip().splitlines():
            if line.startswith(' '):
                # This line is a linting violation
                regex = r'^(?P<line>\d+):(?P<column>\d+)\s+(error|warning)\s+(?P<message>.*)\s+(?P<code>.+)$'
                match = re.match(regex, line.strip())

                violation = Violation(
                    line=int(match.group('line')),
                    column=int(match.group('column')),
                    code=match.group('code').strip(),
                    message=match.group('message').strip()
                )
                violations[current_file].append(violation)
            elif line.startswith('✖'):
                # We're at the end of the file
                break
            else:
                # TODO: ESLint defaults to absolute paths rather than relative paths, which
                # will fail when matching against files in a diff.
                # This line is a file path
                current_file = os.path.normpath(line)

        return violations


class StylelintParser(BaseLintParser):

    def parse_violations(self, output):
        violations = collections.defaultdict(list)

        current_file = None

        # Collect all the issues into a dict where the keys are the file paths and the values are a
        # list of the issues in that file.
        for line in output.strip().splitlines():
            if line.startswith(' '):
                # This line is a linting violation
                regex = r'^(?P<line>\d+):(?P<column>\d+)\s+✖\s+(?P<message>.*)\s+(?P<code>.+)$'
                match = re.match(regex, line.strip())

                violation = Violation(
                    line=int(match.group('line')),
                    column=int(match.group('column')),
                    code=match.group('code').strip(),
                    message=match.group('message').strip()
                )
                violations[current_file].append(violation)
            else:
                # This line is a file path
                current_file = os.path.normpath(line)

        return violations


DEFAULT_PARSER = LineRegexParser(r'^(?P<path>.*):(?P<line>\d+):(?P<column>\d+): (?P<code>\w\d+) (?P<message>.*)$')


PARSERS = {
    # Default flake8 format
    # docs/conf.py:230:1: E265 block comment should start with '# '
    # path:line:column: CODE message
    'unix': DEFAULT_PARSER,
    'flake8': DEFAULT_PARSER,

    # Pylint ---output-format=json
    'pylint-json': PylintJSONParser(),

    # ESLint's default formatter
    # /Users/grant/project/file1.js
    #     1:1    error  '$' is not defined                              no-undef
    'eslint': ESLintParser(),

    # ESLint's unix formatter
    # lintly/static/js/scripts.js:69:1: 'lintly' is not defined. [Error/no-undef]
    # path:line:column: message [CODE]
    'eslint-unix': LineRegexParser(r'^(?P<path>.*):(?P<line>\d+):(?P<column>\d+): '
                                   r'(?P<message>.+) \[(Warning|Error)/(?P<code>.+)\]$'),

    # Stylelint's default formatter
    # lintly/static/sass/file1.scss
    #   13:1  ✖  Expected no more than 1 empty line   max-empty-lines
    'stylelint': StylelintParser(),

}
