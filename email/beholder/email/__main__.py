import json
import socket

import click

from .common import mj_connect, _log, setup_logging

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def get_host():
    return f"http://{get_ip()}:{5000}"


MESSAGE = """Hello,

Your learner's recording device just turned on.
You can manage its settings at {host}.
This can only be accessed on your home's local network.

All the best,
Jack
"""

def recipient():
    with open("/srv/beholder_configuration/config.json", "r") as f:
        data = json.load(f)
    return data["email"]

def construct_email_data(recipient):
    return {
        'Messages': [
            {
                "From": {
                    "Email": "jack@dialogdog.com",
                    "Name": "Jack Terwilliger @ Theycantalk"
                },
                "To": [
                    {
                        "Email": recipient,
                        "Name": "You"
                    }
                ],
                "Subject": "Theycantalk learner's recording device",
                "TextPart": MESSAGE.format(host=get_host())
            }
        ]
    }

def send_email(mjclient):
    data = construct_email_data(recipient())
    mjclient.send.create(data=data)

@click.command()
@click.argument("mjcred", type=click.Path(exists=True))
def main(mjcred):
    setup_logging()
    mjclient = mj_connect(mjcred)
    if mjclient is not None:
        send_email(mjclient)
    else:
        _log().error("Could not connect to postgres or mailjet")


if __name__ == "__main__":
    main()
