# AWS CloudFormation Contract

- Each stack declares account, region, purpose, owner, dependencies, exported interfaces, data retention, and deletion consequences.
- IAM and Lake Formation permissions implement the production trust boundary. A dedicated development account may grant the platform broader development authority only when the user explicitly authorizes it.
- CloudFormation templates avoid name-prefix permissions that accidentally couple future shards or resources to one current instance; permissions follow the intended resource ownership model.
- S3 lifecycle, incomplete multipart upload cleanup, object retention, versioning, and direct-user access semantics are explicit.
- KMS, Glue, Athena, Lake Formation, and cross-account policies are validated together at their real boundary.
- Cost-bearing resources have expected usage, size, lifecycle, and cleanup documented before creation.
- Validate the template and inspect the exact change set before production execution. Development execution follows the user's standing account authorization.
- Handoff reports material cloud mutations and verification without exposing credentials.
