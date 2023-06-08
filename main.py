import os
import re
import copy
from fractions import Fraction
import math
import sys

beatmap = '''osu file format v14

[General]
AudioFilename: audio.mp3
AudioLeadIn: 0
PreviewTime: -1
Countdown: 0
SampleSet: Normal
StackLeniency: 0.7
Mode: 1
LetterboxInBreaks: 0
WidescreenStoryboard: 0

[Editor]
DistanceSpacing: 0.8
BeatDivisor: 7
GridSize: 32
TimelineZoom: 1

[Metadata]
Title: {}
TitleUnicode: {}
Artist: Unknown
ArtistUnicode: Unknown
Creator: Unknown
Version: {}
Source:
Tags: donscore
BeatmapID:0
BeatmapSetID:-1

[Difficulty]
HPDrainRate:5
CircleSize:5
OverallDifficulty:9
ApproachRate:5
SliderMultiplier:1.4
SliderTickRate:1

[Events]
//Background and Video events
//Break Periods
//Storyboard Layer 0 (Background)
//Storyboard Layer 1 (Fail)
//Storyboard Layer 2 (Pass)
//Storyboard Layer 3 (Foreground)
//Storyboard Layer 4 (Overlay)
//Storyboard Sound Samples'''

formats = {
    'timing': '{},{},{},1,0,100,{},{}', # time, length, meter, inherited, kiai
    'don': '256,192,{},1,0,0:0:0:0:', # time
    'ka': '256,192,{},1,2,0:0:0:0:', # time
    'bigdon': '256,192,{},1,4,0:0:0:0:', # time
    'bigka': '256,192,{},1,12,0:0:0:0:', # time
    'slide': '256,192,{},2,0,L|{}:192,1,{}', # time, x, beatlength
    'bigslide': '256,192,{},2,1,L|{}:192,1,{}', # time, x, beatlength
    'spin': '256,192,{},12,0,{}', # time, end
}

difficulty = {
    'かんたん': 'Kantan',
    'ふつう': 'Futsuu',
    'むずかしい': 'Muzukashii',
    'おに': 'Oni',
}

metadata = {}

param = {
    'pos': Fraction(0),
    'time': 0,
    'bpm': 120,
    'duration': 60000 / 120,
    'meter': [4, 4],
    'scroll': 1,
    'char': 4,
    'gogo': False,
    'line': False,
}
branch = [True, False, False]
branch_now = 0
backup = []
cmd_list = []
cmd_tmp = []
osu = []
uninherited_changed = False
inherited_changed = False
osu_bar = [[[], []], [[], []], [[], []]]

def is_power_of_two(n):
    while n > 1:
        if n & 1 != 0:
            return False
        n = n // 2
    return n == 1


