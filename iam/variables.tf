variable "project_id" {
  description = "GCP project id where the service account will be created."
  type        = string
}

variable "region" {
  description = "Default GCP region."
  type        = string
}

variable "universe_domains" {
  description = "Google Cloud universe domain for the provider."
  type        = string
  default     = "googleapis.com"
}

variable "service_account_id" {
  description = "Service account id."
  type        = string
}

variable "service_account_display_name" {
  description = "Service account display name."
  type        = string
  default     = "Terraform test CI/CD"
}

variable "service_account_description" {
  description = "Service account description."
  type        = string
  default     = "Terraform-managed service account for GitHub Actions tests."
}

variable "service_account_project_roles" {
  description = "Project roles to grant to the service account."
  type        = list(string)
  default = [
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter"
  ]
}
