from collections import deque
import copy
import time

class WallzEngine:
    def __init__(self, board_size=9, time_limit_sec=600, rules=None):
        self.board_size = board_size
        self.time_limit = time_limit_sec  # Default 10 mins (600s) per player
        
        # Game Mechanics Configuration
        self.rules = {
            'A': True,   # Rolling reusable walls (11th wall removes oldest)
            'B': True,   # One-time hop
            'C': True,   # Temporary cell block
            'K': 3       # Block duration in plies
        }
        if rules:
            self.rules.update(rules)
            
        self.reset()

    def reset(self):
        mid = self.board_size // 2
        self.pawns = {0: (0, mid), 1: (self.board_size - 1, mid)}
        self.goals = {0: self.board_size - 1, 1: 0}
        
        # FIFO Queues for Rolling Walls
        self.walls = {0: [], 1: []}
        
        # Abilities & Timers
        self.hop_available = {0: self.rules['B'], 1: self.rules['B']}
        self.block_available = {0: self.rules['C'], 1: self.rules['C']}
        self.blocked_cells = {} # {(r, c): remaining_turns}
        
        # Per-player remaining time in seconds
        self.time_remaining = {0: float(self.time_limit), 1: float(self.time_limit)}
        self.last_turn_timestamp = time.time()
        
        self.current_player = 0
        self.turn_count = 0
        self.winner = None
        self.is_draw = False
        
        # History tracking for N-fold repetition draw rule
        self.state_history = {}
        self._record_state_history()
        
        return self.get_state()

    def _get_state_hashable_key(self):
        """Generates a unique tuple representing complete current state for repetition checks."""
        walls_p0 = tuple(self.walls[0])
        walls_p1 = tuple(self.walls[1])
        blocks = tuple(sorted(self.blocked_cells.items()))
        return (
            self.pawns[0],
            self.pawns[1],
            walls_p0,
            walls_p1,
            self.hop_available[0],
            self.hop_available[1],
            self.block_available[0],
            self.block_available[1],
            blocks,
            self.current_player
        )

    def _record_state_history(self):
        key = self._get_state_hashable_key()
        self.state_history[key] = self.state_history.get(key, 0) + 1
        # 5-fold repetition draw rule
        if self.state_history[key] >= 5:
            self.is_draw = True

    def get_state(self):
        return {
            'pawns': copy.deepcopy(self.pawns),
            'walls': copy.deepcopy(self.walls),
            'hop_available': copy.deepcopy(self.hop_available),
            'block_available': copy.deepcopy(self.block_available),
            'blocked_cells': copy.deepcopy(self.blocked_cells),
            'current_player': self.current_player,
            'turn_count': self.turn_count,
            'time_remaining': copy.deepcopy(self.time_remaining),
            'is_draw': self.is_draw,
            'winner': self.winner
        }

    def update_clock(self):
        """Subtracts elapsed time for active player; flags loss on time if depleted."""
        now = time.time()
        elapsed = now - self.last_turn_timestamp
        self.time_remaining[self.current_player] -= elapsed
        self.last_turn_timestamp = now
        
        if self.time_remaining[self.current_player] <= 0:
            self.time_remaining[self.current_player] = 0
            self.winner = 1 - self.current_player # Opponent wins on time

    def _get_all_active_walls(self):
        return set(self.walls[0] + self.walls[1])

    def shortest_path(self, player):
        start = self.pawns[player]
        target_row = self.goals[player]
        queue = deque([(start[0], start[1], 0)])
        visited = {start}
        
        while queue:
            r, c, dist = queue.popleft()
            if r == target_row:
                return dist
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.board_size and 0 <= nc < self.board_size:
                    if (nr, nc) not in visited and not self._is_wall_blocking((r, c), (nr, nc)) and (nr, nc) not in self.blocked_cells:
                        visited.add((nr, nc))
                        queue.append((nr, nc, dist + 1))
        return float('inf')

    def _is_wall_blocking(self, cell1, cell2):
        r1, c1 = cell1
        r2, c2 = cell2
        active = self._get_all_active_walls()
        if r1 == r2:
            min_c = min(c1, c2)
            if (r1, min_c, 'V') in active or (r1 - 1, min_c, 'V') in active:
                return True
        elif c1 == c2:
            min_r = min(r1, r2)
            if (min_r, c1, 'H') in active or (min_r, c1 - 1, 'H') in active:
                return True
        return False

    def is_path_open(self, player):
        return self.shortest_path(player) < float('inf')

    def get_legal_actions(self, player=None):
        if player is None:
            player = self.current_player
        actions = []
        r, c = self.pawns[player]
        
        # 1. Standard Moves
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.board_size and 0 <= nc < self.board_size:
                if not self._is_wall_blocking((r, c), (nr, nc)) and (nr, nc) not in self.blocked_cells:
                    if (nr, nc) != self.pawns[1 - player]:
                        actions.append(('MOVE', (nr, nc)))
                        
        # 2. One-time Hop
        if self.rules['B'] and self.hop_available[player]:
            for dr, dc in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.board_size and 0 <= nc < self.board_size:
                    if (nr, nc) not in self.blocked_cells and (nr, nc) != self.pawns[1 - player]:
                        actions.append(('HOP', (nr, nc)))

        # 3. Rolling Walls
        for wr in range(self.board_size - 1):
            for wc in range(self.board_size - 1):
                for orient in ['H', 'V']:
                    if self._is_valid_wall_placement(player, wr, wc, orient):
                        actions.append(('WALL', (wr, wc, orient)))

        # 4. Temporary Cell Block
        if self.rules['C'] and self.block_available[player]:
            for br in range(self.board_size):
                for bc in range(self.board_size):
                    if (br, bc) not in self.blocked_cells and (br, bc) != self.pawns[0] and (br, bc) != self.pawns[1]:
                        actions.append(('BLOCK', (br, bc)))

        return actions

    def _is_valid_wall_placement(self, player, r, c, orient):
        active = self._get_all_active_walls()
        if (r, c, orient) in active:
            return False
        if orient == 'H' and ((r, c, 'V') in active or (r, c - 1, 'H') in active or (r, c + 1, 'H') in active):
            return False
        if orient == 'V' and ((r, c, 'H') in active or (r - 1, c, 'V') in active or (r + 1, c, 'V') in active):
            return False

        # Temporarily apply wall and drop oldest if > 10
        temp_walls = copy.deepcopy(self.walls)
        temp_walls[player].append((r, c, orient))
        if len(temp_walls[player]) > 10 and self.rules['A']:
            temp_walls[player].pop(0)
            
        old_walls = self.walls
        self.walls = temp_walls
        valid = self.is_path_open(0) and self.is_path_open(1)
        self.walls = old_walls
        return valid

    def apply_action(self, action):
        self.update_clock()
        if self.winner is not None:
            return self.get_state(), self.winner, self.is_draw

        player = self.current_player
        act_type, act_val = action
        
        if act_type == 'MOVE':
            self.pawns[player] = act_val
        elif act_type == 'HOP':
            self.pawns[player] = act_val
            self.hop_available[player] = False
        elif act_type == 'WALL':
            self.walls[player].append(act_val)
            if len(self.walls[player]) > 10 and self.rules['A']:
                self.walls[player].pop(0) # Oldest wall is removed
        elif act_type == 'BLOCK':
            self.blocked_cells[act_val] = self.rules['K']
            self.block_available[player] = False

        # Win condition check
        if self.pawns[player][0] == self.goals[player]:
            self.winner = player

        # Decrement block timers
        to_remove = []
        for cell in self.blocked_cells:
            self.blocked_cells[cell] -= 1
            if self.blocked_cells[cell] <= 0:
                to_remove.append(cell)
        for cell in to_remove:
            del self.blocked_cells[cell]

        # Check repetition rule
        self._record_state_history()

        # Turn transition
        self.current_player = 1 - self.current_player
        self.turn_count += 1
        self.last_turn_timestamp = time.time()
        
        return self.get_state(), self.winner, self.is_draw