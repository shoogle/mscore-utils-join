import xml.etree.ElementTree as ET   # XML parser: <tag attrib="val">text</tag>
import fractions
import string
import jinja2
import yaml
import sys
import os
import datetime

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

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

    def parts(self):
        self.score.findall('Part')

    def staff(self, idx):
        self.score.find("Staff[@id='"+str(idx)+"']")

    def staff_def(self, idx):
        self.score.find("Part/Staff[@id='"+str(idx)+"']")

    def staves(self):
        return self.score.findall('Staff')

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
        for staff in self.staves():
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
                    accidental = ET.SubElement(keysig, 'accidental')
                    accidental.text = "0" # C Major
                    firstVoice.insert(0, keysig)
                    break

    def maxElementID(self):
        max_ID = 0
        for staff in self.staves():
            for elementWithID in staff.findall('.//*[@id]'):
                id = int(elementWithID.get('id'))
                max_ID = max(id, max_ID)
        return max_ID

    def incrementElementIDs(self, offset):
        for staff in self.staves():
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
        for staff in self.staves():
            for measure in staff.findall('.//Measure[@number]'):
                measure_num = int(measure.get('number'))
                max_measure_num = max(measure_num, max_measure_num)
        return max_measure_num

    def incrementMeasureNumbers(self, offset):
        for staff in self.staves():
            for measure in staff.findall('.//Measure[@number]'):
                measure_num = int(measure.get('number'))
                measure.set('number', str(measure_num + offset))

    def incrementTicks(self, offset):
        for staff in self.staves():
            for tick in staff.findall('.//tick'):
                tick_num = int(tick.text)
                tick.text = str(tick_num + offset)

    def ticks(self):
        division = int(self.root.find('Score/Division').text) # ticks per quarter note
        duration = fractions.Fraction(0,4)
        prevTimeSig = fractions.Fraction(4,4)
        for measure in self.firstStaff().findall('Measure'):
            timeSig = None # Does measure contain a time signature?
            for element in measure:
                if element.tag == 'TimeSig':
                    timeSig = element
                    break # TimeSig found, so stop looking
                elif element.tag in ['Note', 'Rest']:
                    break # ignore possible courtesy TimeSig at end of measure.
            children = list(measure)
            if timeSig:
                n = int(timeSig.find('sigN').text)
                d = int(timeSig.find('sigD').text)
                prevTimeSig = fractions.Fraction(n,d)
            length = measure.get('len')
            if length: # anacrusis/irregular measure
                l = fractions.Fraction(length)
                duration += l
            else: # normal measure
                duration += prevTimeSig
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

    def append_score(self, scoreFile, addLineBreak, addPageBreak, addSectionBreak):
        if addPageBreak:
            self.appendLayoutBreak('page')
        elif addLineBreak:
            self.appendLayoutBreak('line')
        if addSectionBreak:
            self.appendLayoutBreak('section')
        else:
            scoreFile.incrementMeasureNumbers(self.maxMeasureNumber())
        scoreFile.explicitCMajorKeySig()
        scoreFile.incrementElementIDs(self.maxElementID())
        scoreFile.incrementTicks(self.ticks())
        for staff in self.staves():
            staff_ID = int(staff.get('id'))
            sameStaffInNextScore = scoreFile.root.find("Score/Staff[@id='"+str(staff_ID)+"']")
            try:
                for child in sameStaffInNextScore:
                    staff.append(child)
            except TypeError:
                break # fewer staves in the next score and now we've used them all

    def writeToFile(self, file):
        self.tree.write(file, encoding="UTF-8", xml_declaration="True")
