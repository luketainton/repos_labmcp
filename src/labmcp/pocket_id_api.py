"""Validated access to Pocket ID's documented JSON API operations."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote

from .clients import ServiceClient


@dataclass(frozen=True)
class PocketIDOperation:
    method: Literal["GET", "POST", "PUT", "DELETE"]
    path: str
    encoding: Literal["json", "form"] = "json"


# Generated from https://pocket-id.org/swagger.yaml. Binary image upload/download
# operations are intentionally excluded; they need an MCP attachment interface.
OPERATIONS: dict[str, PocketIDOperation] = {
    "get_json_web_key_set_jwks": PocketIDOperation("GET", "/.well-known/jwks.json"),
    "get_openid_connect_discovery_configuration": PocketIDOperation(
        "GET", "/.well-known/openid-configuration"
    ),
    "get_client_api_access": PocketIDOperation("GET", "/api/api-access/{clientId}"),
    "update_client_api_access": PocketIDOperation("PUT", "/api/api-access/{clientId}"),
    "list_api_keys": PocketIDOperation("GET", "/api/api-keys"),
    "create_api_key": PocketIDOperation("POST", "/api/api-keys"),
    "revoke_api_key": PocketIDOperation("DELETE", "/api/api-keys/{id}"),
    "renew_api_key": PocketIDOperation("POST", "/api/api-keys/{id}/renew"),
    "list_apis": PocketIDOperation("GET", "/api/apis"),
    "create_api": PocketIDOperation("POST", "/api/apis"),
    "delete_api": PocketIDOperation("DELETE", "/api/apis/{id}"),
    "get_api_by_id": PocketIDOperation("GET", "/api/apis/{id}"),
    "update_api": PocketIDOperation("PUT", "/api/apis/{id}"),
    "update_api_permissions": PocketIDOperation("PUT", "/api/apis/{id}/permissions"),
    "list_public_application_configurations": PocketIDOperation(
        "GET", "/api/application-configuration"
    ),
    "update_application_configurations": PocketIDOperation("PUT", "/api/application-configuration"),
    "list_all_application_configurations": PocketIDOperation(
        "GET", "/api/application-configuration/all"
    ),
    "synchronize_ldap": PocketIDOperation("POST", "/api/application-configuration/sync-ldap"),
    "send_test_email": PocketIDOperation("POST", "/api/application-configuration/test-email"),
    "delete_background_image": PocketIDOperation("DELETE", "/api/application-images/background"),
    "delete_default_profile_picture_image": PocketIDOperation(
        "DELETE", "/api/application-images/default-profile-picture"
    ),
    "list_audit_logs": PocketIDOperation("GET", "/api/audit-logs"),
    "list_all_audit_logs": PocketIDOperation("GET", "/api/audit-logs/all"),
    "list_client_names": PocketIDOperation("GET", "/api/audit-logs/filters/client-names"),
    "list_users_with_ids": PocketIDOperation("GET", "/api/audit-logs/filters/users"),
    "get_custom_claim_suggestions": PocketIDOperation("GET", "/api/custom-claims/suggestions"),
    "update_custom_claims_for_a_user_group": PocketIDOperation(
        "PUT", "/api/custom-claims/user-group/{userGroupId}"
    ),
    "update_custom_claims_for_a_user": PocketIDOperation(
        "PUT", "/api/custom-claims/user/{userId}"
    ),
    "list_oidc_clients": PocketIDOperation("GET", "/api/oidc/clients"),
    "create_oidc_client": PocketIDOperation("POST", "/api/oidc/clients"),
    "delete_oidc_client": PocketIDOperation("DELETE", "/api/oidc/clients/{id}"),
    "get_oidc_client": PocketIDOperation("GET", "/api/oidc/clients/{id}"),
    "update_oidc_client": PocketIDOperation("PUT", "/api/oidc/clients/{id}"),
    "update_allowed_user_groups": PocketIDOperation(
        "PUT", "/api/oidc/clients/{id}/allowed-user-groups"
    ),
    "delete_client_logo": PocketIDOperation("DELETE", "/api/oidc/clients/{id}/logo"),
    "get_client_metadata": PocketIDOperation("GET", "/api/oidc/clients/{id}/meta"),
    "preview_oidc_client_data_for_user": PocketIDOperation(
        "GET", "/api/oidc/clients/{id}/preview/{userId}"
    ),
    "get_scim_service_provider": PocketIDOperation(
        "GET", "/api/oidc/clients/{id}/scim-service-provider"
    ),
    "create_client_secret": PocketIDOperation("POST", "/api/oidc/clients/{id}/secret"),
    "introspect_oidc_tokens": PocketIDOperation("POST", "/api/oidc/introspect", "form"),
    "get_user_information": PocketIDOperation("GET", "/api/oidc/userinfo"),
    "list_authorized_clients_for_a_user": PocketIDOperation(
        "GET", "/api/oidc/users/{id}/authorized-clients"
    ),
    "list_authorized_clients_for_current_user": PocketIDOperation(
        "GET", "/api/oidc/users/me/authorized-clients"
    ),
    "revoke_authorization_for_an_oidc_client": PocketIDOperation(
        "DELETE", "/api/oidc/users/me/authorized-clients/{clientId}"
    ),
    "list_accessible_oidc_clients_for_current_user": PocketIDOperation(
        "GET", "/api/oidc/users/me/clients"
    ),
    "request_one_time_access_email": PocketIDOperation("POST", "/api/one-time-access-email"),
    "exchange_one_time_access_token": PocketIDOperation(
        "POST", "/api/one-time-access-token/{token}"
    ),
    "create_scim_service_provider": PocketIDOperation("POST", "/api/scim/service-provider"),
    "delete_scim_service_provider": PocketIDOperation("DELETE", "/api/scim/service-provider/{id}"),
    "update_scim_service_provider": PocketIDOperation("PUT", "/api/scim/service-provider/{id}"),
    "sync_scim_service_provider": PocketIDOperation(
        "POST", "/api/scim/service-provider/{id}/sync"
    ),
    "sign_up": PocketIDOperation("POST", "/api/signup"),
    "list_signup_tokens": PocketIDOperation("GET", "/api/signup-tokens"),
    "create_signup_token": PocketIDOperation("POST", "/api/signup-tokens"),
    "delete_signup_token": PocketIDOperation("DELETE", "/api/signup-tokens/{id}"),
    "sign_up_initial_admin_user": PocketIDOperation("POST", "/api/signup/setup"),
    "list_user_groups": PocketIDOperation("GET", "/api/user-groups"),
    "create_user_group": PocketIDOperation("POST", "/api/user-groups"),
    "delete_user_group": PocketIDOperation("DELETE", "/api/user-groups/{id}"),
    "get_user_group_by_id": PocketIDOperation("GET", "/api/user-groups/{id}"),
    "update_user_group": PocketIDOperation("PUT", "/api/user-groups/{id}"),
    "update_allowed_oidc_clients": PocketIDOperation(
        "PUT", "/api/user-groups/{id}/allowed-oidc-clients"
    ),
    "update_users_in_a_group": PocketIDOperation("PUT", "/api/user-groups/{id}/users"),
    "list_users": PocketIDOperation("GET", "/api/users"),
    "create_user": PocketIDOperation("POST", "/api/users"),
    "delete_user": PocketIDOperation("DELETE", "/api/users/{id}"),
    "get_user_by_id": PocketIDOperation("GET", "/api/users/{id}"),
    "update_user": PocketIDOperation("PUT", "/api/users/{id}"),
    "get_user_groups": PocketIDOperation("GET", "/api/users/{id}/groups"),
    "request_one_time_access_email_admin": PocketIDOperation(
        "POST", "/api/users/{id}/one-time-access-email"
    ),
    "create_one_time_access_token_for_user_admin": PocketIDOperation(
        "POST", "/api/users/{id}/one-time-access-token"
    ),
    "reset_user_profile_picture": PocketIDOperation("DELETE", "/api/users/{id}/profile-picture"),
    "update_user_groups": PocketIDOperation("PUT", "/api/users/{id}/user-groups"),
    "list_user_passkeys": PocketIDOperation("GET", "/api/users/{id}/webauthn-credentials"),
    "delete_user_passkey": PocketIDOperation(
        "DELETE", "/api/users/{id}/webauthn-credentials/{credentialId}"
    ),
    "get_current_user": PocketIDOperation("GET", "/api/users/me"),
    "update_current_user": PocketIDOperation("PUT", "/api/users/me"),
    "reset_current_user_s_profile_picture": PocketIDOperation(
        "DELETE", "/api/users/me/profile-picture"
    ),
    "send_email_verification": PocketIDOperation("POST", "/api/users/me/send-email-verification"),
    "verify_email": PocketIDOperation("POST", "/api/users/me/verify-email"),
    "get_current_deployed_version_of_pocket_id": PocketIDOperation("GET", "/api/version/current"),
    "get_latest_available_version_of_pocket_id": PocketIDOperation("GET", "/api/version/latest"),
    "responds_to_healthchecks": PocketIDOperation("GET", "/healthz"),
}


def list_operations() -> list[dict[str, str]]:
    """Return names and request details for supported Pocket ID API operations."""
    return [
        {"operation": name, "method": operation.method, "path": operation.path,
         "encoding": operation.encoding}
        for name, operation in sorted(OPERATIONS.items())
    ]


async def call_operation(
    client: ServiceClient,
    operation_name: str,
    *,
    path_params: Mapping[str, str] | None = None,
    query: Mapping[str, Any] | None = None,
    body: Any = None,
    form: Mapping[str, str] | None = None,
) -> Any:
    """Call one documented Pocket ID operation after validating its route."""
    operation = OPERATIONS.get(operation_name)
    if operation is None:
        raise ValueError(f"Unknown Pocket ID operation: {operation_name}")
    if body is not None and form is not None:
        raise ValueError("Provide either body or form, not both.")
    if operation.encoding == "form":
        if body is not None:
            raise ValueError(f"{operation_name} requires form data, not a JSON body.")
    elif form is not None:
        raise ValueError(f"{operation_name} requires a JSON body, not form data.")

    values = dict(path_params or {})
    required = _path_parameter_names(operation.path)
    if set(values) != required:
        raise ValueError(
            f"{operation_name} requires path_params {sorted(required)}, got {sorted(values)}."
        )
    path = operation.path
    for name, value in values.items():
        path = path.replace(f"{{{name}}}", quote(value, safe=""))
    return await client.request(
        operation.method,
        path,
        params=query,
        json=body,
        data=form,
    )


def _path_parameter_names(path: str) -> set[str]:
    return {segment[1:-1] for segment in path.split("/") if segment.startswith("{")}
