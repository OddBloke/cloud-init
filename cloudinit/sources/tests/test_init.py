# This file is part of cloud-init. See LICENSE file for license information.

import os
import six
import stat

from cloudinit.helpers import Paths
from cloudinit.sources import (
    INSTANCE_JSON_FILE, DataSource)
from cloudinit.tests.helpers import CiTestCase, skipIf
from cloudinit.user_data import UserDataProcessor
from cloudinit import util


class DataSourceTestSubclassNet(DataSource):

    dsname = 'MyTestSubclass'

    def __init__(self, sys_cfg, distro, paths, custom_userdata=None):
        super(DataSourceTestSubclassNet, self).__init__(
            sys_cfg, distro, paths)
        self._custom_userdata = custom_userdata

    def _get_cloud_name(self):
        return 'SubclassCloudName'

    def _get_data(self):
        self.metadata = {'local-hostname': 'test-subclass-hostname'}
        if self._custom_userdata:
            self.userdata_raw = self._custom_userdata
        else:
            self.userdata_raw = 'userdata_raw'
        self.vendordata_raw = 'vendordata_raw'
        return True


class InvalidDataSourceTestSubclassNet(DataSource):
    pass


class TestDataSource(CiTestCase):
    maxDiff = None
    with_logs = True

    def setUp(self):
        super(TestDataSource, self).setUp()
        self.sys_cfg = {'datasource': {'_undef': {'key1': False}}}
        self.distro = 'distrotest'  # generally should be a Distro object
        self.paths = Paths({})
        self.datasource = DataSource(self.sys_cfg, self.distro, self.paths)

    def test_datasource_init(self):
        """DataSource initializes metadata attributes, ds_cfg and ud_proc."""
        self.assertEqual(self.paths, self.datasource.paths)
        self.assertEqual(self.sys_cfg, self.datasource.sys_cfg)
        self.assertEqual(self.distro, self.datasource.distro)
        self.assertIsNone(self.datasource.userdata)
        self.assertEqual({}, self.datasource.metadata)
        self.assertIsNone(self.datasource.userdata_raw)
        self.assertIsNone(self.datasource.vendordata)
        self.assertIsNone(self.datasource.vendordata_raw)
        self.assertEqual({'key1': False}, self.datasource.ds_cfg)
        self.assertIsInstance(self.datasource.ud_proc, UserDataProcessor)

    def test_datasource_init_gets_ds_cfg_using_dsname(self):
        """Init uses DataSource.dsname for sourcing ds_cfg."""
        sys_cfg = {'datasource': {'MyTestSubclass': {'key2': False}}}
        distro = 'distrotest'  # generally should be a Distro object
        paths = Paths({})
        datasource = DataSourceTestSubclassNet(sys_cfg, distro, paths)
        self.assertEqual({'key2': False}, datasource.ds_cfg)

    def test_str_is_classname(self):
        """The string representation of the datasource is the classname."""
        self.assertEqual('DataSource', str(self.datasource))
        self.assertEqual(
            'DataSourceTestSubclassNet',
            str(DataSourceTestSubclassNet('', '', self.paths)))

    def test__get_data_unimplemented(self):
        """Raise an error when _get_data is not implemented."""
        with self.assertRaises(NotImplementedError) as context_manager:
            self.datasource.get_data()
        self.assertIn(
            'Subclasses of DataSource must implement _get_data',
            str(context_manager.exception))
        datasource2 = InvalidDataSourceTestSubclassNet(
            self.sys_cfg, self.distro, self.paths)
        with self.assertRaises(NotImplementedError) as context_manager:
            datasource2.get_data()
        self.assertIn(
            'Subclasses of DataSource must implement _get_data',
            str(context_manager.exception))

    def test_get_data_calls_subclass__get_data(self):
        """Datasource.get_data uses the subclass' version of _get_data."""
        tmp = self.tmp_dir()
        datasource = DataSourceTestSubclassNet(
            self.sys_cfg, self.distro, Paths({'run_dir': tmp}))
        self.assertTrue(datasource.get_data())
        self.assertEqual(
            {'local-hostname': 'test-subclass-hostname'},
            datasource.metadata)
        self.assertEqual('userdata_raw', datasource.userdata_raw)
        self.assertEqual('vendordata_raw', datasource.vendordata_raw)

    def test_get_data_write_json_instance_data(self):
        """get_data writes INSTANCE_JSON_FILE to run_dir as readonly root."""
        tmp = self.tmp_dir()
        datasource = DataSourceTestSubclassNet(
            self.sys_cfg, self.distro, Paths({'run_dir': tmp}))
        datasource.get_data()
        json_file = self.tmp_path(INSTANCE_JSON_FILE, tmp)
        content = util.load_file(json_file)
        expected = {
            'availability-zone': None,
            'base64-encoded-keys': [],
            'cloud-name': 'subclasscloudname',
            'instance-id': 'iid-datasource',
            'public-hostname': 'test-subclass-hostname',
            'public-ipv4-address': None,
            'public-ipv6-address': None,
            'region': None,
            '_datasource': {
                'meta-data': {'local-hostname': 'test-subclass-hostname'},
                'user-data': 'userdata_raw',
                'vendor-data': 'vendordata_raw'}}
        self.assertEqual(expected, util.load_json(content))
        file_stat = os.stat(json_file)
        self.assertEqual(0o600, stat.S_IMODE(file_stat.st_mode))

    def test_get_data_handles_redacted_unserializable_content(self):
        """get_data warns unserializable content in INSTANCE_JSON_FILE."""
        tmp = self.tmp_dir()
        datasource = DataSourceTestSubclassNet(
            self.sys_cfg, self.distro, Paths({'run_dir': tmp}),
            custom_userdata={'key1': 'val1', 'key2': {'key2.1': self.paths}})
        self.assertTrue(datasource.get_data())
        json_file = self.tmp_path(INSTANCE_JSON_FILE, tmp)
        content = util.load_file(json_file)
        expected_userdata = {
            'key1': 'val1',
            'key2': {
                'key2.1': "Warning: redacted unserializable type <class"
                          " 'cloudinit.helpers.Paths'>"}}
        instance_json = util.load_json(content)
        self.assertEqual(
            expected_userdata, instance_json['_datasource']['user-data'])

    @skipIf(not six.PY3, "json serialization on <= py2.7 handles bytes")
    def test_get_data_base64encodes_unserializable_bytes(self):
        """On py3, get_data base64encodes any unserializable content."""
        tmp = self.tmp_dir()
        datasource = DataSourceTestSubclassNet(
            self.sys_cfg, self.distro, Paths({'run_dir': tmp}),
            custom_userdata={'key1': 'val1', 'key2': {'key2.1': b'\x123'}})
        self.assertTrue(datasource.get_data())
        json_file = self.tmp_path(INSTANCE_JSON_FILE, tmp)
        content = util.load_file(json_file)
        instance_json = util.load_json(content)
        self.assertEqual(
            ['_datasource/user-data/key2/key2.1'],
            instance_json['base64-encoded-keys'])
        self.assertEqual(
            {'key1': 'val1', 'key2': {'key2.1': 'EjM='}},
            instance_json['_datasource']['user-data'])

    @skipIf(not six.PY2, "json serialization on <= py2.7 handles bytes")
    def test_get_data_handles_bytes_values(self):
        """On py2 get_data handles bytes values without having to b64encode."""
        tmp = self.tmp_dir()
        datasource = DataSourceTestSubclassNet(
            self.sys_cfg, self.distro, Paths({'run_dir': tmp}),
            custom_userdata={'key1': 'val1', 'key2': {'key2.1': b'\x123'}})
        self.assertTrue(datasource.get_data())
        json_file = self.tmp_path(INSTANCE_JSON_FILE, tmp)
        content = util.load_file(json_file)
        instance_json = util.load_json(content)
        self.assertEqual([], instance_json['base64-encoded-keys'])
        self.assertEqual(
            {'key1': 'val1', 'key2': {'key2.1': '\x123'}},
            instance_json['_datasource']['user-data'])
