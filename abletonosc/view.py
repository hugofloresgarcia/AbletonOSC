from functools import partial
from typing import Optional, Tuple, Any
from ableton.v2.base import liveobj_valid
from .handler import AbletonOSCHandler, resolve_device, device_path_spec

class ViewHandler(AbletonOSCHandler):
    def __init__(self, manager):
        super().__init__(manager)
        self.class_identifier = "view"

    def clear_api(self):
        if getattr(self, "_stop_selected_device_path_listener", None):
            self._stop_selected_device_path_listener()
        super().clear_api()

    def init_api(self):
        def get_selected_scene(params: Optional[Tuple] = ()):
            return (list(self.song.scenes).index(self.song.view.selected_scene),)

        def get_selected_track(params: Optional[Tuple] = ()):
            return (list(self.song.tracks).index(self.song.view.selected_track),)

        def get_selected_clip(params: Optional[Tuple] = ()):
            return (get_selected_track()[0], get_selected_scene()[0])
        
        def get_selected_device(params: Optional[Tuple] = ()):
            return (get_selected_track()[0], list(self.song.view.selected_track.devices).index(self.song.view.selected_track.view.selected_device))

        def set_selected_scene(params: Optional[Tuple] = ()):
            self.song.view.selected_scene = self.song.scenes[params[0]]

        def set_selected_track(params: Optional[Tuple] = ()):
            self.song.view.selected_track = self.song.tracks[params[0]]

        def set_selected_clip(params: Optional[Tuple] = ()):
            set_selected_track((params[0],))
            set_selected_scene((params[1],))

        def set_selected_device(params: Optional[Tuple] = ()):
            #--------------------------------------------------------------------------------
            # params[1] can be a top-level device index, or a dotted device path
            # descending into rack chains (e.g. "2.1.0") -- see DeviceHandler.
            #--------------------------------------------------------------------------------
            device = resolve_device(self.song.tracks[int(params[0])], params[1])
            self.song.view.select_device(device)
            return params[0], params[1]

        def get_selected_device_path(params: Optional[Tuple] = ()):
            #--------------------------------------------------------------------------------
            # Like get/selected_device, but returns the device's dotted path, which
            # also works for devices nested inside rack chains. Returns an empty
            # string if no device is selected.
            #--------------------------------------------------------------------------------
            device = self.song.view.selected_track.view.selected_device
            if not liveobj_valid(device):
                try:
                    track_index = list(self.song.tracks).index(self.song.view.selected_track)
                except ValueError:
                    track_index = -1
                return (track_index, "")
            return device_path_spec(self.song, device)

        #--------------------------------------------------------------------------------
        # Listen for changes to the selected device, across track changes.
        #
        # Track.View's selected_device is observable, but the listener must be
        # re-attached to the newly-selected track's view whenever the selected
        # track changes (the same pattern Live's own DeviceProvider uses).
        # Replies are sent to /live/view/get/selected_device_path.
        #--------------------------------------------------------------------------------
        self._selected_device_path_state = None

        def send_selected_device_path():
            self.osc_server.send("/live/view/get/selected_device_path", get_selected_device_path())

        def stop_listen_selected_device_path(params: Optional[Tuple] = ()):
            state = self._selected_device_path_state
            if state is None:
                return
            try:
                self.song.view.remove_selected_track_listener(state["on_track_changed"])
            except Exception as e:
                self.logger.info("Exception whilst removing listener (likely benign): %s" % e)
            if state["track_view"] is not None:
                try:
                    state["track_view"].remove_selected_device_listener(state["on_device_changed"])
                except Exception as e:
                    self.logger.info("Exception whilst removing listener (likely benign): %s" % e)
            self._selected_device_path_state = None

        def start_listen_selected_device_path(params: Optional[Tuple] = ()):
            stop_listen_selected_device_path()
            state = {
                "track_view": None,
                "on_device_changed": send_selected_device_path
            }

            def rehook_track_view():
                if state["track_view"] is not None:
                    try:
                        state["track_view"].remove_selected_device_listener(send_selected_device_path)
                    except Exception as e:
                        self.logger.info("Exception whilst removing listener (likely benign): %s" % e)
                track_view = self.song.view.selected_track.view
                track_view.add_selected_device_listener(send_selected_device_path)
                state["track_view"] = track_view

            def on_track_changed():
                rehook_track_view()
                send_selected_device_path()

            state["on_track_changed"] = on_track_changed
            self.song.view.add_selected_track_listener(on_track_changed)
            rehook_track_view()
            self._selected_device_path_state = state
            #--------------------------------------------------------------------------------
            # Immediately send the current value
            #--------------------------------------------------------------------------------
            send_selected_device_path()

        self._stop_selected_device_path_listener = stop_listen_selected_device_path

        self.osc_server.add_handler("/live/view/get/selected_scene", get_selected_scene)
        self.osc_server.add_handler("/live/view/get/selected_track", get_selected_track)
        self.osc_server.add_handler("/live/view/get/selected_clip", get_selected_clip)
        self.osc_server.add_handler("/live/view/get/selected_device", get_selected_device)
        self.osc_server.add_handler("/live/view/get/selected_device_path", get_selected_device_path)
        self.osc_server.add_handler("/live/view/start_listen/selected_device_path", start_listen_selected_device_path)
        self.osc_server.add_handler("/live/view/stop_listen/selected_device_path", stop_listen_selected_device_path)
        self.osc_server.add_handler("/live/view/set/selected_scene", set_selected_scene)
        self.osc_server.add_handler("/live/view/set/selected_track", set_selected_track)
        self.osc_server.add_handler("/live/view/set/selected_clip", set_selected_clip)
        self.osc_server.add_handler("/live/view/set/selected_device", set_selected_device)
        
        self.osc_server.add_handler('/live/view/start_listen/selected_scene', partial(self._start_listen, self.song.view, "selected_scene", getter=get_selected_scene))
        self.osc_server.add_handler('/live/view/start_listen/selected_track', partial(self._start_listen, self.song.view, "selected_track", getter=get_selected_track))
        self.osc_server.add_handler('/live/view/stop_listen/selected_scene', partial(self._stop_listen, self.song.view, "selected_scene"))
        self.osc_server.add_handler('/live/view/stop_listen/selected_track', partial(self._stop_listen, self.song.view, "selected_track"))
