import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from surtr.fetch import FetchError, download_data


@pytest.fixture
def fake_github():
    """A local server standing in for GitHub's releases API. Set `release`
    to {name: bytes} to publish a "data" release in "owner/repo"."""
    state = {"release": None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            base = f"http://127.0.0.1:{self.server.server_port}"
            release = state["release"]
            if self.path == "/repos/owner/repo/releases/tags/data" and release is not None:
                assets = [
                    {"name": name, "size": len(body), "url": f"{base}/assets/{name}"}
                    for name, body in release.items()
                ]
                self.send(json.dumps({"assets": assets}).encode())
            elif self.path.startswith("/assets/") and release and self.path[8:] in release:
                self.send(release[self.path[8:]])
            else:
                self.send_response(404)
                self.end_headers()

        def send(self, body):
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield state, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def publish(state, version, tiles=2):
    meta = {
        "generated_at": version,
        "tiles": [{"url": f"fire-{version}-{i}.pmtiles"} for i in range(tiles)],
        "fire_list": f"fires-{version}.json",
    }
    state["release"] = {
        "meta.json": json.dumps(meta).encode(),
        f"fires-{version}.json": b'{"count": 0}',
        **{f"fire-{version}-{i}.pmtiles": f"tiles {version} {i}".encode() for i in range(tiles)},
    }


def test_downloads_the_published_files(fake_github, tmp_path):
    state, api = fake_github
    publish(state, "202601010000")
    download_data("owner/repo", "data", tmp_path, api=api)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "fire-202601010000-0.pmtiles",
        "fire-202601010000-1.pmtiles",
        "fires-202601010000.json",
        "meta.json",
    ]
    assert (tmp_path / "fire-202601010000-1.pmtiles").read_bytes() == b"tiles 202601010000 1"


def test_a_newer_release_replaces_the_old_files(fake_github, tmp_path):
    state, api = fake_github
    publish(state, "202601010000", tiles=3)
    download_data("owner/repo", "data", tmp_path, api=api)
    publish(state, "202602010000", tiles=2)
    download_data("owner/repo", "data", tmp_path, api=api)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == [
        "fire-202602010000-0.pmtiles",
        "fire-202602010000-1.pmtiles",
        "fires-202602010000.json",
        "meta.json",
    ]
    assert json.loads((tmp_path / "meta.json").read_text())["generated_at"] == "202602010000"


def test_no_release_says_what_to_do(fake_github, tmp_path):
    _, api = fake_github
    with pytest.raises(FetchError, match="Update data"):
        download_data("owner/repo", "data", tmp_path, api=api)
    assert not (tmp_path / "meta.json").exists()


def test_a_release_missing_files_is_refused(fake_github, tmp_path):
    state, api = fake_github
    publish(state, "202601010000")
    del state["release"]["fire-202601010000-1.pmtiles"]
    with pytest.raises(FetchError, match="missing fire-202601010000-1.pmtiles"):
        download_data("owner/repo", "data", tmp_path, api=api)
    assert not (tmp_path / "meta.json").exists()
