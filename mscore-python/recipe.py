import yaml
import sys
import score

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class Recipe(dict):
    def __init__(self, *args, **kwargs):
        self.update(*args, **kwargs)

    def scores(self):
        return [s['score'] + ".mscx" for s in self['structure'] if 'score' in s]

    def covers(self):
        return [s['cover'] + ".mscx" for s in self['structure'] if 'cover' in s]

    def run(self):
        scores = self.scores()
        if not scores:
            eprint("No scores!")
            exit(1)
        firstScore = score.ScoreFile(scores.pop(0))
        for cover in reversed(self.covers()):
            firstScore.prepend_cover(score.ScoreFile(cover, self))
        for scorefile in scores:
            firstScore.append_score(score.ScoreFile(scorefile), False, True, True)
        firstScore.writeToFile(sys.stdout.buffer)
