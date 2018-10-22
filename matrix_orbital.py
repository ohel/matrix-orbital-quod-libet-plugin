# -*- coding: utf-8 -*-
# Copyright 2018 Olli Helin
#
# Matrix Orbital LCD display plugin for Quod Libet media player.
# Prints information about currently playing song.
# Supports models from MX2/MX3 series (LK202); probably many others, too.
#
# Prerequisites: Linux, Python 3, Unidecode Python module.
# The LCD serial device must be writable and set up correctly.
# Installation: place this file into ~/.quodlibet/plugins/events
#
# To set up the LCD device:
# 1. load the usbserial and ftdi-sio kernel modules
# 2. set up the TTY with correct speed, e.g.
#    /bin/stty -F /dev/serial/matrix_orbital speed 19200 -onlcr
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

from enum import Enum
from gi.repository import Gtk
from math import floor
from platform import system
from quodlibet import _, app
from quodlibet.plugins import ConfProp, PluginConfig
from quodlibet.plugins.events import EventPlugin
from quodlibet.qltk import Icons
from quodlibet.qltk.tracker import TimeTracker
from quodlibet.util import print_e
from unidecode import unidecode


class Config(object):

    _config = PluginConfig(__name__)
    lcd_dev = ConfProp(_config, "lcd_dev", "/dev/serial/matrix_orbital")
    lcd_width = ConfProp(_config, "lcd_width", 20)
    lcd_interval = ConfProp(_config, "lcd_interval", 150)

CONFIG = Config()


class Alignment(Enum):

    LEFT = 1
    RIGHT = 2
    CENTER = 3
    TOP = 4
    BOTTOM = 5


class Phase(Enum):

    BASIC_INFO = 1
    BASIC_SCROLL = 2
    BASIC_INFO_2 = 3
    BASIC_SCROLL_2 = 4
    DISC_INFO = 5
    HEADER_INFO = 6


