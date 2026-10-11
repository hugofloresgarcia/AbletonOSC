from . import client, wait_one_tick
import pytest

#--------------------------------------------------------------------------------
# Test device and chain features, including dotted device paths that descend
# into rack chains ("2.1.0" = device 2 -> chain 1 -> device 0).
#
# These tests run against whatever set is currently open, so they discover
# a device/rack to test against, and skip when the set doesn't contain one.
#--------------------------------------------------------------------------------

def _find_first_device(client):
    num_tracks = client.query("/live/song/get/num_tracks")[0]
    for track_index in range(num_tracks):
        num_devices = client.query("/live/track/get/num_devices", (track_index,))[1]
        if num_devices > 0:
            return track_index
    return None

def _find_rack(client):
    """
    Returns (track_index, device_index) of the first rack device, or None.
    """
    num_tracks = client.query("/live/song/get/num_tracks")[0]
    for track_index in range(num_tracks):
        rv = client.query("/live/track/get/devices/can_have_chains", (track_index,))
        for device_index, can_have_chains in enumerate(rv[1:]):
            if can_have_chains:
                return track_index, device_index
    return None

def test_device_path_addressing_backcompat(client):
    """
    A device addressed by int index and by string path must be the same device.
    """
    track_index = _find_first_device(client)
    if track_index is None:
        pytest.skip("Requires a set containing at least one device")
    rv_int = client.query("/live/device/get/name", (track_index, 0))
    rv_str = client.query("/live/device/get/name", (track_index, "0"))
    assert rv_int[2] == rv_str[2]
    #--------------------------------------------------------------------------------
    # Int specs are echoed back as ints, path specs verbatim as strings.
    #--------------------------------------------------------------------------------
    assert rv_int[1] == 0
    assert rv_str[1] == "0"

def test_device_chains(client):
    rack = _find_rack(client)
    if rack is None:
        pytest.skip("Requires a set containing a rack device")
    track_index, device_index = rack
    num_chains = client.query("/live/device/get/num_chains", (track_index, device_index))[2]
    names = client.query("/live/device/get/chains/name", (track_index, device_index))[2:]
    colors = client.query("/live/device/get/chains/color", (track_index, device_index))[2:]
    assert len(names) == num_chains
    assert len(colors) == num_chains

def test_chain_properties(client):
    rack = _find_rack(client)
    if rack is None:
        pytest.skip("Requires a set containing a rack device")
    track_index, device_index = rack
    num_chains = client.query("/live/device/get/num_chains", (track_index, device_index))[2]
    if num_chains == 0:
        pytest.skip("Requires a rack device with at least one chain")
    chain_names = client.query("/live/device/get/chains/name", (track_index, device_index))[2:]
    rv = client.query("/live/chain/get/name", (track_index, device_index, 0))
    assert rv == (track_index, device_index, 0, chain_names[0])
    color = client.query("/live/chain/get/color", (track_index, device_index, 0))[3]
    assert isinstance(color, int)

def test_nested_device_path(client):
    """
    Devices inside a rack chain are addressable with a dotted path, and the
    names match the chain's own device listing.
    """
    rack = _find_rack(client)
    if rack is None:
        pytest.skip("Requires a set containing a rack device")
    track_index, device_index = rack
    num_chains = client.query("/live/device/get/num_chains", (track_index, device_index))[2]
    for chain_index in range(num_chains):
        num_devices = client.query("/live/chain/get/num_devices", (track_index, device_index, chain_index))[3]
        if num_devices > 0:
            chain_device_names = client.query("/live/chain/get/devices/name", (track_index, device_index, chain_index))[3:]
            path = "%d.%d.0" % (device_index, chain_index)
            rv = client.query("/live/device/get/name", (track_index, path))
            assert rv == (track_index, path, chain_device_names[0])
            #--------------------------------------------------------------------------------
            # Parameter endpoints work through paths too.
            #--------------------------------------------------------------------------------
            num_parameters = client.query("/live/device/get/num_parameters", (track_index, path))[2]
            assert num_parameters > 0
            return
    pytest.skip("Requires a rack device with at least one device in a chain")

def test_track_devices_listener(client):
    track_index = _find_first_device(client)
    if track_index is None:
        pytest.skip("Requires a set containing at least one device")
    client.send_message("/live/track/start_listen/devices", (track_index,))
    #--------------------------------------------------------------------------------
    # The current value is sent immediately on starting to listen.
    #--------------------------------------------------------------------------------
    rv = client.await_message("/live/track/get/devices/name")
    assert rv[0] == track_index
    client.send_message("/live/track/stop_listen/devices", (track_index,))

def test_view_selected_device_path(client):
    track_index = _find_first_device(client)
    if track_index is None:
        pytest.skip("Requires a set containing at least one device")
    client.send_message("/live/view/set/selected_device", (track_index, "0"))
    wait_one_tick()
    rv = client.query("/live/view/get/selected_device_path")
    assert rv == (track_index, "0")

def test_view_selected_device_path_listener(client):
    track_index = _find_first_device(client)
    if track_index is None:
        pytest.skip("Requires a set containing at least one device")
    client.send_message("/live/view/set/selected_device", (track_index, 0))
    wait_one_tick()
    client.send_message("/live/view/start_listen/selected_device_path")
    rv = client.await_message("/live/view/get/selected_device_path")
    assert rv == (track_index, "0")
    client.send_message("/live/view/stop_listen/selected_device_path")
