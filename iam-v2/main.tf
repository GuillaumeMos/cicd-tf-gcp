resource "google_service_account" "default" {
  project      = var.project_id
  account_id   = var.service_account_id
  display_name = var.service_account_display_name
  description  = var.service_account_description
}

resource "google_project_iam_member" "service_account_roles" {
  for_each = toset(var.service_account_project_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.default.email}"
}
