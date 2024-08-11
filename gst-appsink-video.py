#!/usr/bin/env python3

import time
from dataclasses import dataclass

import numpy as np

import gi

gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
gi.require_version('GstApp', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gst, GstVideo, GstApp, GLib

Gst.init(None)


@dataclass
class AppSrcSharedData:
    pipeline: Gst.Pipeline
    app_src: GstApp.AppSrc
    source_id: int
    main_loop: GLib.MainLoop
    frame_ctr: int
    color_val: int


def create_color_tile(hue_val):
    red = 1
    green = 1
    blue = 1
    if hue_val <= 120:
        red = 1 - (hue_val / 120)
        green = hue_val / 120
        blue = 0
    elif hue_val <= 240:
        red = 0
        green = 1 - ((hue_val-120) / 120)
        blue = ((hue_val-120) / 120)
    elif hue_val <= 360:
        red = ((hue_val-240) / 120)
        green = 0
        blue = 1 - ((hue_val-240) / 120)
    return np.full((100, 100, 3), (255 * np.asarray([red, green, blue])), dtype=np.uint8)


def _push_data(data: AppSrcSharedData):
    buffer = Gst.Buffer.new_wrapped(create_color_tile(data.color_val).tobytes())
    buffer.add_reference_timestamp_meta(data.app_src.get_caps(), data.app_src.get_current_running_time(), Gst.CLOCK_TIME_NONE)
    buffer.pts = data.app_src.get_current_running_time()
    buffer.dts = Gst.CLOCK_TIME_NONE
    buffer.duration = Gst.CLOCK_TIME_NONE
    buffer.offset = data.frame_ctr
    data.frame_ctr += 1

    ret = data.app_src.push_buffer(buffer)

    data.color_val += 1
    time.sleep(0.03)
    if data.color_val > 360:
        data.app_src.end_of_stream()
        data.pipeline.send_event(Gst.Event.new_eos())
        data.pipeline.set_state(Gst.State.NULL)
        data.main_loop.quit()
        return False

    if ret != Gst.FlowReturn.OK:
        return True
    else:
        return False


def _start_feed(appsrc, length, udata):
    udata.source_id = GLib.idle_add(_push_data, udata)

def _stop_feed(appsrc, udata):
    GLib.source_remove(udata.appsrc_data.source_id)
    udata.appsrc_data.source_id = 0

if __name__ == '__main__':
    pipe_str = "appsrc name=source ! videoconvert ! autovideosink"
    # pipe_str = ("appsrc name=source format=time is_live=True ! videoconvert ! openh264enc ! rtspclientsink location=rtsp://localhost:8554/test")
    # pipe_str = "appsrc name=source format=time is_live=True ! videoconvert ! jpegenc ! avimux ! filesink location=output.avi"
    pipeline = Gst.parse_launch(pipe_str)
    src = None
    for element in pipeline.children:
        if element.name == "source":
            src = element
    # configure appsrc
    src.set_stream_type(GstApp.AppStreamType.STREAM)
    src.set_live(True)
    src.set_do_timestamp(False)
    src.set_format(Gst.Format.TIME)

    # set caps
    

    video_info = GstVideo.VideoInfo()
    video_info.set_format(GstVideo.VideoFormat.RGB, 100, 100)
    video_caps = video_info.to_caps()
    video_caps.fixate()
    src.set_caps(video_caps)

    main_loop = GLib.MainLoop()
    appsrc_data = AppSrcSharedData(pipeline, src, 0, main_loop, 0, 0)

    # connect callbacks
    src.connect("need-data", _start_feed, appsrc_data)
    src.connect("enough-data", _stop_feed, appsrc_data)
    ret = pipeline.set_state(Gst.State.PLAYING)
    main_loop.run()

