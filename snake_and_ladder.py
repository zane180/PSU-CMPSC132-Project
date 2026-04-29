# =============================================================================
# Snake & Ladder Game  —  CMPSC 132 Final Project
# =============================================================================
# Description:
#   A 2-player (or 1-player vs AI) terminal Snake & Ladder game played on a
#   1-to-100 board. Players roll a dice and move forward; landing on a snake
#   head slides them down, a ladder base climbs them up, a boost advances them
#   extra spaces, and a trap makes them skip their next turn.
#
# Data structures used:
#   dict  — snakes, ladders, boosts, DIFFICULTIES, DICE_FACES  (O(1) lookup)
#   set   — traps                                               (O(1) membership)
#   deque — Game.turn_queue   (Queue:  O(1) popleft / append)
#   list  — Game.history      (Stack:  append to push, slice to peek)
#
# Base enhancements:
#   - 10x10 board visualization with cell labels and player tokens
#   - Boost cells (+5 spaces) and Trap cells (lose next turn)
#   - Per-player game statistics + recent move history
#   - Replay option after each game
#   - Single-player mode against a simple AI opponent
#
# Extra-credit enhancements:
#   - ANSI color-coded board  (snakes=red, ladders=green, boosts=cyan, traps=yellow)
#   - ASCII dice face display  (dict of lists, shown on every roll)
#   - Difficulty levels        (Easy / Normal / Hard stored as a dict of dicts)
# =============================================================================

import sys
import random
import time
from collections import deque


# =============================================================================
#  Color  —  ANSI terminal colors (extra credit)
# =============================================================================
class Color:
    """
    ANSI escape codes for terminal color output.
    wrap() is a no-op when stdout is not a live terminal,
    so the game still works correctly if output is redirected.
    """
    RED    = '\033[91m'   # used for snakes
    GREEN  = '\033[92m'   # used for ladders
    YELLOW = '\033[93m'   # used for traps
    CYAN   = '\033[96m'   # used for boosts
    BOLD   = '\033[1m'    # used for headers and player tokens
    RESET  = '\033[0m'

    @classmethod
    def wrap(cls, text, code):
        """Surround text with an ANSI color code only when writing to a terminal."""
        if sys.stdout.isatty():
            return f"{code}{text}{cls.RESET}"
        return text  # plain text when output is redirected


# =============================================================================
#  Dice faces  —  dict of lists  (extra credit)
# =============================================================================
# Key   : dice value (1-6)
# Value : list of strings representing the ASCII art face
DICE_FACES = {
    1: ["+---------+", "|         |", "|    *    |", "|         |", "+---------+"],
    2: ["+---------+", "|  *      |", "|         |", "|      *  |", "+---------+"],
    3: ["+---------+", "|  *      |", "|    *    |", "|      *  |", "+---------+"],
    4: ["+---------+", "|  *   *  |", "|         |", "|  *   *  |", "+---------+"],
    5: ["+---------+", "|  *   *  |", "|    *    |", "|  *   *  |", "+---------+"],
    6: ["+---------+", "|  *   *  |", "|  *   *  |", "|  *   *  |", "+---------+"],
}


# =============================================================================
#  Required board data  (exact values from assignment spec)
# =============================================================================
snakes  = {16: 6, 48: 30}   # key = snake head,  value = snake tail
ladders = {3: 22, 20: 38}   # key = ladder base, value = ladder top

# =============================================================================
#  Difficulty levels  —  dict of dicts  (extra credit)
# =============================================================================
# Outer dict : menu key  -> difficulty config
# Inner dict : board settings for that difficulty
# Normal difficulty references the spec-required snakes/ladders defined above.
DIFFICULTIES = {
    '1': {
        'name':        'Easy',
        'snakes':      {48: 30},
        'ladders':     {3: 22, 20: 38, 28: 76},
        'description': 'One snake, three ladders',
    },
    '2': {
        'name':        'Normal',
        'snakes':      snakes,           # exact spec values: {16: 6, 48: 30}
        'ladders':     ladders,          # exact spec values: {3: 22, 20: 38}
        'description': 'Standard rules (assignment spec)',
    },
    '3': {
        'name':        'Hard',
        'snakes':      {16: 6, 32: 12, 48: 30, 62: 19, 88: 44, 95: 72},
        'ladders':     {3: 22, 20: 38},
        'description': 'Six snakes, two ladders',
    },
}

