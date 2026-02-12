# Ursina 3D Racing Game

A simple 3D racing prototype built with Python and the **Ursina** engine.

## Prerequisites

- Python 3.10+
- `pip`

## Installation

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install ursina
```

## Run the game

```bash
python racing_game.py
```

## Controls

- **W / Up Arrow**: accelerate forward
- **S / Down Arrow**: brake / reverse
- **A / Left Arrow**: steer left
- **D / Right Arrow**: steer right

## Gameplay notes

- Avoid hitting red barriers; collisions bounce and reduce speed.
- Cross the white start/finish line to increment laps.
- UI displays lap count, current lap timer, and best lap.
