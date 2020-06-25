import os
import sys
import io
import json
import asyncio
import concurrent.futures

# AWS supplied libs
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
# vendored libs
sys.path.insert(0, 'src/vendor')
import chess
import chess.pgn
sys.path.insert(0, 'src/lib')
import annotator
from emailer import create_email_message

SENDER = os.environ["SENDER"]
RECIPIENT = os.environ["RECIPIENT"]
REGION = os.environ["REGION"]
ANNOTATE_GAME = os.environ["ANNOTATE_GAME"]
# global client, because making new clients is apparently not threadsafe.
LAMBDA_CLIENT = boto3.client(
    'lambda',
    region_name=REGION,
    config=Config(
        read_timeout=900,               # otherwise it times out when invoking
        max_pool_connections=110,       # this might limit the concurrency of lambda execution
        retries={
            "total_max_attempts": 1,    # don't want to retry on long-lived requests - expensive.
        },
    )
)

PARAM_CLIENT = boto3.client('ssm')


def annotate_game(event, context):
    evaltime = get_parameter('/chessfunction/evaltime')
    print("evaltime:", evaltime)
    return annotator.one_game(event, evaltime)

def invoke(event):
    response = LAMBDA_CLIENT.invoke(
            FunctionName=ANNOTATE_GAME,
            InvocationType='RequestResponse',
            Payload=json.dumps(event)
        )
    string_response = response["Payload"].read().decode('utf-8')
    return json.loads(string_response)


def annotate_games(event, context):
    loop = asyncio.get_event_loop()
    games = loop.run_until_complete(main(event))
    return games


async def main(event):
    loop = asyncio.get_running_loop()
    pgnfile = io.StringIO(event)
    game_results = [
        loop.run_in_executor(
            # this limits the concurrency of lambda invocation
            concurrent.futures.ThreadPoolExecutor(max_workers=110),
            invoke,
            str(x)
        ) for x in iter(lambda: chess.pgn.read_game(pgnfile), None)
    ]
    string_results = await asyncio.gather(*game_results)
    analyzed_games = "".join(string_results)
    send_email(analyzed_games)
    return analyzed_games


def send_email(analyzed_games):
    SUBJECT = "chess analyzer"
    BODY_TEXT = "Your games are attached!"
    PGN_CONTENT = analyzed_games   
    FILENAME = "games.pgn"
    MIMETYPE = "application/x-chess-pgn"   

    client = boto3.client('ses',region_name=REGION)

    msg = create_email_message(
        SENDER,
        [RECIPIENT],
        SUBJECT,
        BODY_TEXT,
        PGN_CONTENT,
        FILENAME,
        MIMETYPE
    )

    response = client.send_raw_email(
        Source=SENDER,
        Destinations=[RECIPIENT],
        RawMessage={'Data': msg.as_string()}
    )

def get_parameter(key):
    resp = PARAM_CLIENT.get_parameter(
        Name=key,
        WithDecryption=True
    )
    return resp['Parameter']['Value']
