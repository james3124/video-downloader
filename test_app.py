"""Tests for video downloader API endpoints."""

class TestVideoInfo:
    def test_info_missing_url(self, client):
        resp = client.post("/api/info", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_info_empty_url(self, client):
        resp = client.post("/api/info", json={"url": ""})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_info_invalid_url(self, client):
        resp = client.post("/api/info", json={"url": "http://invalid"})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data


class TestDownload:
    def test_download_missing_params(self, client):
        resp = client.post("/api/download", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_download_missing_format(self, client):
        resp = client.post("/api/download", json={"url": "https://example.com/video.mp4"})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_status_not_found(self, client):
        resp = client.get("/api/downloads/nonexistent-id")
        assert resp.status_code == 404


class TestDownloadsList:
    def test_downloads_list_empty(self, client):
        resp = client.get("/api/downloads")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "downloads" in data
        assert isinstance(data["downloads"], list)
