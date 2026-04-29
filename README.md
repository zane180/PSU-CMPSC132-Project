# Snake & Ladder Game

**CMPSC 132 — Final Project**

## Project Description

A terminal-based Snake & Ladder game played on a 1-to-100 board. Two players (or one player vs. an AI) take turns rolling a dice and racing to land exactly on cell 100. Landing on a snake head slides you down, a ladder base climbs you up, a boost cell advances you extra spaces, and a trap cell makes you skip your next turn.

The program uses the data structures covered in class:
- **dict** — for snakes, ladders, boosts, dice faces, and difficulty settings (O(1) lookup)
- **set** — for trap cells (O(1) membership check)
- **deque** — used as a queue to rotate turns between players
- **list** — used as a stack to record a history of moves

### Features
- 10x10 board display with player tokens
- Boost cells (+5 spaces) and trap cells (skip a turn)
- End-of-game statistics and recent move history
- Replay option after each game
- One-player mode against a simple AI

### Extra-Credit Features
- ANSI color-coded board (snakes red, ladders green, boosts cyan, traps yellow)
- ASCII dice face shown on every roll
- Three difficulty levels (Easy, Normal, Hard) stored as a dict of dicts

## How to Run

1. Make sure you have **Python 3** installed.
2. Open a terminal in the folder containing the project file.
3. Run the program:
   ```
   python snake_ladder.py
   ```
   (Use `python3` instead if that's how Python is set up on your machine.)
4. Follow the prompts:
   - Choose a difficulty (1, 2, or 3)
   - Choose a game mode (1 for two players, 2 for vs. AI)
   - Enter player name(s)
   - Press Enter on your turn to roll the dice
5. After the game ends, enter `y` to play again or `n` to quit.

No external libraries are needed — the program only uses the standard library (`sys`, `random`, `time`, `collections`).
