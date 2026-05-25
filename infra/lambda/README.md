# Lambda Scraper and Matcher

Scrapers are modeled as one image-based Lambda per platform with a 15 minute timeout.
The matcher Lambda is triggered from the job SQS queue and publishes qualified jobs to the apply queue.

