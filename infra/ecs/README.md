# ECS Applier

The applier runs as a Fargate task because Playwright needs a full browser runtime.
For the lowest monthly cost, Terraform defaults `applier_desired_count` to `0`.
Set it to `1` when you want an always-on worker, or trigger one-off tasks from EventBridge later.

