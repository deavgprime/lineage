# The realm for the deployment: the local realm's roles, groups, scopes and users, with the
# console's real address, no password grant, and random passwords.
locals {
  local_realm = jsondecode(file("${path.module}/../keycloak/lineage-realm.json"))
  demo_users  = [for u in local.local_realm.users : u.username]

  realm = jsonencode(merge(local.local_realm, {
    sslRequired = "all"
    clients = [for c in local.local_realm.clients :
      c.clientId == "lineage-console" ? merge(c, {
        directAccessGrantsEnabled = false
        redirectUris              = ["${local.urls.console}/*"]
        webOrigins                = [local.urls.console]
        attributes = merge(c.attributes, {
          "post.logout.redirect.uris" = "${local.urls.console}/*"
        })
      }) : c
    ]
    users = [for u in local.local_realm.users : merge(u, {
      credentials = [{
        type      = "password"
        value     = random_password.demo_user[u.username].result
        temporary = false
      }]
    })]
  }))
}
