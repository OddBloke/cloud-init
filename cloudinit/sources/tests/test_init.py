# This file is part of cloud-init. See LICENSE file for license information.

import json
import os
import stat

from cloudinit.helpers import Paths
from cloudinit.sources import INSTANCE_JSON_FILE, DataSource
from cloudinit.tests.helpers import CiTestCase
from cloudinit.user_data import UserDataProcessor
from cloudinit import util


class DataSourceTestSubclassNet(DataSource):

    def __init__(self, sys_cfg, distro, paths, custom_userdata=None):
        super(DataSourceTestSubclassNet, self).__init__(
            sys_cfg, distro, paths)
        self._custom_userdata = custom_userdata

    def _get_data(self):
        self.metadata = {'DataSourceTestSubclassNet': 'was here'}
        if self._custom_userdata:
            self.userdata_raw = self._custom_userdata
        else:
            self.userdata_raw = 'userdata_raw'
        self.vendordata_raw = 'vendordata_raw'
        return True


class InvalidDataSourceTestSubclassNet(DataSource):
    pass


class TestDataSource(CiTestCase):

    with_logs = True

    def setUp(self):
        super(TestDataSource, self).setUp()
        self.sys_cfg = {'datasource': {'': {'key1': False}}}
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

    def test_datasource_init_strips_classname_for_ds_cfg(self):
        """Init strips DataSource prefix and Net suffix for ds_cfg."""
        sys_cfg = {'datasource': {'TestSubclass': {'key2': False}}}
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
            {'DataSourceTestSubclassNet': 'was here'},
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
            'meta-data': {'DataSourceTestSubclassNet': 'was here'},
            'user-data': 'userdata_raw',
            'vendor-data': 'vendordata_raw'}
        self.assertEqual(expected, json.loads(content))
        file_stat = os.stat(json_file)
        self.assertEqual(0o600, stat.S_IMODE(file_stat.st_mode))

    def test_get_data_log_warning_on_non_json_instance_data(self):
        """get_data succeeds but warns on non-json serialization content."""
        tmp = self.tmp_dir()
        datasource = DataSourceTestSubclassNet(
            self.sys_cfg, self.distro, Paths({'run_dir': tmp}),
            custom_userdata=self.paths)
        self.assertTrue(datasource.get_data())
        json_file = self.tmp_path(INSTANCE_JSON_FILE, tmp)
        self.assertFalse(os.path.exists(json_file))
        self.assertIn(
            'WARNING: Error persisting instance-data.json',
            self.logs.getvalue())
