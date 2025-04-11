import logging
from ..logging_config import setup_logging
from ..test_runner import run_team_prompt, print_summary
import time
import random

logger = setup_logging(level=logging.DEBUG)  # Set to DEBUG level to see everything

def run_test_group(prompts, group_name):
    """Run a group of related tests with delays between them."""
    logger.info(f"\n=== Running {group_name} Tests ===")
    results = []
    for i, prompt in enumerate(prompts, 1):
        logger.info(f"Running test {i}/{len(prompts)} in {group_name}")
        result = run_team_prompt(prompt)
        results.append(result)
        if i < len(prompts):  # Don't delay after the last test in the group
            delay = random.uniform(1.0, 2.0)  # Random delay between 1-2 seconds
            time.sleep(delay)
    return results

if __name__ == "__main__":
    logger.info("=== Starting NBA Analysis Team Tests ===")

    # Group tests by category
    test_groups = {
        # "Basic Player Info": [
            # "Give me a summary of Stephen Curry's basic info and headline stats.",
            # "What are LeBron James' career statistics?",
            # "Show me Nikola Jokić's passing stats for the 2022-23 season.",
        # ],
        # "Team Stats": [
            # "Get the Lakers' team passing statistics for the 2022-23 season.",
            # "Show me each of the Warrior's individual shooting stats for last season. Go through each player on the roster.",
            # "What are the Celtics' rebounding numbers for 2022-23?",
        # ],
        "Game Analysis": [
            # "Find games where the Lakers played against the Warriors this season.",
            # "Get the box score for the most recent Lakers vs Celtics game.",
            # "Show me the play-by-play data for the last Nuggets vs Heat game.",
        ],
        "League Analysis": [
            "What are the current league standings?",
            # "Show me today's NBA scoreboard.",
            # "Who are the league leaders in assists this season?",
        ],
        # "Advanced Stats": [
        #     "Compare the clutch stats of Luka Dončić and Devin Booker.",
        #     "Show me Joel Embiid's shooting stats by distance.",
        #     "Get Giannis Antetokounmpo's rebounding stats breakdown.",
        # ],
        # "Historical Data": [
        #     "Who were the top picks in the 2023 NBA draft?",
        #     "What awards has Kevin Durant won in his career?",
        #     "Show me the Lakers' roster changes from last season to this season.",
        # ],
        # "Error Cases": [
        #     "Can you get info for Player XYZ?",
        #     "What's the weather like in Los Angeles?",
        #     "Show me stats for the 1899-00 season.",
        # ],
        # "Complex Queries": [
        #     "Compare the passing efficiency of Jokić, LeBron, and Trae Young this season.",
        #     "Analyze the Warriors' three-point shooting before and after the All-Star break.",
        #     "Show me which teams have the best clutch performance this season.",
        # ]
    }

    # Run each group with delays between groups
    for group_name, prompts in test_groups.items():
        run_test_group(prompts, group_name)
        if group_name != list(test_groups.keys())[-1]:  # Don't delay after the last group
            delay = random.uniform(2.0, 3.0)  # Random delay between 2-3 seconds between groups
            time.sleep(delay)

    print_summary()
    logger.info("=== NBA Analysis Team Tests Complete ===")