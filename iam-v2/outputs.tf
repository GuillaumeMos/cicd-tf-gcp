output "service_account_email" {
  description = "Created service account email."
  value       = google_service_account.default.email
}

output "service_account_project_roles" {
  description = "Roles granted to the created service account."
  value       = sort(tolist(keys(google_project_iam_member.service_account_roles)))
}
