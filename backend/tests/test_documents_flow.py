import time

def _find_folder_id_by_name(api, folder_name: str) -> int | None:
    # используем метаданные-список с фильтром only_folders=true
    r = api.get("metadata", params={"only_folders": True, "limit": 500})
    assert r.status_code == 200, r.text
    data = r.json()
    # Ответ может быть просто списком или объектом — обрабатываем оба случая
    items = data if isinstance(data, list) else data.get("documents") or data.get("response") or data
    if not isinstance(items, list):
        return None
    for d in items:
        if (d.get("file_type") == "folder" or d.get("type") == "folder") and d.get("name") == folder_name:
            return d.get("id")
    return None

def _first_result_id(upload_response_json) -> int:
    data = upload_response_json
    if isinstance(data, dict) and "results" in data and data["results"]:
        item = data["results"][0]
        return item.get("id") or item.get("document_id") or item.get("doc_id")
    raise AssertionError(f"cannot extract id from upload response: {data}")

def test_full_flow_upload_move_trash_restore_delete(api_helpers, unique_names):
    api = api_helpers
    fname = unique_names["file"]
    folder = unique_names["folder"]

    # 1) Upload файл в корень
    files = [("files", (fname, b"Hello EDMS!", "text/plain"))]
    r = api.post("upload", files=files)
    assert r.status_code in (201, 200), r.text
    file_id = _first_result_id(r.json())

    # 2) Создать папку "folder" — дешёвый способ:
    #    грузим любой файл в неё (бэкенд создаст запись папки)
    files2 = [("files", ("placeholder.txt", b"x", "text/plain"))]
    r2 = api.post("upload", params={"folder": folder}, files=files2)
    assert r2.status_code in (201, 200), r2.text
    # найдём id папки через metadata
    time.sleep(0.2)  # на всякий случай
    dest_folder_id = _find_folder_id_by_name(api, folder)
    assert dest_folder_id, f"dest folder not found by name '{folder}'"

    # 3) Move файла в папку (POST /v2/{document_id}/move)
    body = {"target_parent_id": dest_folder_id}
    r3 = api.post(f"{file_id}/move", json=body)
    assert r3.status_code == 200, r3.text
    moved = r3.json()
    assert moved.get("parent_id") == dest_folder_id, moved

    # 4) Скачивание по id (GET /v2/file/{file_id}/download) — просто проверим 200
    r4 = api.get(f"file/{file_id}/download")
    assert r4.status_code == 200, r4.text

    # 5) Удаление в корзину (DELETE /v2/{file_name})
    r5 = api.delete(fname)
    assert r5.status_code == 204, r5.text

    # 6) Список корзины (GET /v2/trash) — проверим, что наш файл там
    r6 = api.get("trash")
    assert r6.status_code == 200, r6.text
    trash = r6.json()
    items = trash.get("response") if isinstance(trash, dict) else trash
    assert any((it.get("name") == fname or it.get("file_name") == fname) for it in items), trash

    # 7) Восстановление (POST /v2/restore/{file})
    r7 = api.post(f"restore/{fname}")
    assert r7.status_code == 200, r7.text

    # 8) Снова удалить в корзину
    r8 = api.delete(fname)
    assert r8.status_code == 204, r8.text

    # 9) Перманентное удаление (DELETE /v2/trash/{file_name})
    r9 = api.delete(f"trash/{fname}")
    assert r9.status_code == 204, r9.text
