# NBA Agent

A tool for analyzing NBA statistics and data using AI.

## Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Testing

The project includes comprehensive test coverage for all NBA data tools:

### Running Tests

To run the tests:

```bash
cd backend
pytest test_tools.py -v
```

### Test Coverage

The test suite covers all NBA data tools including:
- Player information and statistics
- Team information and rosters
- Game logs and box scores
- League standings and leaders
- Draft history
- Play-by-play data

Each tool is tested for both successful scenarios and error handling.

## Team Prompt Testing

For testing team prompts and interactions:

```bash
python test_runner.py
```