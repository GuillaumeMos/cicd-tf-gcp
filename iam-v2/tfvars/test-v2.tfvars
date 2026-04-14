project_id       = "prj-ca0001-core-prod"
region           = "europe-west9"
universe_domains = "googleapis.com"

service_account_id           = "svc-gcp-ca0001-test-v2-bis-cicd"
service_account_display_name = "SA Test V2 CI/CD"
service_account_description  = "Service account created by Terraform from GitHub Actions for test-v2."
service_account_project_roles = [
  "roles/logging.logWriter",
  "roles/monitoring.metricWriter",
  "roles/viewer",
]