# Enhancement: additional special cells (no overlap with snakes / ladders)
boosts = {10: 5, 25: 5, 50: 5}   # dict: key = cell, value = bonus spaces forward
traps  = {35, 60, 75}             # set:  cells where the player loses a turn


# =============================================================================
#  Player
# =============================================================================
class Player:
    """
    Represents one player in the game.

    Attributes:
        name        (str)  : display name
        is_ai       (bool) : True if controlled by the computer
        position    (int)  : current cell (0 = Start, before cell 1)
        skip_turn   (bool) : True when the player must skip their next turn
        turns_taken (int)  : total turns taken (skipped turns are not counted)
        snake_encounters / ladder_climbs / boost_hits / trap_hits (int)
                            : event counters for end-of-game statistics
    """

    def __init__(self, name, is_ai=False):
        self.name      = name
        self.is_ai     = is_ai
        self.position  = 0          # 0 means the player has not yet moved
        self.skip_turn = False      # set to True when landing on a trap

        # Statistics — incremented throughout the game
        self.turns_taken      = 0
        self.snake_encounters = 0
        self.ladder_climbs    = 0
        self.boost_hits       = 0
        self.trap_hits        = 0

    def initial(self):
        """Return the single-character token shown on the board (first letter)."""
        return self.name[0].upper()

    def __repr__(self):
        return f"Player(name={self.name!r}, position={self.position})"


# =============================================================================
#  MoveRecord
# =============================================================================
class MoveRecord:
    """
    Immutable record of a single player move.
    These objects are pushed onto the Game.history stack after every turn
    so the game can display a recent-moves log at the end.
    """

    def __init__(self, player_name, roll, from_pos, to_pos, event):
        self.player_name = player_name
        self.roll        = roll
        self.from_pos    = from_pos
        self.to_pos      = to_pos
        self.event       = event      # human-readable description of what happened

    def __str__(self):
        return (f"  {self.player_name}: rolled {self.roll}  "
                f"[{self.from_pos:>3} -> {self.to_pos:>3}]  {self.event}")


