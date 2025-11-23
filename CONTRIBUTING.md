# Contributing to LogCost

Thanks for helping improve LogCost! Here's how to get started:

1. **Install deps**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e . -r requirements-dev.txt  # optional if you add extra tools
   ```

2. **Run tests**
   ```bash
   pytest
   ```

3. **Coding style**
   - Keep code Python 3.9+ compatible.
   - Add unit tests for new features/bugfixes.
   - Default to ASCII; avoid heavy dependencies.

4. **Pull Requests**
   - Describe motivation and testing steps.
   - Link issues when applicable.
   - Expect CI (pytest) to run; keep commits focused.

Questions? Open a GitHub issue or discussion. Thank you!
