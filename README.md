# CDK Service Monitor

This CDK Construct provisions a Lambda function to run on an interval and make a web request to
a specified URL. If the request fails to return successfully, Lambda publishes a Custom Metric
to Cloudwatch with the provided metric name and a value of 1. The Lambda can optionally publish a
metric value of 0 on successful requests, as well, though AWS charges for each PutMetricData call, so use according to your budget.

## Usage

```python
from constructs import Construct
from cdk_service_monitor.constructs import ServiceMonitor


class MyApi(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        url: str,
        **kwargs,
    ):
        """
        Add a Service Monitor check on MyAPI service.
        """
        super().__init__(scope, id, **kwargs)

        # set up your service

        dd = ServiceMonitor(self, f"ServiceMonitor{id}", url=url, metric_name=f"{id}IsDown", publish_on_success=False)
```

## Permissions

By default, the Construct will create a Lambda function with Internet access and permission to call Cloudwatch:PutMetricData.
