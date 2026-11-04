# RIS-R08-SECURITY-06F — Infrastructure/IAM Review

WorkItems retains primary key `workId`; fence records use the same table and
the existing table ARN. Lambda WorkItems IAM includes `TransactWriteItems` and
the corrected `${table_arn}/index/*` resource. Terraform fmt and offline
validate passed with provider deprecation warnings.

This proves source configuration only. It does not prove deployment, live IAM,
table migration, PITR, queue redrive, or production feature activation.
No foreign project, Cognito, CloudFront, DNS, ACM, Jobsearch, or Mays-Orders
change was made.