def parse(text:list[str], offset:float) -> str:
    global metadata, param, branch, branch_now, backup, cmd_list, cmd_tmp, osu, uninherited_changed, inherited_changed, osu_bar
    long_start = 0
    param['time'] = offset
    for line in text:
        line = line.strip('\n')
        if line.startswith('#'):
            cmd = line.split(' ')
            match cmd[0]:
                case '#bpm':
                    bpm = float(cmd[1])
                    pos = Fraction(0)
                    if len(cmd) > 2:
                        pos = Fraction('/'.join(cmd[3:1:-1]))
                    cmd_list.append(('bpm', pos, bpm))
                case '#meter':
                    meter = [int(cmd[2]), int(cmd[1])]
                    cmd_list.append(('meter', Fraction(0), meter))
                case '#hs':
                    hs = float(cmd[1])
                    pos = Fraction(0)
                    if len(cmd) > 2:
                        pos = Fraction('/'.join(cmd[3:1:-1]))
                    cmd_list.append(('hs', pos, hs))
                case '#begingogo':
                    pos = Fraction(0)
                    if len(cmd) > 1:
                        pos = Fraction('/'.join(cmd[2:0:-1]))
                    cmd_list.append(('begingogo', pos))
                case '#endgogo':
                    pos = Fraction(0)
                    if len(cmd) > 1:
                        pos = Fraction('/'.join(cmd[2:0:-1]))
                    cmd_list.append(('endgogo', pos))
                case '#beatchar':
                    char = int(cmd[1])
                    param['char'] = char
                case '#branch':
                    branch = [c == 'o' for c in cmd[1]]
                    branch_now = [i for i in range(3) if branch[i]][-1]
                case '#barlineon':
                    cmd_list.append(('barlineon', Fraction(0)))
                case '#barlineoff':
                    cmd_list.append(('barlineoff', Fraction(0)))
                case '#title':
                    metadata['title'] = cmd[1]
                case '#difficulty':
                    metadata['difficulty'] = cmd[1]
                case '#level':
                    metadata['level'] = cmd[1]
        else:
            if branch_now == [i for i in range(3) if branch[i]][-1]: # if branch is end
                osu.append(osu_bar)
                backup = [param, cmd_list]
                osu_bar = [None, None, None]
            while not branch[branch_now:=(branch_now+1)%3]: pass # goto next branch
            param = copy.deepcopy(backup[0])
            cmd_list = copy.deepcopy(backup[1])
            cmd_list.extend(cmd_tmp)
            pos = Fraction(0)
            if osu_bar[branch_now] is None:
                osu_bar[branch_now] = [[], []]
            in_balloon = False
            triplet_num = 0
            balloon_num = ''
            i = 0
            while i < len(line) or i % (param['meter'][0] * param['char']) != 0:
                # print(i, param['meter'][0] * param['char'])
                n = line[i] if i < len(line) else ' '
                i += 1
                # process command
                cmd_now = list(filter(lambda i: i[1] == pos, cmd_list))
                cmd_list = list(filter(lambda i: i[1] != pos, cmd_list))
                for cmd in cmd_now:
                    match cmd[0]:
                        case 'bpm':
                            param['duration'] = 60000 / cmd[2] * 4 / param['meter'][1]
                            param['bpm'] = cmd[2]
                            uninherited_changed = True
                        case 'meter':
                            param['duration'] = 60000 / param['bpm'] * 4 / cmd[2][1]
                            param['meter'] = cmd[2]
                            uninherited_changed = True
                        case 'hs':
                            param['scroll'] = cmd[2]
                            inherited_changed = True
                        case 'begingogo':
                            param['gogo'] = True
                            inherited_changed = True
                        case 'endgogo':
                            param['gogo'] = False
                            inherited_changed = True
                        case 'barlineon':
                            param['line'] = True
                            uninherited_changed = True
                        case 'barlineoff':
                            param['line'] = False
                            uninherited_changed = True
                # timingpoint
                # continuous irregular meter
                if float(pos) % param['meter'][0] == 0 and \
                    (param['meter'][0] / param['meter'][1] * 4) % 1 != 0:
                    uninherited_changed = True
                if uninherited_changed:
                    effect = int(param['gogo']) + 8 * int(param['line'])
                    osu_bar[branch_now][0].append(
                        formats['timing'].format(
                            int(param['time']),
                            round(60000 / param['bpm'], 2),
                            math.ceil(param['meter'][0] / param['meter'][1] * 4),
                            1,
                            effect))
                if inherited_changed or (uninherited_changed and param['scroll'] != 1):
                    osu_bar[branch_now][0].append(
                        formats['timing'].format(
                            int(param['time']),
                            round(-100 / param['scroll'], 2),
                            math.ceil(param['meter'][0] / param['meter'][1] * 4),
                            0,
                            int(param['gogo'])))
                inherited_changed = False
                uninherited_changed = False
                # note
                # in balloon
                if in_balloon and n.isdigit():
                    balloon_num += n
                match n:
                    case 'o' | 'c':
                        osu_bar[branch_now][1].append(formats['don'].format(int(param['time'])))
                    case 'O' | 'C':
                        osu_bar[branch_now][1].append(formats['bigdon'].format(int(param['time'])))
                    case 'x':
                        osu_bar[branch_now][1].append(formats['ka'].format(int(param['time'])))
                    case 'X':
                        osu_bar[branch_now][1].append(formats['bigka'].format(int(param['time'])))
                    case '<' | '(':
                        long_start = param['time']
                    case '>' | ')':
                        t = 'slide' if n == '>' else 'bigslide'
                        length = int((param['time'] + param['duration'] / param['char'] - long_start) \
                                  / param['duration'] * param['scroll'] * 1.4 * 100)
                        osu_bar[branch_now][1].append(
                            formats[t].format(int(long_start), 256 + length, length))
                    case '[':
                        long_start = param['time']
                        in_balloon = True
                    case ']':
                        osu_bar[branch_now][1].append(
                            formats['spin'].format(
                                int(long_start), int(param['time'] + param['duration'] / param['char'])))
                        in_balloon = False
                    case '3' if not in_balloon:
                        triplet_num = 3
                        param['duration'] = param['duration'] / 3 * 4
                        # print('increase: ', param['duration'], line)
                        continue

                pos += Fraction(1, param['char'])
                param['pos'] = pos
                param['time'] += param['duration'] / param['char']
                # in triplet
                if triplet_num >= 1:
                    if triplet_num == 1:
                        param['duration'] = param['duration'] / 4 * 3
                        # print('decrease: ', param['duration'])
                    triplet_num -= 1
            cmd_tmp.clear()
    osu.append(osu_bar)

def dump(branch:list[bool], version:str=None) -> list[str]:
    result = []
    if (diff:=metadata.get('difficulty')):
        version = difficulty[diff]
    if version:
        version = input('version: ')
    metadata['version'] = version
    for n, b in enumerate(branch):
        tmp = beatmap
        if not b:
            continue
        tp =  '\n\n[TimingPoints]\n'
        ho =  '\n\n[HitObjects]\n'
        tmp = tmp.format(metadata['title'], metadata['title'], version)
        for s in osu:
            section = s[n] if s[n] is not None else s[0]
            for t in section[0]:
                tp += t + '\n'
            for h in section[1]:
                ho += h + '\n'
        tmp += tp + ho
        result.append(tmp)
    return result



if __name__ == '__main__':
    file = sys.argv[1]
    # file =  r"C:\Users\egnosyz\Downloads\joyful.txt"
    path = os.path.dirname(file)
    with open(file, 'r', encoding='sjis') as f:
        parse(f.readlines(), float(input('offset: ')))
        f.seek(0)
        text = f.read()
    dump_branch = [True, False, False]
    for b in re.findall(r'#branch.+', text):
        for i, c in enumerate(b.strip().split(' ')[1]):
            dump_branch[i] = c == 'o'
    branches = dump(dump_branch)
    branch_name = ['Normal', 'Professional', 'Master']
    for n, b in enumerate(dump_branch):
        if b:
            name = f"{metadata['title']} [{metadata['version']}] [{branch_name[n]}].osu"
            name = os.path.join(path, name)
            print(name)
            with open(name, 'w', encoding='utf-8') as f:
                f.write(branches[n])