class NowPlayingLCDData(object):

    def __init__(self, parent):

        self._parent = parent
        self._max_width = int(CONFIG.lcd_width)
        self._interval = float(CONFIG.lcd_interval)
        self._ticks_in_phase = self._seconds_to_ticks(4)
        self.reset()

    def set_basic_info(self, artist, title):

        self._artist = unidecode(artist)
        self._title = unidecode(title)

        # If the text should scroll, pad it to scroll width.
        if len(self._artist) > self._max_width:
            self._artist += "".ljust(self._max_width)
        if len(self._title) > self._max_width:
            self._title += "".ljust(self._max_width)

    def set_disc_info(self, album, discnumber, tracknumber):

        self._disc_info_row_1 = ""
        self._disc_info_row_2 = ""

        if album is not None:
            tlalbum = unidecode(album)
            if len(tlalbum) > self._max_width:
                tlalbum = tlalbum[0:self._max_width - 3] + "..."
            self._disc_info_row_1 = tlalbum

        if discnumber is not None:
            self._disc_info_row_2 = \
                _("Disc") + " " + unidecode(discnumber) + " "

        if tracknumber is not None:
            self._disc_info_row_2 += \
                (_("Track") + " " + unidecode(tracknumber)) \
                .rjust(self._max_width - len(self._disc_info_row_2))

    def reset(self):

        self._artist = None
        self._title = None
        self._disc_info_row_1 = ""
        self._disc_info_row_2 = ""
        self._skip_ticks = 0
        self._scroll_a = 0
        self._scroll_t = 0
        self._tick_count = 0
        self._phase = Phase.BASIC_INFO
        self._force_refresh = True

    def prevent_update(self, seconds):

        if seconds < 0:
            self._skip_ticks = -1
        else:
            self._skip_ticks = self._seconds_to_ticks(seconds)

    def set_forced_update(self):

        self._force_refresh = True

    def _seconds_to_ticks(self, seconds):

        return int(round(seconds * (1000 / self._interval)))

    def _advance_phase(self):

        self._scroll_a = 0
        self._scroll_t = 0
        self._tick_count = 0

        # Don't scroll if there is no need to.
        if (len(self._artist) <= self._max_width):
            self._scroll_a = -1
        if (len(self._title) <= self._max_width):
            self._scroll_t = -1

        next_phases = {
            Phase.BASIC_INFO: Phase.BASIC_SCROLL,
            Phase.BASIC_SCROLL: Phase.BASIC_INFO_2,
            Phase.BASIC_INFO_2: Phase.BASIC_SCROLL_2,
            Phase.BASIC_SCROLL_2: Phase.DISC_INFO,
            Phase.DISC_INFO: Phase.HEADER_INFO,
            Phase.HEADER_INFO: Phase.BASIC_INFO
            }
        self._phase = next_phases.get(self._phase, Phase.HEADER_INFO)

        self._force_refresh = True

    def on_tracker_tick(self, tracker):

        if (self._artist is None or
            self._title is None or
            self._skip_ticks < 0):
            return

        if self._skip_ticks > 0:
            self._skip_ticks -= 1
            # If resuming after skipped ticks, force refresh.
            # This makes sure there is no garbage on the display.
            if self._skip_ticks == 0:
                self._force_refresh = True
            return

        self._tick_count += 1

        # Display static basic info.
        if (self._phase == Phase.BASIC_INFO or
            self._phase == Phase.BASIC_INFO_2):

            if (self._force_refresh):
                self._force_refresh = False
                self._parent.reset_lcd()
                self._refresh_info()

            if (self._tick_count > self._ticks_in_phase):
                self._advance_phase()

            return

        # Display scrolling basic info.
        if (self._phase == Phase.BASIC_SCROLL or
            self._phase == Phase.BASIC_SCROLL_2):

            # Value -1 indicates scrolling is done.
            refresh_artist = self._scroll_a > -1 or self._force_refresh
            refresh_title = self._scroll_t > -1 or self._force_refresh

            if (self._tick_count > self._ticks_in_phase and
                self._scroll_a == -1 and self._scroll_t == -1):
                self._advance_phase()
                return

            if self._force_refresh:
                self._force_refresh = False
                self._parent.reset_lcd()

            if self._scroll_a > -1:
                self._scroll_a += 1
                if self._scroll_a > len(self._artist):
                    self._scroll_a = -1

            if self._scroll_t > -1:
                self._scroll_t += 1
                if self._scroll_t > len(self._title):
                    self._scroll_t = -1

            if refresh_artist:
                self._refresh_info(True, False)
            if refresh_title:
                self._refresh_info(False)

            return

        # Display disc info.
        if self._phase == Phase.DISC_INFO:

            if self._force_refresh:
                self._force_refresh = False
                self._parent.reset_lcd()
                self._refresh_disc_info()

            if self._tick_count > self._ticks_in_phase:
                self._advance_phase()

            return

        # Display generic status.
        if self._phase == Phase.HEADER_INFO:

            if self._force_refresh:
                self._force_refresh = False
                self._parent.reset_lcd()
                self._parent.write_header_with_text(_("* now playing *"))

            if self._tick_count > self._ticks_in_phase / 2:
                self._advance_phase()

            return

    def _write_text(self, text, scroll, v_align):

        if scroll is not None and scroll > 0:
            text = (text[scroll:] + text)
        text = text[0:self._max_width]
        self._parent.write_bytes(
            self._parent.align_text2bytes(text, Alignment.LEFT, v_align))

    def _refresh_disc_info(self):

        self._write_text(self._disc_info_row_1, None, Alignment.TOP)
        self._write_text(self._disc_info_row_2, None, Alignment.BOTTOM)

    def _refresh_info(self, artist=True, title=True):

        if artist:
            self._write_text(self._artist, self._scroll_a, Alignment.TOP)

        if title:
            self._write_text(self._title, self._scroll_t, Alignment.BOTTOM)


