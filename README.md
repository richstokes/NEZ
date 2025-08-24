# NEZ - NES Emulator

A Nintendo Entertainment System (NES) emulator **vibe-coded** in Python.  

Curious to see how close to a working emulator I can get, using both Warp and GitHub Copilot with various incantations of prompts and models. I'll write a bit more about this later if it gets close to working.

Right now it can _kind_ of load some games/ROMs, but theres a ton of corruption and performance is terrible!

I had assumed that being a 40 year old, incredibly well documented platform, that the LLMs may have been able to build this relatively easily. So far it's been a nightmare, but I'm stubborn so going to keep nudging this along.

## Screenshots

<p align="center">
    <img src="screenshots/c0.png" alt="Screenshot of NEZ running" width="50%">
</p>
<p align="center">
    <img src="screenshots/c1.png" alt="Screenshot of NEZ running" width="50%">
</p>

## Things that are annoying when attempting this

- Can blow through a months Warp quota in a couple of hours when asking it to dive deep into implementing/reviewing logs. Copilot isn't much better.
- GitHub Copilot can't read zsh terminal output properly. Switching it to bash seems to be more reliable.
- GitHub Copilot can't auto run commands, so have to repeatedly click to allow it to grep logs, etc. It looks like they might be fixing this soon.

## Installation

The environment is already set up with pipenv. Just activate it:

```bash
pipenv install
```

## Usage

Run the emulator with a ROM file:

```bash
pipenv run python main.py mario.nes
```

### Controls

| Key | NES Button |
|-----|------------|
| Arrow Keys | D-Pad |
| J | A Button |
| K | B Button |
| Space | Select |
| Enter | Start |
| R | Reset System |
| Escape | Quit |

## Contributions

Contributions are welcome! Feel free to throw up a PR if you know of any changes that could help!
