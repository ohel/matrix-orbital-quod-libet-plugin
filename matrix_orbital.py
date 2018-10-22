# Matrix Orbital LCD display plugin for Quod Libet media player.
# Prints information about currently playing song.
# Supports models from MX2/MX3 series (LK202); probably many others, too.
#
# Installation: place this file into ~/.quodlibet/plugins/events
# Prerequisites: Python 3, Unidecode module, Quod Libet
# The LCD serial device must be writable and set up correctly.
#
# To set up the LCD device:
# 1. load the usbserial and ftdi-sio kernel modules
# 2. set up the TTY with correct speed, e.g.
#    /bin/stty -F /dev/serial/matrix_orbital speed 19200 -onlcr
#
# Copyright 2018 Olli Helin
#
# This software is released under the terms of the
# GNU General Public License v3: http://www.gnu.org/licenses/gpl-3.0.en.html

from enum import Enum
from gi.repository import Gtk
from math import floor
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


class MatrixOrbitalLCD(EventPlugin):

    PLUGIN_ID = 'MatrixOrbitalLCD'
    PLUGIN_NAME = _('Matrix Orbital LCD')
    PLUGIN_DESC = _("Print info to a Matrix Orbital MX2/MX3 LCD.")
    PLUGIN_ICON = Icons.UTILITIES_TERMINAL
    PLUGIN_VERSION = '0.1'

    class _Alignment(Enum):

        LEFT = 1
        RIGHT = 2
        CENTER = 3
        TOP = 4
        BOTTOM = 5

    class _NowPlayingLCDData(object):

        class _Phase(Enum):

            BASIC_INFO = 1
            BASIC_SCROLL = 2
            BASIC_INFO_2 = 3
            BASIC_SCROLL_2 = 4
            DISC_INFO = 5
            HEADER_INFO = 6

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
                    ("Disc " + unidecode(discnumber) + " ").ljust(9)

            if tracknumber is not None:
                self._disc_info_row_2 += ("Track " + unidecode(tracknumber)) \
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
            self._phase = self._Phase.BASIC_INFO
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
                self._Phase.BASIC_INFO: self._Phase.BASIC_SCROLL,
                self._Phase.BASIC_SCROLL: self._Phase.BASIC_INFO_2,
                self._Phase.BASIC_INFO_2: self._Phase.BASIC_SCROLL_2,
                self._Phase.BASIC_SCROLL_2: self._Phase.DISC_INFO,
                self._Phase.DISC_INFO: self._Phase.HEADER_INFO,
                self._Phase.HEADER_INFO: self._Phase.BASIC_INFO
                }
            self._phase = next_phases.get(self._phase, self._Phase.HEADER_INFO)

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
            if (self._phase == self._Phase.BASIC_INFO or
                self._phase == self._Phase.BASIC_INFO_2):

                if (self._force_refresh):
                    self._force_refresh = False
                    self._parent._reset_lcd()
                    self._refresh()

                if (self._tick_count > self._ticks_in_phase):
                    self._advance_phase()

                return

            # Display scrolling basic info.
            if (self._phase == self._Phase.BASIC_SCROLL or
                self._phase == self._Phase.BASIC_SCROLL_2):

                # Value -1 indicates scrolling is done.
                refresh_artist = self._scroll_a > -1 or self._force_refresh
                refresh_title = self._scroll_t > -1 or self._force_refresh

                if (self._tick_count > self._ticks_in_phase and
                    self._scroll_a == -1 and self._scroll_t == -1):
                    self._advance_phase()
                    return

                if self._force_refresh:
                    self._force_refresh = False
                    self._parent._reset_lcd()

                if self._scroll_a > -1:
                    self._scroll_a += 1
                    if self._scroll_a > len(self._artist):
                        self._scroll_a = -1

                if self._scroll_t > -1:
                    self._scroll_t += 1
                    if self._scroll_t > len(self._title):
                        self._scroll_t = -1

                if refresh_artist:
                    self._refresh(True, False)
                if refresh_title:
                    self._refresh(False, True)

                return

            # Display disc info.
            if self._phase == self._Phase.DISC_INFO:

                if self._force_refresh:
                    self._force_refresh = False
                    self._parent._reset_lcd()
                    self._refresh(False, False, True)

                if self._tick_count > self._ticks_in_phase:
                    self._advance_phase()

                return

            # Display disc info.
            if self._phase == self._Phase.HEADER_INFO:

                if self._force_refresh:
                    self._force_refresh = False
                    self._parent._reset_lcd()
                    self._parent._write_header_with_text("* now playing *")

                if self._tick_count > self._ticks_in_phase / 2:
                    self._advance_phase()

                return

        def _write_text(self, text, scroll, v_align):

            if scroll is not None and scroll > 0:
                text = (text[scroll:] + text)
            text = text[0:self._max_width]
            self._parent._dev.write(self._parent._align_text(text,
                self._parent._Alignment.LEFT, v_align))

        def _refresh(self, artist=True, title=True, disc_info=False):

            if disc_info:
                self._write_text(
                    self._disc_info_row_1, None, self._parent._Alignment.TOP)
                self._write_text(self._disc_info_row_2,
                    None, self._parent._Alignment.BOTTOM)
                return

            if artist:
                self._write_text(
                    self._artist, self._scroll_a, self._parent._Alignment.TOP)

            if title:
                self._write_text(self._title, self._scroll_t,
                    self._parent._Alignment.BOTTOM)

    def _align_text(self, text,
        h_align=_Alignment.CENTER, v_align=_Alignment.TOP):

        if (h_align == self._Alignment.LEFT):
            index = 1
        elif (h_align == self._Alignment.RIGHT):
            index = max(CONFIG.lcd_width - len(text) + 1, 1)
        elif (h_align == self._Alignment.CENTER):
            index = floor((int(CONFIG.lcd_width) - len(text)) / 2) + 1

        _Alignment = b"\xFEG" + bytes(chr(index), "utf8")

        if v_align == self._Alignment.TOP:
            _Alignment += b"\x01"
        elif v_align == self._Alignment.BOTTOM:
            _Alignment += b"\x02"

        return _Alignment + bytes(text, "utf8")

    def _reset_lcd(self):

        # Empty LCD screen (X) and send cursor home (H).
        self._dev.write(b"\xFEX\xFEH")

    def _write_header_with_text(self, text=""):

        self._reset_lcd()
        self._write_header()
        self._dev.write(self._align_text(text,
            self._Alignment.CENTER, self._Alignment.BOTTOM))

    def _write_header(self, header="Quod Libet"):

        self._dev.write(self._align_text(header))

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
        hbox.pack_start(label, False, True, 0)

        entry = Gtk.Entry()
        entry.set_text(CONFIG.lcd_dev)
        entry.connect("changed", _path_changed)
        hbox.pack_start(entry, True, True, 0)

        vbox = Gtk.VBox()
        vbox.pack_start(hbox, False, True, 0)

        label = Gtk.Label(label=_("LCD device width (characters):"))
        hbox = Gtk.HBox()
        hbox.pack_start(label, False, True, 0)

        entry = Gtk.Entry()
        entry.set_text(CONFIG.lcd_width)
        entry.connect("changed", _width_changed)
        hbox.pack_start(entry, True, True, 0)

        vbox.pack_start(hbox, True, True, 0)

        label = Gtk.Label(label=_("LCD update interval (ms):"))
        hbox = Gtk.HBox()
        hbox.pack_start(label, False, True, 0)

        entry = Gtk.Entry()
        entry.set_text(CONFIG.lcd_interval)
        entry.connect("changed", _interval_changed)
        hbox.pack_start(entry, True, True, 0)

        vbox.pack_start(hbox, True, True, 0)
        return vbox

    def _failed_initialization(self):

        if not hasattr(self, "_dev"):
            print_e("Matrix Orbital LCD plugin not initialized correctly.")
            return True
        return False

    def enabled(self):

        try:
            self._dev = open(CONFIG.lcd_dev, 'wb', buffering=0)
        except:
            print_e("Matrix Orbital LCD device not found at " + CONFIG.lcd_dev)
            return

        self._reset_lcd()

        # Ready horizontal bars.
        self._dev.write(b"\xFEh")
        # Turn backlight on.
        self._dev.write(b"\xFEB\x00")

        self._write_header()

        self._npld = self._NowPlayingLCDData(self)
        self._tracker = TimeTracker(app.player)
        self._tracker.connect('tick', self._npld.on_tracker_tick)
        self._tracker.set_interval(int(CONFIG.lcd_interval))

    def disabled(self):

        if self._failed_initialization():
            return

        self._tracker.destroy()
        self._reset_lcd()

        # Turn backlight off.
        self._dev.write(b"\xFEF")

    def plugin_on_seek(self, song, msec):

        if self._failed_initialization():
            return

        self._reset_lcd()
        self._npld.prevent_update(1)

        self._write_header("Seeking...")
        percent_played = int(round(msec / float(song.get("~#length", 0)) / 10))

        # Draw a horizontal bar graph starting at column 1 on row 2
        # to the right (0), with a length of 0-100 pixels.
        self._dev.write(b"\xFE\x7C\x01\x02\x00" +
            bytes(chr(percent_played), "utf8"))

    def plugin_on_song_started(self, song):

        if self._failed_initialization() or song is None:
            return

        self._npld.reset()
        self._npld.set_basic_info(song("artist"), song("title"))
        self._npld.set_disc_info(song("album"),
            song.get("discnumber"), song.get("tracknumber"))
        self._reset_lcd()

    def plugin_on_song_ended(self, song, stopped):

        if self._failed_initialization():
            return

        self._npld.reset()
        self._write_header_with_text("* stopped *")

    def plugin_on_paused(self):

        if self._failed_initialization():
            return

        # No need to set pause for trackers manually.
        self._write_header_with_text("* paused *")

    def plugin_on_unpaused(self):

        if self._failed_initialization():
            return

        self._npld.set_forced_update()