# =============================================================================
#  Board
# =============================================================================
class Board:
    """
    Owns all board rules and handles rendering the 10x10 grid.

    Accepts a difficulty config dict so the snake/ladder layout can change
    between Easy, Normal, and Hard without modifying any other code.

    The board uses a serpentine (boustrophedon) layout:
        Row 0 (bottom) : cells  1 – 10  left -> right
        Row 1          : cells 11 – 20  right -> left  (displayed 20..11)
        Row 2          : cells 21 – 30  left -> right
        ...
        Row 9 (top)    : cells 91 – 100 right -> left  (displayed 100..91)
    """

    # Maps raw symbol character -> ANSI color code (extra credit)
    _SYMBOL_COLORS = {
        'S': Color.RED,
        'L': Color.GREEN,
        'B': Color.CYAN,
        'T': Color.YELLOW,
    }

    def __init__(self, config):
        # Load snake/ladder dicts from the chosen difficulty config
        self.snakes  = config['snakes']
        self.ladders = config['ladders']
        self.boosts  = boosts
        self.traps   = traps

    # ── private helpers ───────────────────────────────────────────────────────

    def _raw_symbol(self, cell):
        """Plain one-character label for a special cell (no color codes)."""
        if cell in self.snakes:   return 'S'
        if cell in self.ladders:  return 'L'
        if cell in self.boosts:   return 'B'
        if cell in self.traps:    return 'T'
        return ' '

    def _colored_symbol(self, cell):
        """
        Color-coded label for display (extra credit).
        Falls back to the plain symbol when stdout is not a terminal.
        Uses _raw_symbol so color and padding calculations stay separate.
        """
        raw   = self._raw_symbol(cell)
        color = self._SYMBOL_COLORS.get(raw)
        return Color.wrap(raw, color) if color else raw

    def _row_cells(self, row):
        """
        Return cell numbers in left-to-right display order for a given row.
        Even rows go left->right; odd rows go right->left (serpentine).
        """
        if row % 2 == 0:
            return list(range(row * 10 + 1, row * 10 + 11))   # ascending
        else:
            return list(range(row * 10 + 10, row * 10, -1))   # descending

    # ── public display ────────────────────────────────────────────────────────

    def display(self, players):
        """
        Print the 10x10 board to the terminal.
        Each cell shows its number, a color-coded symbol, and any player tokens.

        Padding is calculated from raw (uncolored) symbol lengths so that ANSI
        escape codes do not break column alignment.
        """
        # Build an occupancy dict: cell number -> list of player initials
        # (Multiple players can share a cell without affecting each other)
        occupants = {}
        for p in players:
            if p.position > 0:
                occupants.setdefault(p.position, []).append(p.initial())

        divider = "+" + ("-------+" * 10)

        # Color-coded legend (extra credit)
        legend = (f"[ {Color.wrap('S', Color.RED)}=Snake "
                  f" {Color.wrap('L', Color.GREEN)}=Ladder "
                  f" {Color.wrap('B', Color.CYAN)}=Boost "
                  f" {Color.wrap('T', Color.YELLOW)}=Trap ]")

        print("\n" + "=" * 81)
        print(f"  BOARD    {legend}")
        print("=" * 81)

        # Print rows from top (row 9) to bottom (row 0)
        for row in range(9, -1, -1):
            cells = self._row_cells(row)
            print(divider)

            # Line 1: cell numbers (no color needed)
            num_line = "|"
            for c in cells:
                num_line += f"  {c:>3}  |"
            print(num_line)

            # Line 2: colored symbol + player token(s)
            sym_line = "|"
            for c in cells:
                raw_sym    = self._raw_symbol(c)       # 1 char — used for padding math
                col_sym    = self._colored_symbol(c)   # may contain ANSI escape codes
                raw_tokens = "".join(occupants.get(c, []))
                col_tokens = Color.wrap(raw_tokens, Color.BOLD) if raw_tokens else ''

                # Padding is based on visible character count, not string length,
                # so ANSI codes in col_sym / col_tokens do not break alignment.
                visible_len = len(raw_sym) + len(raw_tokens)
                padding     = " " * max(0, 5 - visible_len)

                sym_line += f" {col_sym}{col_tokens}{padding} |"
            print(sym_line)

        print(divider)
        print()

        # Player position summary beneath the grid
        for p in players:
            pos_label = f"cell {p.position}" if p.position > 0 else "Start"
            ai_tag    = " [AI]" if p.is_ai else ""
            skip_tag  = "  (TRAPPED - skips next turn)" if p.skip_turn else ""
            print(f"  [{p.initial()}] {p.name}{ai_tag}  ->  {pos_label}{skip_tag}")
        print()

    # ── board effect resolution ───────────────────────────────────────────────

    def apply_effects(self, player, cell):
        """
        Determine what happens when a player lands on a cell.

        Priority order: snake -> ladder -> boost -> trap -> normal move.
        Only ONE effect applies per move (effects do not chain).

        Returns:
            (final_position : int, event_description : str)
        """
        # Snake check: landing on a head slides the player down to the tail
        if cell in self.snakes:
            dest = self.snakes[cell]          # look up tail position in dict
            player.snake_encounters += 1
            return dest, f"SNAKE! slid from {cell} down to {dest}"

        # Ladder check: landing on the base climbs the player to the top
        if cell in self.ladders:
            dest = self.ladders[cell]         # look up top position in dict
            player.ladder_climbs += 1
            return dest, f"LADDER! climbed from {cell} up to {dest}"

        # Boost check: player advances extra spaces (cannot overshoot 100)
        if cell in self.boosts:
            extra = self.boosts[cell]         # look up bonus amount in dict
            dest  = cell + extra
            if dest > 100:                    # edge case: boost would exceed 100
                dest = cell                   # stay; same overshoot rule applies
            player.boost_hits += 1
            return dest, f"BOOST! +{extra} spaces -> moved to {dest}"

        # Trap check: player must skip their very next turn
        if cell in self.traps:               # O(1) set membership check
            player.skip_turn = True
            player.trap_hits += 1
            return cell, f"TRAP! {player.name} loses their next turn"

        # Default: plain move, no special effect
        return cell, "moved"


