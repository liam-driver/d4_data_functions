from email.mime.text import MIMEText
import json
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader
from oauth2client.service_account import ServiceAccountCredentials
import smtplib


# Send email
def send_email(client):
    # Initialise the html template
    env = Environment(loader=FileSystemLoader('templates'))
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
        smtp.sendmail(wr_email, secrets["send_email_test"], msg.as_string()) 
