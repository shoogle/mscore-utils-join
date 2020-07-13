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

parser.add_argument("files", nargs='+', help="path to input files")

breaks = parser.add_mutually_exclusive_group()
breaks.add_argument("-l", "--line-breaks", action="store_true", help="add line breaks between scores (can't be used with -p)")
breaks.add_argument("-p", "--page-breaks", action="store_true", help="add page breaks between scores (can't be used with -l)")

parser.add_argument("-s", "--section-breaks", action="store_true", help="add section breaks between scores") # can use with with -l and -p
parser.add_argument("-c", "--cover", type=str, action="append", help="insert frames from score file")
parser.add_argument("-d", "--dictionary", type=str, action="append", help="path to YAML (.yml) file with variable substitutions")

parser.add_argument("-t", "--template", action="store_true", help="fix instrument names in a template score")


try:
    argcomplete.autocomplete(parser)
except NameError:
    pass # no bash completion :(

args = parser.parse_args()

# argcomplete has exited by this point, so here comes the actual program code.

import recipe
import score
import sys
import yaml

if args.files[0].endswith(".yml"):
    r = recipe.Recipe(yaml.safe_load(open(args.files[0])))
    r.run()
    exit()

firstScore = score.ScoreFile(args.files.pop(0))

if args.template:
    firstScore.fix_instrument_names()
    firstScore.writeToFile(sys.stdout.buffer)
    exit()

dictionary = {}
if args.dictionary:
    for path in args.dictionary:
        d = yaml.safe_load(open(path))
        dictionary.update(d)
    score_id = dictionary['id']['musescore']
    if isinstance(score_id, int) or score_id.isdigit():
        score_url = "https://musescore.com/score/{0}".format(score_id)
    else:
        score_url = ""
    firstScore['source'] = score_url

if args.cover:
    firstScore['movementNumber'] = ""
    firstScore['movementTitle'] = ""
    firstScore.set_style('footerFirstPage', '0')
    firstScore.score.find('showInvisible').text = '0'
    firstScore.score.find('showUnprintable').text = '0'
    firstScore.score.find('showFrames').text = '0'
    firstScore.score.find('showMargins').text = '0'
    for cover in reversed(args.cover):
        firstScore.prepend_cover(score.ScoreFile(cover, dictionary))

for file in args.files:
    firstScore.append_score(score.ScoreFile(file), args.line_breaks, args.page_breaks, args.section_breaks)

firstScore.writeToFile(sys.stdout.buffer)
