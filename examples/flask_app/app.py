"""
Simple Flask app demonstrating LogCost tracking

Run:
    python app.py

Then visit http://localhost:5000 a few times and check /tmp/logcost_stats.json
"""

# THE MAGIC LINE - Add this as first import
import sys
sys.path.insert(0, '../../')  # For local development
import logcost

# Rest of your app code (unchanged)
from flask import Flask
import logging

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.route("/")
def home():
    logger.info("Homepage accessed")
    return "Hello World!"


@app.route("/user/<user_id>")
def user_profile(user_id):
    logger.info("User profile accessed: %s", user_id)
    logger.debug("Loading user data for %s", user_id)
    return f"User: {user_id}"


@app.route("/expensive")
def expensive_log():
    """This route logs way too much - will show up as expensive"""
    for i in range(100):
        logger.info("Processing item %d with lots of data: %s", i, "x" * 1000)
    return "Done! Check your log costs."


if __name__ == "__main__":
    logger.info("Starting Flask app with LogCost tracking")
    app.run(debug=False)  # debug=False to avoid double-import

    # On shutdown, export stats
    stats_file = logcost.export("/tmp/logcost_flask_demo.json")
    print(f"\n✅ LogCost stats exported to: {stats_file}")
    print("Check it out to see which log statements cost the most!")
