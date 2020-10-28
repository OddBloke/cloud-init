import io
import pickletools
import re

import pytest


class TestPickle:
    def _normalise_pkl_dis(self, pkl_dis):
        # The empty multipart MIME lines contain a number which changes each
        # time an instance is launched: replace it with a static string
        pkl_dis = re.sub(r"===============\d{19}==", "REMOVED", pkl_dis)
        pkl_dis = re.sub(r"\d+", "N", pkl_dis)
        return pkl_dis

    # Instance name is encoded in the dumped pickle, so hold it constant
    @pytest.mark.instance_name("pickle-check")
    def test_pickle(self, client):
        # Pull obj.pkl from the SUT
        pkl_content = client.read_from_file(
            "/var/lib/cloud/instance/obj.pkl", mode="rb"
        )

        # Generate a human-readable string version
        with io.StringIO() as s:
            pickletools.dis(pkl_content, out=s)
            actual_pkl_dis = s.getvalue()

        # Fetch the human-readable string version of the currently expected
        # pickle
        with open("tests/data/current_pickle.txt") as f:
            expected_pkl_dis = f.read()

        # Remove any non-deterministic discrepancies
        expected_pkl_dis = self._normalise_pkl_dis(expected_pkl_dis)
        actual_pkl_dis = self._normalise_pkl_dis(actual_pkl_dis)

        # Compare them
        assert expected_pkl_dis == actual_pkl_dis
