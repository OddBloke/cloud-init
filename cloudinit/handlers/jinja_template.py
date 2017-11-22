# Copyright (C) 2012 Canonical Ltd.
# Copyright (C) 2012 Hewlett-Packard Development Company, L.P.
# Copyright (C) 2012 Yahoo! Inc.
#
# Author: Scott Moser <scott.moser@canonical.com>
# Author: Juerg Haefliger <juerg.haefliger@hp.com>
# Author: Joshua Harlow <harlowja@yahoo-inc.com>
#
# This file is part of cloud-init. See LICENSE file for license information.

import os

from cloudinit import handlers
from cloudinit.handlers.cloud_config import CloudConfigPartHandler
from cloudinit.handlers.shell_script import ShellScriptPartHandler
from cloudinit import log as logging
from cloudinit.sources import INSTANCE_JSON_FILE
from cloudinit.templater import render_string
from cloudinit.util import b64d, load_file, load_json

from cloudinit.settings import (PER_ALWAYS, PER_INSTANCE)

LOG = logging.getLogger(__name__)
JINJA_PREFIX = "## template: jinja"


class JinjaTemplatePartHandler(handlers.Handler):

    def __init__(self, paths, **_kwargs):
        handlers.Handler.__init__(self, PER_ALWAYS, version=3)
        self.paths = paths
        self._kwargs = _kwargs
        self.sub_handlers = {}

    def list_types(self):
        return [
            handlers.type_from_starts_with(JINJA_PREFIX),
        ]

    def handle_part(self, data, ctype, filename, payload, frequency, headers):
        if ctype == handlers.CONTENT_START:
            return
        if ctype == handlers.CONTENT_END:
            for sub_handler in self.sub_handlers.values():
                if sub_handler.handler_version == 2:
                    sub_handler.handle_part(
                        data, ctype, None, None, PER_INSTANCE)
                elif sub_handler.handler_version == 3:
                    sub_handler.handle_part(
                        data, ctype, None, None, PER_INSTANCE, {})
            return
        instance_data = {}
        json_file_path = os.path.join(self.paths.run_dir, INSTANCE_JSON_FILE)
        if os.path.exists(json_file_path):
            instance_data = load_json(load_file(json_file_path))
        else:
           LOG.warning(
               'Instance data not yet present at {0}'.format(json_file_path))
        instance_jinja_vars = convert_jinja_instance_data(instance_data)
        rendered_payload = render_string(payload, instance_jinja_vars)
        rendered_payload = rendered_payload.replace(JINJA_PREFIX + '\n', '')
        subtype = handlers.type_from_starts_with(rendered_payload)
        handler = self.sub_handlers.get(subtype)
        # Pass our rendered payload onto cloud-config of shellscript handlers
        if subtype == 'text/cloud-config':
            if not handler:
                self.sub_handlers[subtype] = CloudConfigPartHandler(
                    self.paths, **self._kwargs)
                handler = self.sub_handlers[subtype]
                handler.handle_part(
                    data, handlers.CONTENT_START, None, None, PER_INSTANCE, {})
            handler.handle_part(
                data, ctype, filename, rendered_payload, frequency, headers)
        elif subtype == 'text/x-shellscript':
            if not handler:
                self.sub_handlers[subtype] = ShellScriptPartHandler(
                    self.paths, **self._kwargs)
                handler = self.sub_handlers[subtype]
                handler.handle_part(data, handlers.CONTENT_START, None, None, PER_INSTANCE)
            handler.handle_part(
                data, ctype, filename, rendered_payload, frequency)
        else:
            raise RuntimeError(
                'After processing jinja template, could not find supported'
                ' sub-handler for type {0}'.format(
                    subtype))


def convert_jinja_instance_data(d, prefix='', sep='/', decode_paths=()):
    """Process instance-data.json dict for use in jinja templates.

    Replace hyphens with underscores for jinja templates and decode any
    base64-encoded-keys.
    """
    result = {}
    for key, value in d.items():
        key_path = '{0}{1}{2}'.format(prefix, sep, key) if prefix else key
        if key_path in decode_paths:
            value = b64d(value)
        key = key.replace('-', '_')
        if isinstance(value, dict):
            result[key] = convert_jinja_instance_data(
                value, key_path, sep=sep, decode_paths=decode_paths)
        else:
            result[key] = value
    return result


# vi: ts=4 expandtab
