import smtplib
import json
import datetime
import os
from email.mime.text import MIMEText


def send_email(traceback):
    json_data = open(os.path.join(os.path.dirname(__file__), "email_config.cfg"), "r").read()
    data = json.loads(json_data)
    server = smtplib.SMTP(data['hostname'])
    server.starttls()
    server.login(data['username'], data['password'])
    message = "An error occured. Here is the traceback:\n %s" % traceback
    msg = MIMEText(message)
    msg['Subject'] = "Error in pulse_actions - Time %s" % str(datetime.datetime.now())
    msg['From'] = data['username']
    server.sendmail(msg['From'], data['sender_list'], msg.as_string())
