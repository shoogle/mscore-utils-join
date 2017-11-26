import xml.etree.ElementTree as ET   # XML parser: <tag attrib="val">text</tag>
import fractions

class ScoreFile:
    def __init__(self, filePath):
        self.filePath = filePath
        self.tree = ET.parse(filePath)
        self.root = self.tree.getroot()
        self.staves = self.root.findall('Score/Staff')

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
        prevTimeSig = fractions.Fraction(4,4)
        for measure in self.staves[0].findall('Measure'):
            timeSig = measure.find('TimeSig')
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
        layoutBreak = ET.Element('LayoutBreak')
        subtype = ET.SubElement(layoutBreak, 'subtype')
        subtype.text = type
        finalMeasure = self.staves[0].findall('Measure')[-1]
        finalMeasure.append(layoutBreak)

    def append(self, scoreFile, addLineBreak, addPageBreak, addSectionBreak):
        if addPageBreak:
            self.appendLayoutBreak('page')
        elif addLineBreak:
            self.appendLayoutBreak('line')
        if addSectionBreak:
            self.appendLayoutBreak('section')
        else:
            scoreFile.incrementMeasureNumbers(self.maxMeasureNumber())
        scoreFile.incrementElementIDs(self.maxElementID())
        scoreFile.incrementTicks(self.ticks())
        for staff in self.staves:
            staff_ID = int(staff.get('id'))
            sameStaffInNextScore = scoreFile.root.find("Score/Staff[@id='"+str(staff_ID)+"']")
            try:
                for child in sameStaffInNextScore:
                    staff.append(child)
            except TypeError:
                break # fewer staves in the next score and now we've used them all

    def writeToFile(self, file):
        self.tree.write(file, encoding="UTF-8", xml_declaration="True")
