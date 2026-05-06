import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader
import smtplib


def send_email(client):
    # Initialise the html template
    env = Environment(loader=FileSystemLoader('templates'), autoescape=True)
    template = env.get_template('email_template_2025.html')
    html_email = template.render(client=client)
    # Define email & password for sender email
    with open("storage/secrets.json","r") as f:
        secrets = json.load(f)  

    wr_email = secrets["email"]
    wr_password = secrets["password"]

    # Create a message object
    msg = MIMEMultipart()
    msg['From'] = wr_email
    msg['Subject'] = f"{client['name']} Weekly Report"

    # Add the HTML body to the message
    body = MIMEText(html_email, 'html')
    msg.attach(body)

    # Send the message
    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(wr_email, wr_password)
        smtp.sendmail(wr_email, secrets["send_email"], msg.as_string())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", required=True, help="Client name as it appears in config.json")
    args = parser.parse_args()

    with open(f"storage/{args.client}_data.json", "r", encoding="utf-8") as f:
        client = json.load(f)

    with open(f"storage/{args.client}_commentary.json", "r", encoding="utf-8") as f:
        client["commentary"] = json.load(f)

    send_email(client)
    print(f"Email sent for {args.client}")
