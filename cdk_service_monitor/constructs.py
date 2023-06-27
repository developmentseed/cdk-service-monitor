import os
from typing import Optional
from constructs import Construct

from aws_cdk import (
    SecretValue,
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_events as events,
    aws_events_targets as events_targets,
    aws_secretsmanager as secretsmanager,
    Duration,
)


def generate_name(construct_id: str, name: str):
    return f"{construct_id}-{name}"


class ServiceMonitor(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        service_name: str,
        url: str,
        metric_name: str,
        metric_namespace: str,
        publish_on_success: bool = False,
        expected_header_value: Optional[dict] = None,
        expected_json_key_value: Optional[dict] = None,
        timeout: Optional[Duration] = Duration.seconds(60),
        schedule: Optional[events.Schedule] = events.Schedule.cron(minute="*"),
        slack_channel_id: Optional[str] = None,
        slack_token: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        A CDK construct for monitoring a public web service via a scheduled
        Lambda function.

        :param scope: The parent Construct
        :param id: The construct ID
        :param service_name: The name of the service being monitored. This appears in alerts.
        :param url: The URL to monitor
        :param metric_name: The name of the Cloudwatch metric
        :param metric_namespace: The namespace of the Cloudwatch metric
        :param publish_on_success: Whether to publish a metric on successful requests
        :param expected_header_value: An optional dictionary of headers to check
        :param expected_json_key_value: An optional dictionary of JSON keys to check in
                                       the response body
        :param timeout: The timeout for the Lambda function
        :param schedule: The schedule for the Lambda function
        :param slack_webhook_url: An optional Slack webhook URL to send notifications to
        :param slack_channel_id: An optional Slack channel ID to send notifications to
        :param slack_token: An optional Slack API token use when sending notifications
        """

        super().__init__(scope, id, **kwargs)

        # Cf_Update lambda function
        lambda_function = lambda_.Function(
            self,
            generate_name(id, "ServiceMonitorLambda"),
            code=lambda_.Code.from_asset(
                os.path.join(os.path.dirname(__file__), "./detector_lambda/"),
            ),
            handler="handler.handler",
            runtime=lambda_.Runtime.PYTHON_3_8,
            timeout=timeout,
        )

        lambda_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudwatch:PutMetricData",
                ],
                resources=["*"],
            )
        )

        target = events_targets.LambdaFunction(
            handler=lambda_function,
            event=events.RuleTargetInput.from_object(
                {
                    "url": url,
                    "metric_name": metric_name,
                    "metric_namespace": metric_namespace,
                    "publish_on_success": publish_on_success,
                    "expected_header_value": expected_header_value,
                    "expected_json_key_value": expected_json_key_value,
                }
            ),
        )

        events.Rule(
            self,
            generate_name(id, "ServiceMonitorRule"),
            description=f"Once per minute, trigger Service Monitor function for {url}",
            enabled=True,
            schedule=schedule,
            targets=[target],
        )

        if slack_channel_id and slack_token:
            slack_secret = secretsmanager.Secret(
                self,
                generate_name(id, "SlackSecret"),
                secret_object_value={
                    "SLACK_API_TOKEN": SecretValue.unsafe_plain_text(slack_token),
                    "SLACK_CHANNEL_ID": SecretValue.unsafe_plain_text(slack_channel_id),
                },
            )

            slack_notification_lambda = lambda_.Function(
                self,
                generate_name(id, "SlackNotificationLambda"),
                code=lambda_.Code.from_asset(
                    os.path.join(
                        os.path.dirname(__file__),
                        "./slack_notify/",
                    ),
                ),
                environment={
                    "SERVICE_NAME": service_name,
                    "SERVICE_URL": url,
                    "SLACK_SECRET_NAME": slack_secret.secret_name,
                    "SLACK_SECRET_REGION": Stack.of(self).region,
                },
                handler="handler.handler",
                runtime=lambda_.Runtime.PYTHON_3_8,
                timeout=Duration.seconds(60),
            )

            slack_secret.grant_read(slack_notification_lambda)

            alarm = cloudwatch.Alarm(
                self,
                generate_name(id, "ServiceMonitorAlarm"),
                metric=cloudwatch.Metric(
                    metric_name=metric_name,
                    namespace=metric_namespace,
                    period=Duration.minutes(1),
                    statistic=cloudwatch.Stats.MAXIMUM,
                ),
                threshold=1,
                alarm_description=f"Service Monitor alarm for {url}",
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,  # noqa: E501
                evaluation_periods=1,
                datapoints_to_alarm=1,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )

            rule = events.Rule(
                self,
                "rule",
                event_pattern=events.EventPattern(
                    account=[os.environ["CDK_DEFAULT_ACCOUNT"]],
                    region=[os.environ["CDK_DEFAULT_REGION"]],
                    source=["aws.cloudwatch"],
                    resources=[alarm.alarm_arn],
                ),
                targets=[
                    events_targets.LambdaFunction(
                        handler=slack_notification_lambda,
                        # event=events.RuleTargetInput.from_object(
                        #     {
                        #         "detail": {
                        #             "state": {
                        #                 "value": "ALARM",
                        #             },
                        #         },
                        #     }
                        # ),
                    ),
                ],
            )
