# Matrix Orbital LCD display Quod Libet plugin

A Quod Libet media player event plugin to show information about the currently playing song in a Matrix Orbital LCD display such as the MX2 or MX3 series (LK202).

It shows if Quod Libet is paused or playing or seeking (also the seek point is shown). When playing, the plugin cycles through artist/title and album/track views. The artist/title view is scrolled if it doesn't fit in the display.

![Picture](picture.jpg)

The picture is from a computer case equipped with an LK202 display, showing artist and title of the currently playing track.

## Requirements

* A Matrix Orbital LCD display. Probably works with several different models, tested using LK202. Supports two rows. Column count is configurable, as is the serial TTY device location.
* Developed against Quod Libet 4.x. Might work on earlier versions.
* Written in Python 3, will not work with Python 2.
* The plugin uses the Unidecode module for transliterations.

## Installation

Copy the plugin into `~/.quodlibet/plugins/events/`. Enable write access to `/dev/ttyUSB0` or wherever the display is located. Configure the location for the plugin.
