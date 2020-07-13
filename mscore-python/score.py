import xml.etree.ElementTree as ET   # XML parser: <tag attrib="val">text</tag>
import fractions
import string
import jinja2
import re
import yaml
import sys
import os
import datetime

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def tuple(timesig):
    n = int(timesig.find('sigN').text)
    d = int(timesig.find('sigD').text)
    return (n,d)

def fraction(timesig):
    t = tuple(timesig)
    return fractions.Fraction(t[0], t[1])

def elements_equal(e1, e2):
    if e1.tag != e2.tag: return False
    if e1.text != e2.text: return False
    if e1.tail != e2.tail: return False
    if e1.attrib != e2.attrib: return False
    if len(e1) != len(e2): return False
    return all(elements_equal(c1, c2) for c1, c2 in zip(e1, e2))

def stave_defs_equal(sd1, sd2):
    # IDs are allowed to differ but all else must be equal
    saveID = sd1.get('id')
    sd1.set('id', sd2.get('id'))
    result = elements_equal(sd1, sd2)
    sd1.set('id', saveID)
    return result

class ScoreFile:
    def __init__(self, filePath, dictionary=None):
        self.filePath = filePath
        if dictionary:
            self.root = ET.fromstring(self.substitute_variables(dictionary))
            self.tree = ET.ElementTree(self.root)
        else:
            self.tree = ET.parse(filePath)
            self.root = self.tree.getroot()
        self.score = self.root.find('Score')
        self.style = self.score.find('Style')

    def substitute_variables(self, dictionary):
        dirname, basename = os.path.split(self.filePath)
        env = jinja2.Environment(autoescape=jinja2.select_autoescape(['mscx']),loader=jinja2.FileSystemLoader(searchpath=dirname))
        s = env.get_template(basename)
        g = {
            'EOL': '\n',
            'DATE': datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
        }
        return s.render(**g, **dictionary)

    @property
    def parts(self):
        return self.score.findall('Part')

    @property
    def staves(self):
        return self.score.findall('Staff') # excludes Part/Staff (staff defs)

    def part(self, idx):
        return self.parts[idx]

    def staff(self, idx):
        id = idx + 1 # IDs are one-indexed
        return self.score.find("Staff[@id='"+str(id)+"']")

    def staff_def(self, idx):
        id = idx + 1 # IDs are one-indexed
        return self.score.find("Part/Staff[@id='"+str(id)+"']")

    def part_for_staff(self, idx):
        id = idx + 1 # IDs are one-indexed
        return self.score.find("Part/Staff[@id='"+str(id)+"']/..")

    def firstStaff(self):
        return self.score.find('Staff')

    def get_style(self, name):
        return self.style.find(name)

    def set_style(self, name, value):
        style = self.get_style(name)
        if style is None:
            style = ET.Element(name)
            self.style.append(style)
        style.text = value

    @property
    def spatium(self):
        return float(self.get_style('Spatium').text)

    @spatium.setter
    def spatium(self, value):
        self.set_style("Spatium", value)

    def _metaTag(self, name):
        return self.score.find("metaTag[@name=\'" + name + "\']")

    def __getitem__(self, key):
        el = self._metaTag(key)
        return None if el is None else el.text

    def __setitem__(self, key, value):
        el = self._metaTag(key)
        if el is None:
            el = ET.Element("metaTag")
            el.set("name", key)
        el.text = value

    def explicitCMajorKeySig(self):
        # insert a C Major key signature if no key is specified
        for staff in self.staves:
            firstMeasure = staff.find('Measure')
            if firstMeasure is None:
                continue
            firstVoice = firstMeasure.find('voice')
            if firstVoice is None:
                continue
            firstVoice.find('KeySig')
            for element in firstVoice:
                if element.tag == 'KeySig':
                    break # staff already has an explicit keysig
                if element.tag in ['Chord', 'Rest']:
                    # no keysig before first Chord/Rest, so insert one now
                    keysig = ET.Element('KeySig')
                    keysig.tail = "\n          "
                    accidental = ET.SubElement(keysig, 'accidental')
                    accidental.text = "0" # C Major
                    firstVoice.insert(0, keysig)
                    break

    def explicitFinalBarline(self):
        # insert a final 'end' barline if no barline is specified
        for staff in self.staves:
            try:
                finalMeasure = staff.findall('Measure')[-1]
            except IndexError:
                continue # no measures in staff
            firstVoice = finalMeasure.find('voice')
            if firstVoice is None:
                firstVoice = ET.SubElement(finalMeasure, 'voice')
            try:
                lastElement = firstVoice[-1]
                if lastElement.tag == 'BarLine':
                    continue # already has explicit final barline (any kind)
            except IndexError:
                pass # voice is empty
            barline = ET.SubElement(firstVoice, 'BarLine')
            barline.tail = "\n          "
            ET.SubElement(barline, 'subtype').text = 'end'

    def maxElementID(self):
        max_ID = 0
        for staff in self.staves:
            for elementWithID in staff.findall('.//*[@id]'):
                id = int(elementWithID.get('id'))
                max_ID = max(id, max_ID)
        return max_ID

    def incrementElementIDs(self, offset):
        for staff in self.staves:
            for elementWithID in staff.findall('.//*[@id]'):
                ID = int(elementWithID.get('id'))
                elementWithID.set('id', str(ID + offset))
            # update beam and tuplet numbers to match new IDs
            for tag in ["Beam", "Tuplet"]:
                for element in staff.findall('.//' + tag):
                    try:
                        element.text = str(int(element.text) + offset)
                    except ValueError:
                        pass # had an ID, not a number

    def maxMeasureNumber(self):
        max_measure_num = 0
        for staff in self.staves:
            for measure in staff.findall('.//Measure[@number]'):
                measure_num = int(measure.get('number'))
                max_measure_num = max(measure_num, max_measure_num)
        return max_measure_num

    def incrementMeasureNumbers(self, offset):
        for staff in self.staves:
            for measure in staff.findall('.//Measure[@number]'):
                measure_num = int(measure.get('number'))
                measure.set('number', str(measure_num + offset))

    def incrementTicks(self, offset):
        for staff in self.staves:
            for tick in staff.findall('.//tick'):
                tick_num = int(tick.text)
                tick.text = str(tick_num + offset)

    def ticks(self):
        division = int(self.root.find('Score/Division').text) # ticks per quarter note
        duration = fractions.Fraction(0,4)
        currTimeSig = fractions.Fraction(4,4)
        for measure in self.firstStaff().findall('Measure'):
            for element in measure:
                if element.tag == 'TimeSig':
                    currTimeSig = fraction(element)
                    break # TimeSig found, so stop looking
                elif element.tag in ['Note', 'Rest']:
                    break # ignore possible courtesy TimeSig at end of measure.
            children = list(measure)
            length = measure.get('len')
            if length: # anacrusis/irregular measure
                l = fractions.Fraction(length)
                duration += l
            else: # normal measure
                duration += currTimeSig
        return duration * division * 4

    def appendLayoutBreak(self, type): # line, page, section
        if self.firstStaff().find('Measure') is not None:
            layoutBreak = ET.Element('LayoutBreak')
            subtype = ET.SubElement(layoutBreak, 'subtype')
            subtype.text = type
            finalMeasure = self.firstStaff().findall('Measure')[-1]
            finalMeasure.append(layoutBreak)

    def scale_frame_height(self, spatium):
        for h in self.score.findall('.//height'):
            h.text = str(float(h.text) * self.spatium / spatium)

    def add_text_styles_from_score_file(self, score_file):
        style = self.score.find('Style')
        for text_style in score_file.score.findall('Style/TextStyle/name/..'):
            style_name = text_style.find('name').text
            # Only add named styles that do not already exist in this score
            if style.find('TextStyle[name=\'' + style_name + '\']') == None:
                style.append(text_style)

    def prepend_cover(self, cover):
        cover.scale_frame_height(self.spatium)
        firstStaff = self.firstStaff()
        for frame in reversed(cover.firstStaff()):
            if frame.tag == "Measure":
                break
            firstStaff.insert(0, frame)
        self.add_text_styles_from_score_file(cover)

    def fix_instrument_names(self):
        instruments = {}
        for instrument in self.score.findall(".//Instrument"):
            long_name = instrument.find("longName").text
            if long_name in instruments:
                instruments[long_name].append(instrument)
            else:
                instruments[long_name] = [instrument]
        for long_name, occurrences in instruments.items():
            total = len(occurrences)
            match = re.search("^(([A-H]♭?) )?(.*?)( in (.*))?$", long_name)
            assert(match)
            key = match.group(2)
            if not key:
                key = match.group(5)
            long = match.group(3)
            match = re.search("^(([A-H]♭?) )?(.*?)( in (.*))?$", occurrences[0].find("shortName").text)
            assert(match)
            short = match.group(3)
            for num, instrument in enumerate(occurrences, 1):
                for tag in ["longName", "shortName", "trackName"]:
                    text = short if tag == "shortName" else long
                    if total > 1:
                        text += " " + str(num)
                    if key:
                        text += ("\n" if tag == "shortName" else " ") + "in " + key
                    instrument.find(tag).text = text

    def append_score(self, scoreFile, addLineBreak, addPageBreak, addSectionBreak):
        # score1 must include all parts and staves that are in score2.
        # score2 needn't include all parts and staves from score1.
        assert(len(self.parts)  >= len(scoreFile.parts))
        assert(len(self.staves) >= len(scoreFile.staves))

        self.explicitFinalBarline()

        if addPageBreak:
            self.appendLayoutBreak('page')
        elif addLineBreak:
            self.appendLayoutBreak('line')

        if addSectionBreak:
            self.appendLayoutBreak('section')
        else:
            scoreFile.incrementMeasureNumbers(self.maxMeasureNumber())

        scoreFile.explicitCMajorKeySig()
        scoreFile.explicitFinalBarline()
        scoreFile.incrementElementIDs(self.maxElementID())
        scoreFile.incrementTicks(self.ticks())

        p_idx2 = 0
        s_idx2 = 0
        part2 = scoreFile.part(p_idx2)   # same part in next score
        staff2 = scoreFile.staff(s_idx2) # same staff in next score

        for p_idx1, part1 in enumerate(self.parts):

            long_name = part1.find("Instrument/longName").text
            eprint(long_name)

            if long_name != part2.find("Instrument/longName").text:
                # part1 not in score2 so fill part1 staves with
                # empty measures for the duration of part2.
                eprint("Part1 not found in " + scoreFile.filePath)
                for staff_def in part1.findall('Staff'):
                    s_idx1 = int(staff_def.get('id')) - 1
                    staff1 = self.staff(s_idx1)
                    currTimeSig = fractions.Fraction(4,4)
                    for measure in staff2:
                        if measure.tag != 'Measure':
                            staff1.append(measure) # append frames
                            continue
                        for element in measure:
                            if element.tag == 'TimeSig':
                                currTimeSig = fraction(element)
                                break # TimeSig found, so stop looking
                            elif element.tag in ['Note', 'Rest']:
                                break # ignore possible courtesy TimeSig at end of measure.
                        rest = ET.Element('Rest')
                        ET.SubElement(rest, 'durationType').text = 'measure'
                        ET.SubElement(rest, 'duration').text = str(currTimeSig)
                        staff1.append(rest)
                continue

            instrument1 = part1.find("Instrument")
            instrument2 = part2.find("Instrument")

            short_name = instrument1.find("shortName").text
            track_name = instrument1.find("trackName").text
            instrument_id = instrument1.find("instrumentId").text

            assert(short_name == instrument2.find("shortName").text)
            assert(track_name == instrument2.find("trackName").text)
            assert(instrument_id == instrument2.find("instrumentId").text)

            for staff_def in part1.findall('Staff'):
                s_idx1 = int(staff_def.get('id')) - 1
                staff1 = self.staff(s_idx1)

                if not part2 is scoreFile.part_for_staff(s_idx2) or not stave_defs_equal(staff_def, scoreFile.staff_def(s_idx2)):
                    eprint("Staff1 not found in " + scoreFile.filePath)
                    # staff1 not in score2 so fill staff1 with
                    # empty measures for the duration of staff2.
                    currTimeSig = (4,4)
                    for measure in staff2:
                        if measure.tag != 'Measure':
                            # append frames to first staff only
                            if s_idx1 == 0:
                                staff1.append(measure)
                            continue
                        new_measure = ET.SubElement(staff1, 'Measure')
                        new_measure.text = "\n        "
                        new_measure.tail = "\n      "
                        foundVoice = False
                        for voice in measure:
                            if voice.tag != 'voice':
                                # keep layout breaks
                                new_measure.append(voice)
                                continue
                            # keep first voice only
                            if foundVoice:
                                continue
                            foundVoice = True
                            new_voice = ET.SubElement(new_measure, 'voice')
                            new_voice.text = "\n          "
                            new_voice.tail = "\n        "
                            foundCR = False
                            for element in voice:
                                if element.tag in ['Chord', 'Rest']:
                                    if foundCR:
                                        continue # don't add element.
                                    foundCR = True
                                    # Create single rest to fill measure.
                                    rest = ET.SubElement(new_voice, 'Rest')
                                    rest.tail = "\n          "
                                    ET.SubElement(rest, 'durationType').text = 'measure'
                                    # ET.SubElement(rest, 'duration').text = "%s/%s" % currTimeSig
                                    continue # don't add original element
                                if element.tag == 'TimeSig':
                                    # Is it a courtesy timesig at end of measure?
                                    if not foundCR: # No, it is real timesig.
                                        currTimeSig = tuple(element)
                                new_voice.append(element)
                    continue

                eprint("Part: %s, %s %s %s" % (p_idx1, long_name, short_name, track_name))
                for child in staff2:
                    staff1.append(child)
                s_idx2 += 1
                try:
                    staff2 = scoreFile.staff(s_idx2)
                except IndexError:
                    s_idx2 -= 1 # stay on previous staff

            # move to first staff in next part
            p_idx2 += 1
            try:
                part2 = scoreFile.part(p_idx2)
            except IndexError:
                p_idx2 -= 1 # stay on previous part

    def writeToFile(self, file):
        self.tree.write(file, encoding="UTF-8", xml_declaration="True")
