project_id       = "prj-ca0001-core-prod"
region           = "europe-west9"
universe_domains = "googleapis.com"

service_account_id           = "svc-gcp-ca0001-test-cicd"
service_account_display_name = "SA Test CI/CD"
service_account_description  = "Service account created by Terraform from GitHub Actions."
service_account_project_roles = [
  "roles/logging.logWriter",
  "roles/monitoring.metricWriter"
]
