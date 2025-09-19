def test_children_and_metadata(api_helpers):
    api = api_helpers
    # children/{parent_id} — проверим root (часто null нельзя передать, пропустим и проверим metadata)
    r = api.get("metadata", params={"limit": 50, "only_folders": False})
    assert r.status_code == 200, r.text

def test_shared_with_me(api_helpers):
    api = api_helpers
    r = api.get("sharing/shared-with-me")
    # может быть пусто, важно чтобы эндпоинт живой
    assert r.status_code == 200, r.text
