# test_cicd

Mini stack Terraform de test pour GitHub Actions et GCP.

Elle crée :

- un service account
- des bindings IAM projet pour ce service account

## Prerequisites

- un bucket GCS pour le backend Terraform
- un service account GCP utilisable par GitHub Actions via OIDC
- les secrets GitHub suivants :
  - `GCP_WORKLOAD_IDENTITY_PROVIDER`
  - `GCP_SERVICE_ACCOUNT`

## Usage local

```bash
task plan ENV=test
task apply ENV=test
```

## Fichiers à adapter

- `tfvars/test.tfvars`
- `backend-vars/test.tfvars`
- `.github/workflows/terraform.yml`