class MatrixOrbitalLCD(EventPlugin):

    PLUGIN_ID = "MatrixOrbitalLCD"
    PLUGIN_NAME = "Matrix Orbital LCD"
    PLUGIN_DESC = _("Print info to a Matrix Orbital MX2/MX3 LCD.")
    PLUGIN_ICON = Icons.UTILITIES_TERMINAL
    PLUGIN_VERSION = "1.0"

    def align_text2bytes(self, text,
        h_align=Alignment.CENTER, v_align=Alignment.TOP):

        if (h_align == Alignment.LEFT):
            index = 1
        elif (h_align == Alignment.RIGHT):
            index = max(CONFIG.lcd_width - len(text) + 1, 1)
        elif (h_align == Alignment.CENTER):
            index = floor((int(CONFIG.lcd_width) - len(text)) / 2) + 1

        alignment = b"\xFEG" + bytes(chr(index), "utf8")

        if v_align == Alignment.TOP:
            alignment += b"\x01"
        elif v_align == Alignment.BOTTOM:
            alignment += b"\x02"

        return alignment + bytes(text, "utf8")

    def reset_lcd(self):

        # Empty LCD screen (X) and send cursor home (H).
        self.write_bytes(b"\xFEX\xFEH")

    def write_bytes(self, text):

        self._dev.write(text)

    def write_header_with_text(self, text=""):

        self.reset_lcd()
        self._write_header()
        self.write_bytes(
            self.align_text2bytes(text, Alignment.CENTER, Alignment.BOTTOM))

    def _write_header(self, header="Quod Libet"):

        self.write_bytes(self.align_text2bytes(header))

    def PluginPreferences(self, parent):

        def _path_changed(entry):
            CONFIG.lcd_dev = entry.get_text()

        def _width_changed(entry):
            try:
                CONFIG.lcd_width = int(entry.get_text())
            except:
                CONFIG.lcd_width = 20

        def _interval_changed(entry):
            try:
                CONFIG.lcd_interval = int(entry.get_text())
            except:
                CONFIG.lcd_interval = 150

        label = Gtk.Label(label=_("LCD serial device path:"))
        hbox = Gtk.HBox()
        hbox.pack_start(label, False, True, 6)

        entry = Gtk.Entry()
        entry.set_text(CONFIG.lcd_dev)
        entry.connect("changed", _path_changed)
        hbox.pack_start(entry, True, True, 6)

        vbox = Gtk.VBox()
        vbox.pack_start(hbox, False, True, 6)

        label = Gtk.Label(label=_("LCD device width (characters):"))
        hbox = Gtk.HBox()
        hbox.pack_start(label, False, True, 6)

        entry = Gtk.Entry()
        entry.set_text(CONFIG.lcd_width)
        entry.connect("changed", _width_changed)
        hbox.pack_start(entry, True, True, 6)

        vbox.pack_start(hbox, True, True, 0)

        label = Gtk.Label(label=_("LCD update interval (ms):"))
        hbox = Gtk.HBox()
        hbox.pack_start(label, False, True, 6)

        entry = Gtk.Entry()
        entry.set_text(CONFIG.lcd_interval)
        entry.connect("changed", _interval_changed)
        hbox.pack_start(entry, True, True, 6)

        vbox.pack_start(hbox, True, True, 6)
        return vbox

    def _failed_initialization(self):

        if not hasattr(self, "_dev"):
            print_e("Matrix Orbital LCD plugin not initialized correctly.")
            return True
        return False

    def enabled(self):

        if system() != "Linux":
            print_e(self.PLUGIN_NAME + " plugin requires a Linux environment.")
            return

        try:
            self._dev = open(CONFIG.lcd_dev, 'wb', buffering=0)
        except:
            print_e("Matrix Orbital LCD device not found at " + CONFIG.lcd_dev)
            return

        self.reset_lcd()

        # Ready horizontal bars.
        self.write_bytes(b"\xFEh")
        # Turn backlight on.
        self.write_bytes(b"\xFEB\x00")

        self._write_header()

        self._npld = NowPlayingLCDData(self)
        self._tracker = TimeTracker(app.player)
        self._tracker.connect('tick', self._npld.on_tracker_tick)
        self._tracker.set_interval(int(CONFIG.lcd_interval))

    def disabled(self):

        if self._failed_initialization():
            return

        self._tracker.destroy()
        self.reset_lcd()

        # Turn backlight off.
        self.write_bytes(b"\xFEF")

    def plugin_on_seek(self, song, msec):

        if self._failed_initialization():
            return

        self.reset_lcd()
        self._npld.prevent_update(1)

        self._write_header(_("Seeking..."))
        percent_played = int(round(msec / float(song.get("~#length", 0)) / 10))

        # Draw a horizontal bar graph starting at column 1 on row 2
        # to the right (0), with a length of 0-100 pixels.
        self.write_bytes(b"\xFE\x7C\x01\x02\x00" +
            bytes(chr(percent_played), "utf8"))

    def plugin_on_song_started(self, song):

        if self._failed_initialization() or song is None:
            return

        self._npld.reset()
        self._npld.set_basic_info(song("artist"), song("title"))
        self._npld.set_disc_info(song("album"),
            song.get("discnumber"), song.get("tracknumber"))
        self.reset_lcd()

    def plugin_on_song_ended(self, song, stopped):

        if self._failed_initialization():
            return

        self._npld.reset()
        self.write_header_with_text(_("* not playing *"))

    def plugin_on_paused(self):

        if self._failed_initialization():
            return

        # No need to set pause for trackers manually.
        self.write_header_with_text(_("* paused *"))

    def plugin_on_unpaused(self):

        if self._failed_initialization():
            return

        self._npld.set_forced_update()
