output "urls" {
  description = "Addresses of the console, the API and the sign-in service."
  value       = local.urls
}

output "registry" {
  description = "Where to push the api, console and keycloak images."
  value       = local.registry
}

output "demo_passwords" {
  description = "Passwords for the realm's users in this deployment."
  value       = { for u, p in random_password.demo_user : u => p.result }
  sensitive   = true
}
