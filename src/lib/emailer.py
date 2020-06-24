from email.message import EmailMessage


def create_email_message(sender, recipients, subject, body,
                         attachment, file_name, mimetype):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    msg.set_content(body)
    data = attachment.encode('utf-8')  # must be bytes to specify mimeparts below
    mimeparts = mimetype.split("/")
    msg.add_attachment(
        data,
        maintype=mimeparts[0],
        subtype=mimeparts[1],
        filename=file_name
    )
    return msg