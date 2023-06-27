import json
from typing import Optional
import urllib3


def put_metric(metric_name: str, metric_namespace: str, value: int):
    import boto3

    client = boto3.client("cloudwatch")
    client.put_metric_data(
        Namespace=metric_namespace,
        MetricData=[
            {
                "MetricName": metric_name,
                "Value": value,
                "Unit": "Count",
            },
        ],
    )


def handler(event, context):
    """
    The Lambda function handler

    :param event: The event data
    :param context: The context data
    """
    url = event["url"]
    metric_name = event["metric_name"]
    metric_namespace = event["metric_namespace"]
    publish_on_success = event["publish_on_success"]
    expected_json_key_value: Optional[dict] = event.get("expected_json_key_value")
    expected_header_value: Optional[dict] = event.get("expected_header_value")

    try:
        http = urllib3.PoolManager()
        response = http.request("GET", url)
    except urllib3.exceptions.HTTPError as e:
        print(f"Error requesting {url}: {e}")
        put_metric(metric_name, metric_namespace, 1)
    else:
        if response.status >= 400:
            print(f"Error requesting {url}: {response.status}")
            put_metric(metric_name, metric_namespace, 1)
            return
        else:
            print(f"Successfully requested {url}")
            if expected_json_key_value:
                try:
                    json_body = json.loads(response.data.decode("utf-8"))
                except (UnicodeDecodeError, json.decoder.JSONDecodeError) as e:
                    print(f"Error decoding JSON response: {e}")
                    put_metric(metric_name, metric_namespace, 1)
                    return
                else:
                    for key, value in expected_json_key_value.items():
                        if json_body[key] != value:
                            print(
                                f"Expected JSON key {key} to have value {value}, but it was {json_body[key]}"  # noqa: E501
                            )
                            put_metric(metric_name, metric_namespace, 1)
                            return
            if expected_header_value:
                for key, value in expected_header_value.items():
                    if response.headers[key] != value:
                        print(
                            f"Expected header {key} to have value {value}, but it was {response.headers[key]}"  # noqa: E501
                        )
                        put_metric(metric_name, metric_namespace, 1)
                        return

            if publish_on_success:
                put_metric(metric_name, metric_namespace, 0)
