from urllib.parse import parse_qs

import httpx2
import pytest

from comic_helper import shopify
from comic_helper.shopify import Shopify, ShopifyError


@pytest.fixture(autouse=True)
def clean_token_cache():
    shopify._TOKENS.clear()
    yield
    shopify._TOKENS.clear()


def make(handler, **kw):
    return Shopify("test.myshopify.com", kw.pop("token", ""), "2026-07", "1",
                   transport=httpx2.MockTransport(handler), **kw)


def test_client_credentials_token_is_fetched_once_and_refreshed_on_401():
    token_calls, seen, revoked = [], [], {"t1": False}

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/admin/oauth/access_token":
            form = parse_qs(request.content.decode())
            assert form == {"grant_type": ["client_credentials"], "client_id": ["cid"], "client_secret": ["sec"]}
            token_calls.append(1)
            return httpx2.Response(200, json={"access_token": f"t{len(token_calls)}", "expires_in": 86399})
        token = request.headers["x-shopify-access-token"]
        seen.append(token)
        if revoked.get(token):
            return httpx2.Response(401, json={"errors": "revoked"})
        return httpx2.Response(200, json={"data": {"ok": True}})

    a = make(handler, client_id="cid", client_secret="sec")
    b = make(handler, client_id="cid", client_secret="sec")  # the helper builds a client per request
    assert a.gql("{ shop { name } }", {}) == {"ok": True}
    assert b.gql("{ shop { name } }", {}) == {"ok": True}
    assert len(token_calls) == 1 and seen == ["t1", "t1"]
    revoked["t1"] = True
    assert a.gql("{ shop { name } }", {}) == {"ok": True}
    assert len(token_calls) == 2 and seen[-2:] == ["t1", "t2"]


def test_static_token_is_used_as_is_without_token_request():
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path.endswith("/graphql.json")
        seen.append(request.headers["x-shopify-access-token"])
        return httpx2.Response(200, json={"data": {}})

    make(handler, token="tok").gql("{ shop { name } }", {})
    assert seen == ["tok"]


def test_token_error_does_not_leak_response_and_missing_credentials_fail():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(400, text="invalid client_secret sec")

    with pytest.raises(ShopifyError) as e:
        make(handler, client_id="cid", client_secret="sec").gql("{ shop { name } }", {})
    assert "sec" not in str(e.value).replace("secret", "")
    with pytest.raises(ShopifyError):
        make(handler, client_id="cid")
