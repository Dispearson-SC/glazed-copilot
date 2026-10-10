from conftest import CASE

STORES = [
    {"store_id": "S001", "name": "Food Court – Full Counter 1", "site_name": "Harborview International Airport",
     "display_name": "Harborview International Airport · Food Court – Full Counter 1", "format": "Full", "site_id": "ST01",
     "region": "Northeast"},
    {"store_id": "S002", "name": "Food Court – Full Counter 1", "site_name": "Bayfront Municipal Airport",
     "display_name": "Bayfront Municipal Airport · Food Court – Full Counter 1", "format": "Full", "site_id": "ST12",
     "region": "Southeast"},
    {"store_id": "S003", "name": "Food Court – Full Counter 2", "site_name": "Harborview International Airport",
     "display_name": "Harborview International Airport · Food Court – Full Counter 2", "format": "Full", "site_id": "ST01",
     "region": "Northeast"},
]
NAMED = {**CASE, "store_id": "S001", "store_display_name": STORES[0]["display_name"]}


def test_stores_table_shows_display_name(api, run):
    api.on("GET", "/api/v1/stores", STORES)
    r = run("stores")
    assert r.exit_code == 0 and "Harborview International Airport" in r.output


def test_store_code_is_used_as_is_without_lookup(api, run):
    api.on("POST", "/api/v1/cases", NAMED)
    assert run("case", "new", "--store", "s001", "--date", "2026-03-10").exit_code == 0
    assert api.last_json()["store_id"] == "S001"
    assert all(c.url.path != "/api/v1/stores" for c in api.calls)


def test_partial_name_resolves_to_the_unique_store(api, run):
    api.on("GET", "/api/v1/stores", STORES)
    api.on("POST", "/api/v1/cases", NAMED)
    r = run("case", "new", "--store", "harborview food court 1", "--date", "2026-03-10")
    assert r.exit_code == 0, r.output
    assert api.last_json()["store_id"] == "S001"
    assert "Harborview International Airport" in r.output  # announced by name


def test_ambiguous_name_lists_matches_and_never_guesses(api, run):
    api.on("GET", "/api/v1/stores", STORES)
    r = run("case", "new", "--store", "food court", "--date", "2026-03-10")
    assert r.exit_code == 1
    assert "more specific" in r.output and "S001" in r.output and "S002" in r.output and "S003" in r.output
    assert all(c.method != "POST" for c in api.calls)


def test_unknown_name_is_reported(api, run):
    api.on("GET", "/api/v1/stores", STORES)
    r = run("alerts", "--store", "narnia")
    assert r.exit_code == 1 and "No store matches" in r.output


def test_alerts_and_cases_show_store_display_name(api, run):
    name = STORES[0]["display_name"]
    api.on("GET", "/api/v1/alerts", [{"alert_id": "a1", "alert_type": 1, "store_id": "S001",
                                       "store_display_name": name, "severity_usd": 5, "state": "nueva",
                                       "as_of": "2026-03-10", "issue_key": "k"}])
    assert "Harborview International Airport" in run("alerts").output
    api.on("GET", "/api/v1/cases", [NAMED])
    assert "Harborview International Airport" in run("case", "list").output
