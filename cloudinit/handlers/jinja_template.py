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

from cloudinit.settings import (PER_ALWAYS)

LOG = logging.getLogger(__name__)
JINJA_PREFIX = "## template: jinja"


class JinjaTemplatePartHandler(handlers.Handler):

    def __init__(self, paths, **_kwargs):
        handlers.Handler.__init__(self, PER_ALWAYS, version=3)
        self.paths = paths
        self._kwargs = _kwargs

    def list_types(self):
        return [
            handlers.type_from_starts_with(JINJA_PREFIX),
        ]

    def handle_part(self, data, ctype, filename, payload, frequency, headers):
        if ctype in handlers.CONTENT_SIGNALS:
            return
        instance_data = {}
        if os.path.exists(INSTANCE_JSON_FILE):
            instance_data = load_json(load_file(INSTANCE_JSON_FILE))
        instance_jinja_vars = InstanceDataJinjaDict(instance_data)
        rendered_payload = render_string(payload, instance_jinja_vars)
        rendered_payload = rendered_payload.replace(JINJA_PREFIX + '\n', '')
        include_type = handlers.type_from_starts_with(rendered_payload)
        # Pass our rendered payload onto cloud-config of shellscript handlers
        if include_type == 'text/cloud-config':
            handler = CloudConfigPartHandler(self.paths, **self._kwargs)
            handler.handle_part(data, ctype, filename, rendered_payload,
                                frequency, headers)
        elif include_type == 'text/x-shellscript':
            handler = ShellScriptPartHandler(self.paths, **self._kwargs)
            handler.handle_part(data, ctype, filename, rendered_payload,
                                frequency)
        else:
            raise RuntimeError(
                'After processing jinja template, could not find supported'
                ' sub-handler for type {0}'.format(
                    include_type))


def flatten_jinja_dict(d, prefix='', sep='.', replacements=()):
    """Flatten dict, replacing hyphens with underscores for jinja templates."""
    items = []
    for key, value in d.items():
        key = key.replace('-', '_')
        new_key = '{0}{1}{2}'.format(prefix, sep, key) if prefix else key
        try:
            items.extend(flatten_jinja_dict(value, new_key, sep=sep).items())
        except AttributeError:
            items.append((new_key, value))
    return dict(items)


class InstanceDataJinjaDict(dict):
    '''Wrapper around instance-data.json to return jinja compatible content.

    This class wraps the dict getitem to automatically convert hyphenated
    key names to underscores and automatically decode b64 encoded data.
    '''

    flat_dict = None

    def __init__(self, *args, **kwargs):
        super(InstanceDataJinjaDict, self).__init__(*args, **kwargs)
        orig_dict = args[0]
        self.flat_dict = flatten_jinja_dict(orig_dict)

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, dict.__repr__(self))

    def keys(self):
        return self.flat_dict.keys()

    def __getitem__(self, key_path):
        value = self.flat_dict.get(key_path)
        if key_path in self.flat_dict['b64_keys']:
            value = b64d(value)
        return value


# vi: ts=4 expandtab
