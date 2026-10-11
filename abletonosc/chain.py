from typing import Tuple, Any
from .handler import AbletonOSCHandler, resolve_device

class ChainHandler(AbletonOSCHandler):
    """
    Handler for chains of rack devices (Instrument/Audio Effect/MIDI Effect/Drum Racks).

    Chains are addressed by (track_index, device_spec, chain_index), where
    device_spec addresses the rack device: either a top-level device index,
    or a dotted device path descending into nested racks (e.g. "2.1.0" --
    see DeviceHandler).
    """
    def __init__(self, manager):
        super().__init__(manager)
        self.class_identifier = "chain"

    def init_api(self):
        def create_chain_callback(func, *args):
            def chain_callback(params: Tuple[Any]):
                track_index = int(params[0])
                rack = resolve_device(self.song.tracks[track_index], params[1])
                chain_index = int(params[2])
                chain = rack.chains[chain_index]
                rv = func(chain, *args, params[3:])

                if rv is not None:
                    device_spec = params[1] if isinstance(params[1], str) else int(params[1])
                    return (track_index, device_spec, chain_index, *rv)

            return chain_callback

        methods = [
        ]
        properties_r = [
            "has_audio_input",
            "has_audio_output",
            "has_midi_input",
            "has_midi_output",
            "muted_via_solo"
        ]
        properties_rw = [
            "color",
            "color_index",
            "mute",
            "name",
            "solo"
        ]

        for method in methods:
            self.osc_server.add_handler("/live/chain/%s" % method,
                                        create_chain_callback(self._call_method, method))

        for prop in properties_r + properties_rw:
            self.osc_server.add_handler("/live/chain/get/%s" % prop,
                                        create_chain_callback(self._get_property, prop))
            self.osc_server.add_handler("/live/chain/start_listen/%s" % prop,
                                        create_chain_callback(self._start_listen, prop))
            self.osc_server.add_handler("/live/chain/stop_listen/%s" % prop,
                                        create_chain_callback(self._stop_listen, prop))
        for prop in properties_rw:
            self.osc_server.add_handler("/live/chain/set/%s" % prop,
                                        create_chain_callback(self._set_property, prop))

        #--------------------------------------------------------------------------------
        # Chain: Enumerate devices.
        # Devices within a chain are addressed through the device path mechanism
        # of /live/device endpoints (e.g. device path "2.1.0").
        #--------------------------------------------------------------------------------
        def chain_get_num_devices(chain, params: Tuple[Any] = ()):
            return len(chain.devices),

        def chain_get_device_names(chain, params: Tuple[Any] = ()):
            return tuple(device.name for device in chain.devices)

        def chain_get_device_types(chain, params: Tuple[Any] = ()):
            return tuple(device.type for device in chain.devices)

        def chain_get_device_class_names(chain, params: Tuple[Any] = ()):
            return tuple(device.class_name for device in chain.devices)

        def chain_get_device_can_have_chains(chain, params: Tuple[Any] = ()):
            return tuple(device.can_have_chains for device in chain.devices)

        self.osc_server.add_handler("/live/chain/get/num_devices", create_chain_callback(chain_get_num_devices))
        self.osc_server.add_handler("/live/chain/get/devices/name", create_chain_callback(chain_get_device_names))
        self.osc_server.add_handler("/live/chain/get/devices/type", create_chain_callback(chain_get_device_types))
        self.osc_server.add_handler("/live/chain/get/devices/class_name", create_chain_callback(chain_get_device_class_names))
        self.osc_server.add_handler("/live/chain/get/devices/can_have_chains", create_chain_callback(chain_get_device_can_have_chains))
