#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK - see https://argcomplete.readthedocs.io/

# Argcomplete generates Bash completions dynamically by running the file up to
# the point where arguments are parsed. Want minimal code before this point.

import argparse

try:
    import argcomplete
except ImportError:
    pass # no bash completion :(

parser = argparse.ArgumentParser()

parser.add_argument("file", action="store", help="path to input MSCX files")

parser.add_argument("-m", "--meta-tags", nargs="+", help="set tags passed in as a list of metaTag='Tag value' pairs")
parser.add_argument("-t", "--title-frame", action="store_true", help="set title frame based on score's metatags")

try:
    argcomplete.autocomplete(parser)
except NameError:
    pass # no bash completion :(

args = parser.parse_args()

# argcomplete has exited by this point, so here comes the actual program code.

import score
import sys

song = score.ScoreFile(args.file)

if args.meta_tags:
    for tag_pair in args.meta_tags:
        t = tag_pair.split("=") # e.g.: composer="Ludwig van Beethoven"
        tag = t[0]
        val = t[1]
        song.set_meta_tag(tag, val)

if args.title_frame:
    def set_title_from_tag(title, tag):
        value = song.get_meta_tag(tag)
        if value == None:
            return False
        song.set_frame_text(title, value)
        return True

    set_title_from_tag("Composer", "composer")
    set_title_from_tag("Lyricist", "lyricist")

    mvt = song.get_meta_tag("movementTitle")

    if mvt == None or mvt == "" or mvt == song.get_meta_tag("workTitle"):
        # work contains only one song
        set_title_from_tag("Title", "workTitle")
        song.set_meta_tag("movementTitle", "")
        song.set_meta_tag("movementNumber", "")
    else:
        # work contains multiple songs, so treat this song as a movement
        song.delete_frame_text("Title")
        set_title_from_tag("Work Title", "workTitle")
        set_title_from_tag("Movement Title", "movementTitle")

song.writeToFile(sys.stdout.buffer)
