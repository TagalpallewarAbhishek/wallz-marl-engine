from wallz_engine import WallzEngine
from greedy_agent import GreedyAgent

def run_match():
    # Initialize engine with all 3 mechanics enabled (Configuration A + B + C)
    engine = WallzEngine(board_size=9, time_limit_sec=600, rules={'A': True, 'B': True, 'C': True, 'K': 3})
    
    agent0 = GreedyAgent(player_id=0)
    agent1 = GreedyAgent(player_id=1)
    agents = {0: agent0, 1: agent1}

    print("--- Starting Headless Match: Greedy vs Greedy ---")
    
    max_steps = 200
    while engine.winner is None and not engine.is_draw and engine.turn_count < max_steps:
        current_p = engine.current_player
        action = agents[current_p].select_action(engine)
        
        if action is None:
            print(f"Player {current_p} has no legal actions available!")
            break
            
        state, winner, is_draw = engine.apply_action(action)
        print(f"Turn {engine.turn_count:03d} | Player {current_p} executed {action[0]} -> {action[1]}")

    print("\n--- Match Summary ---")
    if engine.winner is not None:
        print(f"Result: WINNER -> Player {engine.winner} in {engine.turn_count} turns!")
    elif engine.is_draw:
        print(f"Result: DRAW -> 5-Fold State Repetition reached at turn {engine.turn_count}.")
    else:
        print(f"Result: TRUNCATED -> Reached T_max = {max_steps} steps without a winner.")

if __name__ == "__main__":
    run_match()