from typing import Tuple, Any
from .handler import AbletonOSCHandler, resolve_device

class DeviceHandler(AbletonOSCHandler):
    def __init__(self, manager):
        super().__init__(manager)
        self.class_identifier = "device"

    def clear_api(self):
        #--------------------------------------------------------------------------------
        # Parameter value listeners use a custom add/remove mechanism, so detach
        # them here before the generic listener cleanup runs.
        #--------------------------------------------------------------------------------
        for listener_key in list(self.listener_functions.keys()):
            prop, params = listener_key
            if prop == 'device_parameter_value':
                listener_function = self.listener_functions.pop(listener_key)
                parameter = self.listener_objects.pop(listener_key, None)
                if parameter is not None:
                    try:
                        parameter.remove_value_listener(listener_function)
                    except Exception as e:
                        self.logger.info("Exception whilst removing listener (likely benign): %s" % e)
        super().clear_api()

    def init_api(self):
        def canonical_spec(spec):
            #--------------------------------------------------------------------------------
            # Echo numeric device specifiers back as ints (backwards-compatible),
            # and dotted device paths back verbatim as strings.
            #--------------------------------------------------------------------------------
            return spec if isinstance(spec, str) else int(spec)

        def create_device_callback(func, *args, include_ids: bool = False):
            def device_callback(params: Tuple[Any]):
                #--------------------------------------------------------------------------------
                # params[1] addresses the device: either a top-level device index,
                # or a dotted path descending into rack chains (e.g. "2.1.0").
                #--------------------------------------------------------------------------------
                track_index, device_spec = int(params[0]), params[1]
                device = resolve_device(self.song.tracks[track_index], device_spec)
                if (include_ids):
                    rv = func(device, *args, params[0:])
                else:
                    rv = func(device, *args, params[2:])

                if rv is not None:
                    return (track_index, canonical_spec(device_spec), *rv)

            return device_callback

        methods = [
            #--------------------------------------------------------------------------------
            # Macro variations (rack devices only).
            #--------------------------------------------------------------------------------
            "recall_selected_variation",
            "recall_last_used_variation",
            "store_variation"
        ]
        properties_r = [
            "class_name",
            "name",
            "type",
            "can_have_chains",
            "can_have_drum_pads",
            "variation_count"
        ]
        properties_rw = [
            "selected_variation_index"
        ]

        for method in methods:
            self.osc_server.add_handler("/live/device/%s" % method,
                                        create_device_callback(self._call_method, method))

        for prop in properties_r + properties_rw:
            self.osc_server.add_handler("/live/device/get/%s" % prop,
                                        create_device_callback(self._get_property, prop))
            self.osc_server.add_handler("/live/device/start_listen/%s" % prop,
                                        create_device_callback(self._start_listen, prop))
            self.osc_server.add_handler("/live/device/stop_listen/%s" % prop,
                                        create_device_callback(self._stop_listen, prop))
        for prop in properties_rw:
            self.osc_server.add_handler("/live/device/set/%s" % prop,
                                        create_device_callback(self._set_property, prop))

        #--------------------------------------------------------------------------------
        # Device: View properties.
        # is_collapsed lives on device.view; it reflects (and sets) the device's
        # folded state in Live's device chain, and is observable.
        #--------------------------------------------------------------------------------
        def device_get_is_collapsed(device, params: Tuple[Any] = ()):
            return int(device.view.is_collapsed),

        def device_set_is_collapsed(device, params: Tuple[Any] = ()):
            device.view.is_collapsed = bool(params[0])

        def device_start_listen_is_collapsed(device, params: Tuple[Any] = ()):
            self._start_listen(device.view, "is_collapsed", params)

        def device_stop_listen_is_collapsed(device, params: Tuple[Any] = ()):
            self._stop_listen(device.view, "is_collapsed", params)

        self.osc_server.add_handler("/live/device/get/is_collapsed", create_device_callback(device_get_is_collapsed))
        self.osc_server.add_handler("/live/device/set/is_collapsed", create_device_callback(device_set_is_collapsed))
        self.osc_server.add_handler("/live/device/start_listen/is_collapsed", create_device_callback(device_start_listen_is_collapsed, include_ids=True))
        self.osc_server.add_handler("/live/device/stop_listen/is_collapsed", create_device_callback(device_stop_listen_is_collapsed, include_ids=True))

        #--------------------------------------------------------------------------------
        # Device: Visible macro count (rack devices only; racks show 1-16 macros).
        #--------------------------------------------------------------------------------
        def device_get_visible_macro_count(device, params: Tuple[Any] = ()):
            return (device.visible_macro_count if device.can_have_chains else 0),

        def device_start_listen_visible_macro_count(device, params: Tuple[Any] = ()):
            self._start_listen(device, "visible_macro_count", params)

        def device_stop_listen_visible_macro_count(device, params: Tuple[Any] = ()):
            self._stop_listen(device, "visible_macro_count", params)

        self.osc_server.add_handler("/live/device/get/visible_macro_count", create_device_callback(device_get_visible_macro_count))
        self.osc_server.add_handler("/live/device/start_listen/visible_macro_count", create_device_callback(device_start_listen_visible_macro_count, include_ids=True))
        self.osc_server.add_handler("/live/device/stop_listen/visible_macro_count", create_device_callback(device_stop_listen_visible_macro_count, include_ids=True))

        #--------------------------------------------------------------------------------
        # Device: Enumerate rack chains
        #--------------------------------------------------------------------------------
        def device_get_num_chains(device, params: Tuple[Any] = ()):
            return (len(device.chains) if device.can_have_chains else 0),

        def device_get_chains_name(device, params: Tuple[Any] = ()):
            return tuple(chain.name for chain in device.chains)

        def device_get_chains_color(device, params: Tuple[Any] = ()):
            return tuple(chain.color for chain in device.chains)

        def device_get_chains_color_index(device, params: Tuple[Any] = ()):
            return tuple(chain.color_index for chain in device.chains)

        def device_get_chains_num_devices(device, params: Tuple[Any] = ()):
            return tuple(len(chain.devices) for chain in device.chains)

        self.osc_server.add_handler("/live/device/get/num_chains", create_device_callback(device_get_num_chains))
        self.osc_server.add_handler("/live/device/get/chains/name", create_device_callback(device_get_chains_name))
        self.osc_server.add_handler("/live/device/get/chains/color", create_device_callback(device_get_chains_color))
        self.osc_server.add_handler("/live/device/get/chains/color_index", create_device_callback(device_get_chains_color_index))
        self.osc_server.add_handler("/live/device/get/chains/num_devices", create_device_callback(device_get_chains_num_devices))

        #--------------------------------------------------------------------------------
        # Device: Get/set parameter lists
        #--------------------------------------------------------------------------------
        def device_get_num_parameters(device, params: Tuple[Any] = ()):
            return len(device.parameters),

        def device_get_parameters_name(device, params: Tuple[Any] = ()):
            return tuple(parameter.name for parameter in device.parameters)

        def device_get_parameters_value(device, params: Tuple[Any] = ()):
            return tuple(parameter.value for parameter in device.parameters)

        def device_get_parameters_min(device, params: Tuple[Any] = ()):
            return tuple(parameter.min for parameter in device.parameters)

        def device_get_parameters_max(device, params: Tuple[Any] = ()):
            return tuple(parameter.max for parameter in device.parameters)

        def device_get_parameters_is_quantized(device, params: Tuple[Any] = ()):
            return tuple(parameter.is_quantized for parameter in device.parameters)

        def device_set_parameters_value(device, params: Tuple[Any] = ()):
            for index, value in enumerate(params):
                device.parameters[index].value = value

        self.osc_server.add_handler("/live/device/get/num_parameters", create_device_callback(device_get_num_parameters))
        self.osc_server.add_handler("/live/device/get/parameters/name", create_device_callback(device_get_parameters_name))
        self.osc_server.add_handler("/live/device/get/parameters/value", create_device_callback(device_get_parameters_value))
        self.osc_server.add_handler("/live/device/get/parameters/min", create_device_callback(device_get_parameters_min))
        self.osc_server.add_handler("/live/device/get/parameters/max", create_device_callback(device_get_parameters_max))
        self.osc_server.add_handler("/live/device/get/parameters/is_quantized", create_device_callback(device_get_parameters_is_quantized))
        self.osc_server.add_handler("/live/device/set/parameters/value", create_device_callback(device_set_parameters_value))

        #--------------------------------------------------------------------------------
        # Device: Get/set individual parameters
        #--------------------------------------------------------------------------------
        def device_get_parameter_value(device, params: Tuple[Any] = ()):
            # Cast to ints so that we can tolerate floats from interfaces such as TouchOSC
            # that send floats by default.
            # https://github.com/ideoforms/AbletonOSC/issues/33
            param_index = int(params[0])
            return param_index, device.parameters[param_index].value
        
        # Uses str_for_value method to return the UI-friendly version of a parameter value (ex: "2500 Hz")
        def device_get_parameter_value_string(device, params: Tuple[Any] = ()):
            param_index = int(params[0])
            return param_index, device.parameters[param_index].str_for_value(device.parameters[param_index].value)
        
        def device_get_parameter_value_listener(device, params: Tuple[Any] = ()):
            param_index = int(params[2])

            def property_changed_callback():
                parameter = device.parameters[param_index]
                value = parameter.value
                self.logger.info("Property %s changed of %s %s: %s" % ('value', 'device parameter', str(params), value))
                self.osc_server.send("/live/device/get/parameter/value", (*params, value,))

                value_string = parameter.str_for_value(parameter.value)
                self.logger.info("Property %s changed of %s %s: %s" % ('value_string', 'device parameter', str(params), value_string))
                self.osc_server.send("/live/device/get/parameter/value_string", (*params, value_string,))

            listener_key = ('device_parameter_value', tuple(params))
            if listener_key in self.listener_functions:
               device_get_parameter_remove_value_listener(device, params)

            self.logger.info("Adding listener for %s %s, property: %s" % ('device parameter', str(params), 'value'))
            device.parameters[param_index].add_value_listener(property_changed_callback)
            self.listener_functions[listener_key] = property_changed_callback
            self.listener_objects[listener_key] = device.parameters[param_index]

            property_changed_callback()

        def device_get_parameter_remove_value_listener(device, params: Tuple[Any] = ()):
            listener_key = ('device_parameter_value', tuple(params))
            if listener_key in self.listener_functions:
                self.logger.info("Removing listener for %s %s, property %s" % (self.class_identifier, str(params), 'value'))
                listener_function = self.listener_functions[listener_key]
                device.parameters[int(params[2])].remove_value_listener(listener_function)
                del self.listener_functions[listener_key]
                self.listener_objects.pop(listener_key, None)
            else:
                self.logger.warning("No listener function found for device parameter value (%s)" % (str(params),))

        def device_set_parameter_value(device, params: Tuple[Any] = ()):
            param_index, param_value = params[:2]
            param_index = int(param_index)
            device.parameters[param_index].value = param_value

        def device_get_parameter_name(device, params: Tuple[Any] = ()):
            param_index = int(params[0])
            return param_index, device.parameters[param_index].name

        self.osc_server.add_handler("/live/device/get/parameter/value", create_device_callback(device_get_parameter_value))
        self.osc_server.add_handler("/live/device/get/parameter/value_string", create_device_callback(device_get_parameter_value_string))
        self.osc_server.add_handler("/live/device/set/parameter/value", create_device_callback(device_set_parameter_value))
        self.osc_server.add_handler("/live/device/get/parameter/name", create_device_callback(device_get_parameter_name))
        self.osc_server.add_handler("/live/device/start_listen/parameter/value", create_device_callback(device_get_parameter_value_listener, include_ids = True))
        self.osc_server.add_handler("/live/device/stop_listen/parameter/value", create_device_callback(device_get_parameter_remove_value_listener, include_ids = True))
