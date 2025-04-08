from logging_config import setup_logging
from test_runner import run_team_prompt, print_summary

logger = setup_logging()

if __name__ == "__main__":
    logger.info("--- Running NBA Analysis Team Tests ---")

    prompts = [
        "Give me a summary of Stephen Curry's basic info and headline stats.",
        "Analyze LeBron James' game log for the 2023-24 regular season.",
        "Compare Kevin Durant's per-game career stats to his totals.",
        "Provide an overview of the Lakers 2023-24 season based on their roster and common info.",
        "Find the games played by the Lakers this season and summarize their record.",
        "Can you get info for Player XYZ?",
        "What is the weather like in Los Angeles?"
    ]

    for prompt in prompts:
        run_team_prompt(prompt)

    print_summary()
    logger.info("--- NBA Analysis Team Tests Complete ---")