# NEZ - NES Emulator

A Nintendo Entertainment System (NES) emulator **vibe-coded** in Python.  

An experiment to see how close to a working emulator I can get, using both Warp and GitHub Copilot with various incantations of prompts and models. I'll write a bit more about this later if it gets close to working. I'm reviewing basically none of the generated code, instead I'm just giving the LLMs feedback based on my experience when running the emulator and steering it on areas I think it may need to focus on.  

Right now it can _kind_ of load some games/ROMs, but theres a ton of corruption and performance is terrible!

I had assumed that being a 40 year old, incredibly well documented platform, that the LLMs may have been able to build this relatively easily. So far it's been a nightmare, but I'm stubborn so going to keep nudging this along.

## Screenshots

<p align="center">
    <img src="screenshots/c0.png" alt="Screenshot of NEZ running" width="50%">
</p>
<p align="center">
    <img src="screenshots/c1.png" alt="Screenshot of NEZ running" width="50%">
</p>
<p align="center">
    <img src="screenshots/c2.png" alt="Screenshot of NEZ running" width="50%">
</p>


## Things I have found are not great when attempting this

- Can blow through a months Warp quota in a couple of hours when asking it to dive deep into implementing/reviewing logs. Copilot isn't much better. This experiment is doing a lot of iterating/scanning huge log output so perhaps understandable, but it doesn't feel like you get many credits for your money.
- GitHub Copilot can't read zsh terminal output properly. Switching it to bash seems to be more reliable.
- GitHub Copilot can't auto run commands, so have to repeatedly click to allow it to grep logs, etc. It looks like they might be fixing this soon.
- GitHub Copilot seems to hardly ever consider the `copilot-instructions.md` file.
- The "lower" models (GPT <5, the free models with copilot, gemini) are often lazy and like to either propose changes vaguely, and not actually implement them even though they are in agent mode. Or they don't consider the full context, often deleting large swathes of code with placeholders like `# Rest of code here`. Sometimes I catch this, but I'm mostly not reviewing the code. Instead, commit often and revert if it seems to have regressed. I'm sure the spaghetti factor here is horrendous as a result.
- The lower models often like to duplicate functions. Again it seems that they are not reviewing/considering the full context of the codebase (even when asked). Often times I've had to tell it to go and consolidate duplicate/similar methods. Similarly they have a tendency to create placeholder or stub methods.
- As a result, using non-premium models is basically pointless / will result in a mess and set you back.

## Installation

Using pipenv:

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
