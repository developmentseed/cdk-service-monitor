import json
import urllib3
import os
import base64
import boto3
from botocore.exceptions import ClientError


def get_secret(secret_name: str, secret_region: str):
    """
    Gets a secret
    """
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=secret_region)

    # In this sample we only handle the specific exceptions for the 'GetSecretValue' API.
    # See https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
    # We rethrow the exception by default.

    try:
        # We need only the name of the secret
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        if e.response["Error"]["Code"] == "DecryptionFailureException":
            # Secrets Manager can't decrypt the protected secret text using the provided KMS key.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response["Error"]["Code"] == "InternalServiceErrorException":
            # An error occurred on the server side.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response["Error"]["Code"] == "InvalidParameterException":
            # You provided an invalid value for a parameter.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response["Error"]["Code"] == "InvalidRequestException":
            # You provided a parameter value that is not valid for the current state of the resource.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response["Error"]["Code"] == "ResourceNotFoundException":
            # We can't find the resource that you asked for.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        else:
            raise e
    else:
        # Decrypts secret using the associated KMS key.
        # Depending on whether the secret is a string or binary, one of these fields will be populated.
        if "SecretString" in get_secret_value_response:
            secret = get_secret_value_response["SecretString"]
            # If you have multiple secret values, you will need to json.loads(secret) here and then access the values using dict keys
            return secret
        else:
            decoded_binary_secret = base64.b64decode(
                get_secret_value_response["SecretBinary"]
            )
            return decoded_binary_secret


def handler(event, context):
    """
    Respond to EventBridge event about a service's availability.
    """
    secret_name = os.getenv("SLACK_SECRET_NAME")
    secret_region = os.getenv("SLACK_SECRET_REGION")

    if not (secret_name and secret_region):
        raise Exception("Must specify SLACK_SECRET_NAME and SLACK_SECRET_REGION")

    slack_secret = json.loads(get_secret(secret_name, secret_region))

    slack_token = slack_secret["SLACK_API_TOKEN"]
    slack_channel_id = slack_secret["SLACK_CHANNEL_ID"]

    service_name = os.environ["SERVICE_NAME"]
    service_url = os.environ["SERVICE_URL"]
    alarm_state = event["detail"]["state"]["value"]
    print(f"Alarm state: {alarm_state}")
    available = "DOWN" if alarm_state == "ALARM" else "UP"

    data = {
        "channel": slack_channel_id,
        "text": f"{service_name} at {service_url} is {available}",
    }

    http = urllib3.PoolManager()
    response = http.request(
        "POST",
        "https://slack.com/api/chat.postMessage",
        headers={
            "Content-type": "application/json;charset=UTF-8",
            "Authorization": "Bearer %s" % slack_token,
        },
        body=json.dumps(data).encode("utf-8"),
    )

    if response.status >= 400:
        raise Exception(
            f"Error sending Slack notification: {response.status} {response.data}"
        )

    data = json.loads(response.data)
    if not data["ok"]:
        raise Exception(f"Error sending Slack notification: {data['error']}")
    return {}
