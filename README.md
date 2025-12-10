# PlayStation Disc Image Tools

This repo contains a few Python scripts to manipulate PlayStation 1 (PS1 / PSX) and PlayStation 2 (PS2) disc images.

These scripts are designed to run in a folder containing lots of disc images or lots of disc image *archives* and will group / modify things appropriately without making any changes to the original file *contents*, although renaming operations **do** occur on the originals - but if you're following the 01/02/03 sequence this renaming will happen to the single bin/cue pair images generated from your originals.

Options to run the scripts are probably:
- Just plonk a copy in the directory containing your disc images and run it, or
- Call the scripts from some path and use the direcory flags to point to the location of your disc images, or
- Put the script(s) somewhere in your path (such as `/usr/local/bin` if on Linux) and call them in the pwd containing your disc images.

I numbered these scripts because the first three steps are the order it makes sense to run them when converting files for the PS1 - feel free to rename them as you wish.

## Dependencies:
- `python` for scripting,
- `chdman` for data manipulation - specifically for combining bin/wav data, and required for the `01_createSingleBinCue.py` script, and
- `7z` for de/compression - optional for the `01_createSingleBinCue.py` script but mandatory for the `03_compressBinCueGames.py` script.

Further reading about the CHDMAN (Compressed Hunks of Data) tool used for .bin file consolidation:
[https://docs.mamedev.org/tools/chdman.html](https://docs.mamedev.org/tools/chdman.html)

## CAUTION
While I've made reasonable efforts to ensure these scripts are safe & functional, it's likely best to run them against *copies* of the files you wish to manipulate, so in case anything goes awry you've still got your originals! =D

Okay, on with the show....

## PlayStation 1 / PS1 / PSX Disc Image Scripts

### 01_createSingleBinCue.py

#### Purpose
Takes a PS1 game in the format of a single cue file plus multiple bin files and combines it into a single cue/bin pair with .cue file rewriting so that CD audio music works when running on a PS3 via CFW / webMAN MOD.

#### What / How
Run this in a directory with one or more PSX games either as 7z archives or as cue/bin files where each / any game has multiple bin or wav files and it will use MAME's CHDMAN to rewrite it into a single bin/cue pair.

#### Before
Compressed - will extract::
- `My Game.7z`

Or existing extracted files:
- `My Game.cue`
- `My Game (track 01).bin`
- `My Game (track 02).bin`
- ...
- `My Game (track 99).bin`
- etc.

#### After
New `SingleTrackDiscImages` folder exists containing:
- `SingleTrackDiscImages/My Game.bin` <-- Contains all combined tracks for each / any given game combined into a single larger file .bin file
- `SingleTrackDiscImages/My Game.cue` <-- Cue file rewritten to access the single .bin with offsets of where each track exists

The original disc images are not modified in any way - we just create a new bin/cue pair *from* them.

#### Why?
Because if you play PS1 games on a PS3 then you won't get the CD audio music if you have multiple .bin files referenced from a single .cue - but combining them into a single bin/cue pair allows the in-game CD audio to work.

#### Usage
`python 01_createSingleBinCue.py /path/to/ps1-disc-images [--chdman /usr/bin/chdman] [--sevenzip /usr/bin/7z]`

If the script is in the same directory as the bin/cue pairs you don't have to specify a path (`.` is assumed as default) and you can get away with just:
`python 01_creadeSingleBinCue.py`

<hr/>

### 02_tagBinCuePairsWithIDs.py

#### Purpose
Interogates bin/cue/iso games for the product ID then adds it to the filename so that webMAN MOD on the PS3 will show correct cover images in the XMB.

#### What / How
Run this in a directory with one or more PSX games as either bin/cue sets or in ISO format and it will analyse the file to determine the SLUS-XXXX / SLES-XXXX etc. game identifier and add it to the filename. It will also cleanly re-format any existing [SLUS_xxxx] type name that might use an underscore or such rather than a hypen.

#### Before
`My Game.iso`
or
`My Other Game (PAL).cue` / `My Other Game (PAL).bin`

#### After
`My Game [SLUS-XXXX].iso`
or
`My Other Game (PAL) [SLUS-XXXX].cue` / `My Other Game (PAL) [SLUS-XXXX].bin`

**Note**: The .cue file contents will be modified to point to the renamed .bin file, and the original files are renamed (we don't duplicate then rename the dupes).

#### Usage
`python 02_tagBinCuePairsWithIDs.py [directory] [--dry-run]`

<hr/>

### 03_compressBinCueGames.py

#### What / How
Run this in a directory with one or more PSX games as bin/cue pairs and it will grab both files and compress them with max compression & automatic CPU core usage using 7z into a single named archive. It does not delete the original files.

#### Before
`My Game (PAL) [SLUS-XXXX].cue` / `My Game (PAL) [SLUS-XXXX].bin`

#### After
`My Game (PAL).7z` now also exists which contains both `My Game (PAL) [SLUS-XXXX].cue` / `My Game (PAL) [SLUS-XXXX].bin` 

**Note**: The archive name does not contain the product code, I didn't feel it was necessary but feel free to adjust or raise an issue if you feel it makes more sense to keep it.

#### Why?
For archival - raw ISOs or bin/cue formats can often be crunched down significantly, although you likely won't be able to play them directly in this compressed state.

#### Usage
`python 03_compressBinCueGames.py [directory] [--dry-run] [--overwrite] [--sevenzip /path/to/7z] [--level 9] [--threads 0]`

<hr/>

## PlayStation 2 / PS2 Disc Image Scripts

### 04_tagPs2IsosWithIDs.py

#### Purpose
Interrogates and renames PS2 .ISO files to include the product ID so that the cover images match the game and are shown via CFW / webMAN MOD.

#### What / How
Run this in a directory with one or more **PS2** games as ISO files and it will analyse the file to determine the product ID then add that to the filename.

#### Before
`My PS2 Game (PAL).iso`

#### After
`My PS2 Game (PAL) [SLUS-XXXX].iso`

**Note**: The original files are renamed - we don't duplicate then rename the dupes.

#### Usage
`python 04_tagPs2IsosWithIDs.py [directory] [--dry-run]`

## Not Working / Something's Broken

I've only tested this on Linux, but I tried to get it cross-platform by using Python rather than shell scripts. Lemme know if something's not working and I'll see what I can do - or just punt the script at ChatGPT and it'll likely be able to fix it for ya. Feel free to raise a PR if you fix something and as long as it makes sense and doesn't break anything else I'll merge it in =D
