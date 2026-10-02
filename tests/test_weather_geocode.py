from app.weather import geocode


class _Response:
    def raise_for_status(self):
        pass

    def json(self):
        return {
            "results": [
                {
                    "name": "Hubli",
                    "latitude": 18.6429,
                    "longitude": 76.21599,
                    "country": "India",
                },
                {
                    "name": "Hubballi",
                    "latitude": 15.3647,
                    "longitude": 75.1240,
                    "country": "India",
                    "admin1": "Karnataka",
                    "timezone": "Asia/Kolkata",
                },
            ]
        }


def test_hubli_uses_qualified_hubballi_query_and_correct_candidate(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured.update(params)
        return _Response()

    monkeypatch.setattr("app.weather.requests.get", fake_get)

    result = geocode("Hubali")

    assert captured["name"] == "Hubballi, Karnataka, India"
    assert result == {
        "name": "Hubballi",
        "latitude": 15.3647,
        "longitude": 75.1240,
        "country": "India",
        "admin1": "Karnataka",
        "timezone": "Asia/Kolkata",
    }
