import httpx
import pytest

from arxiv_title.sources.arxiv_api import ArxivAPIError, fetch_titles, parse_feed

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>arXiv Query: id_list=2101.05536v1</title>
  <entry>
    <id>http://arxiv.org/abs/2101.05536v1</id>
    <title>Scaling Equilibrium Propagation to Deep ConvNets by
  Drastically Reducing its Gradient Estimator Bias</title>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2606.32026v1</id>
    <title>AdaJEPA: An Adaptive Latent World Model</title>
  </entry>
</feed>
"""

ERROR_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/api/errors#incorrect_id_format</id>
    <title>Error</title>
  </entry>
</feed>
"""


def test_parse_feed_keys_by_bare_id():
    titles = parse_feed(FEED)
    assert set(titles) == {"2101.05536", "2606.32026"}
    assert titles["2606.32026"] == "AdaJEPA: An Adaptive Latent World Model"


def test_parse_feed_preserves_wrapped_title_text():
    # Unwrapping is slugify's job; the parser must not lose the tail of the title.
    assert "Gradient Estimator Bias" in parse_feed(FEED)["2101.05536"]


def test_parse_feed_skips_error_entries():
    assert parse_feed(ERROR_FEED) == {}


def test_parse_feed_rejects_garbage():
    with pytest.raises(ArxivAPIError):
        parse_feed("<not xml")


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_titles_issues_one_request_for_many_ids():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, text=FEED)

    with _client(handler) as client:
        fetch_titles(["2101.05536v1", "2606.32026v1"], client=client)

    assert len(calls) == 1
    assert calls[0].url.params["id_list"] == "2101.05536,2606.32026"


def test_fetch_titles_deduplicates_versions_of_the_same_paper():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, text=FEED)

    with _client(handler) as client:
        fetch_titles(["2101.05536v1", "2101.05536v2"], client=client)

    assert calls[0].url.params["id_list"] == "2101.05536"


def test_fetch_titles_empty_input_makes_no_request():
    def handler(request):  # pragma: no cover - must never run
        raise AssertionError("no request expected")

    with _client(handler) as client:
        assert fetch_titles([], client=client) == {}


def test_fetch_titles_raises_on_http_error():
    def handler(request):
        return httpx.Response(503)

    with _client(handler) as client, pytest.raises(ArxivAPIError):
        fetch_titles(["2101.05536v1"], client=client)