# =============================================================================
#  Game
# =============================================================================
class Game:
    """
    Manages a complete game session from start to finish.

    Key data structures:
        turn_queue (deque) — acts as a Queue to rotate players each round.
                             popleft() dequeues the active player in O(1);
                             append() re-enqueues them at the back in O(1).

        history    (list)  — acts as a Stack to record every move.
                             append() pushes a MoveRecord in O(1);
                             reversed slicing peeks the most recent entries.
    """

    def __init__(self, players, config):
        self.board      = Board(config)
        self.players    = players
        self.turn_queue = deque(players)   # Queue for fair turn alternation
        self.history    = []               # Stack of MoveRecord objects

    # ── dice roll ─────────────────────────────────────────────────────────────

    @staticmethod
    def roll_dice():
        """Simulate a standard six-sided dice roll."""
        return random.randint(1, 6)

    @staticmethod
    def show_dice(roll):
        """
        Display the ASCII face for the given roll value (extra credit).
        DICE_FACES is a dict of lists: key = roll (1-6), value = list of rows.
        """
        for line in DICE_FACES[roll]:   # iterate the list of strings for this face
            print(f"    {line}")
        print()

    # ── turn logic ────────────────────────────────────────────────────────────

    def take_turn(self, player):
        """
        Execute one player's turn.

        If the player is trapped (skip_turn == True), the turn is forfeited.
        Otherwise the dice is rolled, the overshoot rule is applied, and any
        board effects are resolved.

        Returns:
            MoveRecord if a move was made, None if the turn was skipped.
        """
        print(f"\n{'-' * 61}")

        # --- Handle trap: player loses this turn ---
        if player.skip_turn:
            player.skip_turn = False       # reset flag so they play next time
            print(f"  !! {player.name} is TRAPPED and loses this turn!!")
            input("     Press Enter to continue...")
            return None                    # no MoveRecord pushed for a skipped turn

        player.turns_taken += 1
        pos_label = f"cell {player.position}" if player.position > 0 else "Start"
        print(f"  {player.name}'s turn  (currently at: {pos_label})")

        # --- Wait for input (AI rolls automatically after a brief pause) ---
        if player.is_ai:
            input("  Press Enter to roll for the AI opponent...")
            time.sleep(0.4)
        else:
            input("  Press Enter to roll the dice...")

        roll    = self.roll_dice()
        old_pos = player.position
        raw_pos = old_pos + roll

        # Show the ASCII dice face for this roll (extra credit)
        self.show_dice(roll)
        print(f"  {player.name} rolled: {roll}")

        # --- Overshoot rule: must land exactly on 100 to win ---
        if raw_pos > 100:
            # Player cannot move; they stay and wait for a better roll
            event = (f"overshoot! ({old_pos} + {roll} = {raw_pos} > 100) "
                     f"-- {player.name} stays at {old_pos}")
            player.position = old_pos
            print(f"  Needs exact 100 to win! Stays at {old_pos}.")
        else:
            # Resolve any board effects (snake, ladder, boost, trap, or none)
            final, event = self.board.apply_effects(player, raw_pos)
            player.position = final
            print(f"  {event}")

        # Push this move onto the history stack
        record = MoveRecord(player.name, roll, old_pos, player.position, event)
        self.history.append(record)
        return record

    # ── statistics ────────────────────────────────────────────────────────────

    def show_stats(self, winner):
        """
        Display end-of-game statistics for all players.
        Peeks at the top 5 entries of the history stack without removing them.
        """
        total_turns = sum(p.turns_taken for p in self.players)

        print("\n" + "=" * 61)
        print("  GAME STATISTICS")
        print("=" * 61)
        print(f"  Total turns played  : {total_turns}")
        print()

        for p in self.players:
            tag = "  <-- WINNER" if p is winner else ""
            print(f"  {p.name}{tag}")
            print(f"    Turns taken       : {p.turns_taken}")
            print(f"    Snake encounters  : {p.snake_encounters}")
            print(f"    Ladder climbs     : {p.ladder_climbs}")
            print(f"    Boost cells hit   : {p.boost_hits}")
            print(f"    Trap cells hit    : {p.trap_hits}")
            print()

        # Peek top 5 of history stack (most recent first)
        print("  -- Last 5 moves (most recent first) --")
        for record in list(reversed(self.history))[:5]:
            print(record)
        print("=" * 61)

    # ── main game loop ────────────────────────────────────────────────────────

    def run(self):
        """
        Run the game from start to finish.

        Loop:
            1. Dequeue the next player from turn_queue  (Queue popleft)
            2. Execute their turn
            3. Check for a winner (position == 100)
            4. Re-enqueue the player at the back       (Queue append)
        """
        print("\n" + "=" * 61)
        print("   SNAKE & LADDER -- GAME START!")
        print("=" * 61)
        self.board.display(self.players)

        winner = None
        while winner is None:
            player = self.turn_queue.popleft()    # dequeue: get next player
            self.take_turn(player)
            self.board.display(self.players)

            # Win condition: player must reach exactly 100
            if player.position == 100:
                winner = player
                break

            self.turn_queue.append(player)        # re-enqueue: end of turn

        print(f"\n{'*' * 61}")
        print(f"  CONGRATULATIONS!  {winner.name}  WINS THE GAME!")
        print(f"{'*' * 61}")
        self.show_stats(winner)


