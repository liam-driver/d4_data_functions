import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from datetime import datetime
from core.error_logger import log_error
from core.generate_commentary import generate_weekly_commentary
from weekly_reports.fetch_data import fetch_client_data
from send_email import send_email


def main():
    with open("storage/config.json", "r") as f:
        clients = json.load(f)

    for config in clients:
        if config['report_due_date'] != datetime.today().strftime("%A"):
            continue
        print(config['name'])

        try:
            client = fetch_client_data(config)
        except:
            log_error(f"{config['name']} Report Skipped: misconfigured Paid Data")
            continue

        try:
            client['commentary'] = generate_weekly_commentary(client)
        except:
            log_error(f"{config['name']} Report Skipped: misconfigured Commentary")
            continue

        try:
            send_email(client)
        except:
            log_error(f"{config['name']} Report Skipped: Error Sending Email")
            continue

    return 0


main()
