provider "google" {
  project         = var.project_id
  region          = var.region
  universe_domain = var.universe_domains
}
