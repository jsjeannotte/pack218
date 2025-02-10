# https://developers.google.com/gmail/api/quickstart/python

import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import base64
from email.message import EmailMessage


from pathlib import Path
home = Path.home()


# If modifying these scopes, delete the file token.json.
# SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
SECRETS_LOCATION = home / ".secrets"

def authenticate():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    token_file = str(SECRETS_LOCATION / "token.json")
    credentials_file = str(SECRETS_LOCATION / "credentials.json")
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file, SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_file, "w") as token:
            token.write(creds.to_json())
    return creds


def send_message(to: str,
                 subject: str,
                 message_text: str,
                 cc: str = None,
                 bcc: str = None,
                 is_html: bool = False,
                 subject_prefix: str = None):

    # TODO: Add support for Rich email
    subject_prefix = subject_prefix or "[Pack 218] "
    try:
        creds = authenticate()
        service = build("gmail", "v1", credentials=creds)
        message = EmailMessage()


        if is_html:
            message.add_alternative(message_text, subtype="html")
        else:
            message.set_content(message_text)

        message["To"] = to
        message["From"] = "jsjeannotte@gmail.com"
        if cc:
            message["Cc"] = cc
        if bcc:
            message["Bcc"] = bcc
        message["Subject"] = subject_prefix + subject

        # encoded message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        create_message = {"raw": encoded_message}
        # pylint: disable=E1101
        send_message = (
            service.users()
            .messages()
            .send(userId="me", body=create_message)
            .execute()
        )
        print(f'Message Id: {send_message["id"]}')
    except HttpError as error:
        print(f"An error occurred: {error}")
        send_message = None

    return send_message

def main():
    send_message(to="jsjeannotte@gmail.com,jjeannotte@netflix.com",
                 subject="Test email", message_text="test <b>email</b>: <a href='http://google/com'>Google</a>", is_html=True)

if __name__ == "__main__":
    main()