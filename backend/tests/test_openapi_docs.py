"""The generated OpenAPI page (/docs) documents the API completely: authentication, errors, fields, parameters."""
import pytest

from app.main import app

OPERATIONS = ("get", "post", "put", "delete")
# The email webhooks have their own secrets instead of the API key
WEBHOOK_PREFIX = "/api/webhooks/"


@pytest.fixture(scope="module")
def spec():
    return app.openapi()


def _operations(spec):
    for path, item in spec["paths"].items():
        for method in OPERATIONS:
            if method in item:
                yield method.upper(), path, item[method]


def test_every_credential_is_declared_as_a_security_scheme(spec):
    schemes = spec["components"]["securitySchemes"]

    assert schemes["ApiKey"]["name"] == "X-API-Key" and schemes["ApiKey"]["in"] == "header"
    assert schemes["WebhookSignature"]["name"] == "X-Webhook-Signature"
    assert {"BrevoTokenHeader", "BrevoAltTokenHeader", "BrevoTokenQuery"} <= set(schemes)
    assert all(scheme.get("description") for scheme in schemes.values())


def test_api_routes_require_the_api_key_and_document_its_errors(spec):
    for method, path, op in _operations(spec):
        if path == "/health" or path.startswith(WEBHOOK_PREFIX):
            continue
        assert {"ApiKey": []} in op["security"], f"{method} {path} does not declare the API key"
        assert {"401", "503"} <= set(op["responses"]), f"{method} {path} does not document 401 / 503"
        names = [p["name"].lower() for p in op.get("parameters", [])]
        assert "x-api-key" not in names, f"{method} {path} still lists the key as an ordinary parameter"


def test_webhooks_document_their_own_authentication(spec):
    hmac_op = spec["paths"]["/api/webhooks/email-inbound"]["post"]
    brevo_op = spec["paths"]["/api/webhooks/email-inbound/brevo"]["post"]

    assert hmac_op["security"] == [{"WebhookSignature": []}]
    assert {tuple(s) for s in brevo_op["security"]} == {("BrevoTokenHeader",), ("BrevoAltTokenHeader",), ("BrevoTokenQuery",)}
    assert {"400", "401", "403", "404", "429", "503"} <= set(hmac_op["responses"])
    assert {"401", "429", "503"} <= set(brevo_op["responses"])


@pytest.mark.parametrize(
    "method,path,code",
    [
        ("POST", "/api/query", "429"),
        ("POST", "/api/tickets", "429"),
        ("POST", "/api/tickets/{ticket_id}/resolve", "429"),
        ("POST", "/api/knowledge/ingest", "429"),
        ("GET", "/api/tickets/{ticket_id}", "404"),
        ("GET", "/api/tickets/by-support-message/{message_id}", "404"),
        ("POST", "/api/tickets/{ticket_id}/support-card", "404"),
        ("POST", "/api/tickets/{ticket_id}/resolve", "404"),
        ("GET", "/api/crypto/{symbol}", "404"),
        ("DELETE", "/api/admin/whitelist/{user_id}", "404"),
        ("GET", "/health", "503"),
    ],
)
def test_the_errors_a_route_can_really_return_are_documented(spec, method, path, code):
    assert code in spec["paths"][path][method.lower()]["responses"]


def test_error_responses_share_the_documented_body(spec):
    for method, path, op in _operations(spec):
        for code, response in op["responses"].items():
            if code.startswith("2") or code == "422":
                continue
            ref = response["content"]["application/json"]["schema"]["$ref"]
            assert ref.endswith("/ErrorResponse"), f"{method} {path} {code}"
            assert response["description"], f"{method} {path} {code}"


def test_every_operation_says_what_it_returns_on_success(spec):
    for method, path, op in _operations(spec):
        success = [r for code, r in op["responses"].items() if code.startswith("2")]
        assert success, f"{method} {path}"
        assert "content" in success[0] and success[0]["content"]["application/json"]["schema"] != {}, f"{method} {path}"


def test_every_field_of_every_schema_is_described(spec):
    missing = [
        f"{schema}.{field}"
        for schema, body in spec["components"]["schemas"].items()
        for field, prop in body.get("properties", {}).items()
        if not (prop.get("description") or any("description" in alt for alt in prop.get("anyOf", [])) or "$ref" in prop)
    ]
    # `$ref` fields (nested models) inherit the description of the model they point to; validation-error
    # schemas come from FastAPI itself
    missing = [name for name in missing if not name.startswith(("HTTPValidationError", "ValidationError"))]
    assert not missing, missing


def test_every_parameter_is_described(spec):
    missing = [
        f"{method} {path} {p['name']}"
        for method, path, op in _operations(spec)
        for p in op.get("parameters", [])
        if not p.get("description")
    ]
    assert not missing, missing


def test_every_request_body_has_an_example_value(spec):
    for name, body in spec["components"]["schemas"].items():
        if not name.endswith("Request"):
            continue
        assert any("examples" in prop or "anyOf" in prop and any("examples" in a for a in prop["anyOf"]) or "default" in prop
                   for prop in body["properties"].values()), name


def test_tags_are_described_and_cover_every_route(spec):
    described = {tag["name"] for tag in spec["tags"] if tag.get("description")}
    used = {tag for _, _, op in _operations(spec) for tag in op["tags"]}

    assert used <= described


def test_the_description_explains_authentication_and_rate_limits(spec):
    description = spec["info"]["description"]

    assert "X-API-Key" in description and "429" in description
