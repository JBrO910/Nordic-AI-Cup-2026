import pygame
import random
import sys
from src.core import SimulationCore
from evaluate import load_policy, DEFAULT_POLICY

def local_simulation(verbose=True, policy=DEFAULT_POLICY, seed=None):
    """policy: 'module:Class' (see evaluate.py), e.g. src.utils.controllers.dummy_agent_policy:dummy"""
    if seed is None: # If no seed is provided, generate a random one
        seed = random.randint(0, 2**32 - 1)

    sim = SimulationCore(seed=seed)
    decide = load_policy(policy, seed)

    pygame.init()
    screen, clock = None, None

    # Optional render
    if verbose:
        info = pygame.display.Info()
        env_ratio = sim.env_width / sim.env_height
        screen_height = int(info.current_h * 0.9) # 90% of screen height
        screen_width = int(screen_height * env_ratio) # Keep aspect ratio
        screen = pygame.display.set_mode((screen_width, int(screen_height)), pygame.SCALED)
        clock = pygame.time.Clock()

    running = True
    actions = []

    while running:
        if verbose: 
            for event in pygame.event.get():
                if event.type == pygame.QUIT: # Check if user closes window
                    running = False

        state = sim.step(actions)
        actions = decide(state)

        if verbose:
            sim.env.draw(screen)
            font = pygame.font.SysFont(None, 24)
            img = font.render(f'Score: {state["score"]:.2f}', True, (255,255,255))
            screen.blit(img, (20, 20))
            pygame.display.flip()
            clock.tick(60) # Control max FPS

        print(f'Score: {state["score"]:.2f} | Agents alive: {state["num_agents"]:.0f} | Time: {sim.env.time:.2f}')

        if state["num_agents"] == 0 or sim.env.time > 3000:
            print(f"Game over! Final Score: {state['score']}")
            print(f"Seed: {seed}")
            running = False

    pygame.quit()

if __name__ == "__main__":
    # python local_playground.py [module:Class] [seed]
    local_simulation(verbose=True, policy=sys.argv[1] if len(sys.argv) > 1 else DEFAULT_POLICY,
                     seed=int(sys.argv[2]) if len(sys.argv) > 2 else None)