# =============================================================================
#  Input / setup helpers  (edge-case handling)
# =============================================================================

def print_rules(config):
    """
    Display the game rules and board layout for the chosen difficulty.
    Snake/ladder positions change per difficulty, so they are read from config.
    """
    snakes_str  = ", ".join(f"{h}->{t}" for h, t in sorted(config['snakes'].items()))
    ladders_str = ", ".join(f"{b}->{t}" for b, t in sorted(config['ladders'].items()))
    print(f"""
  RULES  [{config['name']} difficulty]
  ---------------------------------------------------------
  * Roll the dice on your turn to advance your position.
  * First player to land EXACTLY on cell 100 wins.
  * Overshoot 100? You stay in your current position.
  * Land on a Snake head (S) -> slide DOWN to its tail.
  * Land on a Ladder base  (L) -> climb UP to its top.
  * Land on a Boost cell   (B) -> advance bonus spaces.
  * Land on a Trap cell    (T) -> lose your next turn.
  * Both players may occupy the same cell at once.
  ---------------------------------------------------------
  Snakes  : {snakes_str}
  Ladders : {ladders_str}
  Boosts  : 10(+5), 25(+5), 50(+5)
  Traps   : 35, 60, 75
  ---------------------------------------------------------
""")


def choose_difficulty():
    """
    Prompt the user to select a difficulty level (extra credit).
    Performs a dict lookup on DIFFICULTIES using the entered key.
    Loops until a valid choice ('1', '2', or '3') is entered.
    Edge case: any other input is rejected with a clear error message.
    """
    print("  Select difficulty:")
    for key, cfg in DIFFICULTIES.items():
        print(f"  {key}. {cfg['name']}  --  {cfg['description']}")
    while True:
        choice = input("  Enter 1, 2, or 3: ").strip()
        if choice in DIFFICULTIES:
            return DIFFICULTIES[choice]   # dict lookup returns the config dict
        # Edge case: invalid menu selection
        print("  Invalid choice. Please enter 1, 2, or 3.")


def choose_mode():
    """
    Prompt the user to select a game mode.
    Loops until a valid choice ('1' or '2') is entered.
    Edge case: any other input is rejected with a clear error message.
    """
    print("\n  Select game mode:")
    print("  1. Two-player  (both human)")
    print("  2. One-player  (you vs AI)")
    while True:
        choice = input("  Enter 1 or 2: ").strip()
        if choice == '1':
            return 1
        elif choice == '2':
            return 2
        else:
            # Edge case: invalid menu selection
            print("  Invalid choice. Please enter 1 or 2.")


def create_players(mode):
    """
    Collect player names and create Player objects.
    Edge case: empty name input defaults to a generic label so the game
    never runs with a nameless player.
    """
    if mode == 1:
        # Two human players
        name1 = input("  Enter name for Player 1: ").strip()
        name2 = input("  Enter name for Player 2: ").strip()
        name1 = name1 if name1 else "Player 1"   # default if blank
        name2 = name2 if name2 else "Player 2"
        return [Player(name1), Player(name2)]
    else:
        # One human player vs the AI
        name = input("  Enter your name: ").strip()
        name = name if name else "Player"         # default if blank
        return [Player(name), Player("Computer", is_ai=True)]


def ask_replay():
    """
    Ask whether the players want to play again.
    Loops until a clear 'y' or 'n' answer is given.
    Edge case: any other input is rejected with a clear error message.
    """
    while True:
        ans = input("\n  Play again? (y / n): ").strip().lower()
        if ans in ('y', 'yes'):
            return True
        elif ans in ('n', 'no'):
            return False
        else:
            # Edge case: invalid yes/no response
            print("  Invalid input. Please enter 'y' for yes or 'n' for no.")


# =============================================================================
#  Entry point
# =============================================================================

def main():
    """
    Program entry point.
    Selects difficulty, then loops through full game sessions until the user quits.
    """
    print("\n  SNAKE & LADDER  --  CMPSC 132 Final Project")
    while True:
        config  = choose_difficulty()        # extra credit: dict of dicts lookup
        mode    = choose_mode()
        players = create_players(mode)
        print_rules(config)

        game = Game(players, config)
        game.run()

        # Enhancement: replay option lets players start a fresh game immediately
        if not ask_replay():
            print("\n  Thanks for playing Snake & Ladder! Goodbye!\n")
            break


if __name__ == "__main__":
    main()
