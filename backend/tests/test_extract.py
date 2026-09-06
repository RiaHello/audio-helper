import json

import httpx
import pytest
import respx

from config import settings


@pytest.fixture
def extract_client(client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test-not-real")
    return client


def mock_model(payload: dict | str):
    content = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    respx.post(settings.deepseek_api_url).mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )
    )


def test_extract_missing_fields(extract_client):
    response = extract_client.post("/extract", json={"city": "杭州"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["stage"] == "extract"


@respx.mock
def test_extract_success_returns_five_fields(extract_client):
    mock_model(
        {
            "city_a": "杭州",
            "address_a": "杭州东站",
            "city_b": "杭州",
            "address_b": "西湖龙翔桥地铁站",
            "category": "咖啡店",
            "party_count": 2,
            "incomplete_reason": None,
        }
    )
    response = extract_client.post(
        "/extract",
        json={
            "text": "我在杭州东站，朋友在西湖龙翔桥地铁站，帮我们找个中间的咖啡店。",
            "city": "杭州",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data == {
        "city_a": "杭州",
        "address_a": "杭州东站",
        "city_b": "杭州",
        "address_b": "西湖龙翔桥地铁站",
        "category": "咖啡店",
    }
    assert "party_count" not in data
    assert "incomplete_reason" not in data


@respx.mock
def test_extract_fills_page_city_and_normalizes_coffee(extract_client):
    mock_model(
        {
            "city_a": None,
            "address_a": "杭州东站",
            "city_b": None,
            "address_b": "龙翔桥地铁站",
            "category": "喝咖啡",
            "party_count": 2,
            "incomplete_reason": None,
        }
    )
    response = extract_client.post(
        "/extract",
        json={"text": "我在东站，朋友在龙翔桥，一起喝咖啡。", "city": "杭州"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["city_a"] == "杭州"
    assert data["city_b"] == "杭州"
    assert data["category"] == "咖啡店"


@respx.mock
def test_extract_same_city_with_shi_suffix(extract_client):
    mock_model(
        {
            "city_a": "杭州",
            "address_a": "杭州东站",
            "city_b": "杭州市",
            "address_b": "龙翔桥地铁站",
            "category": "咖啡店",
            "party_count": 2,
            "incomplete_reason": None,
        }
    )
    response = extract_client.post(
        "/extract",
        json={"text": "我在杭州东站，朋友在杭州市龙翔桥地铁站。", "city": "杭州"},
    )
    assert response.status_code == 200


@respx.mock
def test_extract_missing_address(extract_client):
    mock_model(
        {
            "city_a": "杭州",
            "address_a": "杭州东站",
            "city_b": "杭州",
            "address_b": None,
            "category": "咖啡店",
            "party_count": 2,
            "incomplete_reason": "missing_address",
        }
    )
    response = extract_client.post(
        "/extract",
        json={"text": "我在杭州东站，帮我找咖啡店。", "city": "杭州"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EXTRACT_INCOMPLETE"


@respx.mock
def test_extract_home_is_incomplete(extract_client):
    mock_model(
        {
            "city_a": "杭州",
            "address_a": None,
            "city_b": "杭州",
            "address_b": "龙翔桥地铁站",
            "category": "咖啡店",
            "party_count": 2,
            "incomplete_reason": "ambiguous_place",
        }
    )
    response = extract_client.post(
        "/extract",
        json={"text": "我在我家，朋友在龙翔桥地铁站，找咖啡店。", "city": "杭州"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EXTRACT_INCOMPLETE"


@respx.mock
def test_extract_party_count_invalid(extract_client):
    mock_model(
        {
            "city_a": "杭州",
            "address_a": "杭州东站",
            "city_b": "杭州",
            "address_b": "龙翔桥地铁站",
            "category": "咖啡店",
            "party_count": 3,
            "incomplete_reason": "party_count_mismatch",
        }
    )
    response = extract_client.post(
        "/extract",
        json={"text": "我们三个人分别在东站、龙翔桥和城西银泰，找咖啡店。", "city": "杭州"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PARTY_COUNT_INVALID"


@respx.mock
def test_extract_cross_city(extract_client):
    mock_model(
        {
            "city_a": "杭州",
            "address_a": "杭州东站",
            "city_b": "上海",
            "address_b": "虹桥火车站",
            "category": "咖啡店",
            "party_count": 2,
            "incomplete_reason": None,
        }
    )
    response = extract_client.post(
        "/extract",
        json={"text": "我在杭州东站，朋友在上海虹桥火车站，找咖啡店。", "city": "杭州"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CROSS_CITY"


@respx.mock
def test_extract_district_is_cross_city(extract_client):
    mock_model(
        {
            "city_a": "杭州",
            "address_a": "杭州东站",
            "city_b": "萧山",
            "address_b": "萧山国际机场",
            "category": "咖啡店",
            "party_count": 2,
            "incomplete_reason": None,
        }
    )
    response = extract_client.post(
        "/extract",
        json={"text": "我在杭州东站，朋友在萧山国际机场，找咖啡店。", "city": "杭州"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CROSS_CITY"


@respx.mock
def test_extract_invalid_json_is_model_error(extract_client):
    mock_model("not-json")
    response = extract_client.post(
        "/extract",
        json={"text": "我在杭州东站，朋友在龙翔桥。", "city": "杭州"},
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "MODEL_OUTPUT_INVALID"
    assert response.json()["error"]["stage"] == "extract"


@respx.mock
def test_extract_missing_model_field_is_model_error(extract_client):
    mock_model(
        {
            "city_a": "杭州",
            "address_a": "杭州东站",
            "city_b": "杭州",
            "address_b": "龙翔桥地铁站",
            "category": "咖啡店",
            "incomplete_reason": None,
        }
    )
    response = extract_client.post(
        "/extract",
        json={"text": "我在杭州东站，朋友在龙翔桥。", "city": "杭州"},
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "MODEL_OUTPUT_INVALID"


@respx.mock
def test_extract_timeout(extract_client):
    respx.post(settings.deepseek_api_url).mock(side_effect=httpx.TimeoutException("timeout"))
    response = extract_client.post(
        "/extract",
        json={"text": "我在杭州东站，朋友在龙翔桥。", "city": "杭州"},
    )
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"
    assert response.json()["error"]["stage"] == "extract"
