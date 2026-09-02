from types import SimpleNamespace

from app.storage import db


def test_save_case_fills_missing_timestamps(tmp_path, monkeypatch):
    monkeypatch.setattr(
        db,
        "get_settings",
        lambda: SimpleNamespace(data_dir=tmp_path, db_path=tmp_path / "medray.sqlite3"),
    )
    db.init_db()

    db.save_case({"case_id": "case-without-timestamps", "title": "No timestamps"})
    saved = db.get_case("case-without-timestamps")

    assert saved is not None
    assert saved["created_at"]
    assert saved["updated_at"]


def test_storage_skips_corrupt_legacy_json_and_uses_runtime_default(tmp_path, monkeypatch):
    settings = SimpleNamespace(
        data_dir=tmp_path,
        db_path=tmp_path / "medray.sqlite3",
        cases_dir=tmp_path / "cases",
    )
    monkeypatch.setattr(db, "get_settings", lambda: settings)
    db.init_db()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO cases (case_id, title, image_path, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("corrupt", "Corrupt", None, "not-json", "now", "now"),
        )
        conn.execute("INSERT INTO runtime_config (id, payload) VALUES (1, ?)", ("[]",))

    assert db.get_case("corrupt") is None
    assert db.list_cases() == []
    assert db.load_runtime_config({"primary_backend": "demo"}) == {"primary_backend": "demo"}


def test_safe_case_path_cannot_escape_cases_directory(tmp_path, monkeypatch):
    settings = SimpleNamespace(
        data_dir=tmp_path,
        db_path=tmp_path / "medray.sqlite3",
        cases_dir=tmp_path / "cases",
    )
    monkeypatch.setattr(db, "get_settings", lambda: settings)

    path = db.safe_case_path("../../outside", "../image.png").resolve()

    assert path.is_relative_to(settings.cases_dir.resolve())
    assert path.name.startswith("image-")
    assert path.suffix == ".png"
    assert "/" not in db.safe_path_component("../../outside")
    assert "\\" not in db.safe_path_component("..\\outside")


def test_safe_path_components_handle_windows_device_names_and_length(tmp_path, monkeypatch):
    settings = SimpleNamespace(
        data_dir=tmp_path,
        db_path=tmp_path / "medray.sqlite3",
        cases_dir=tmp_path / "cases",
    )
    monkeypatch.setattr(db, "get_settings", lambda: settings)

    case_path = db.safe_case_path("CON", "NUL.png")
    long_component = db.safe_path_component("x" * 500, max_length=40)

    assert case_path.parent.name != "CON"
    assert case_path.name != "NUL.png"
    assert case_path.suffix == ".png"
    assert len(long_component) <= 40


def test_safe_case_path_rejects_preexisting_case_symlink(tmp_path, monkeypatch):
    settings = SimpleNamespace(
        data_dir=tmp_path,
        db_path=tmp_path / "medray.sqlite3",
        cases_dir=tmp_path / "cases",
    )
    monkeypatch.setattr(db, "get_settings", lambda: settings)
    settings.cases_dir.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (settings.cases_dir / "linked-case").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        import pytest
        pytest.skip("Symlinks are unavailable in this test environment")

    import pytest
    with pytest.raises(ValueError, match="symbolic link"):
        db.safe_case_path("linked-case", "image.png")


def test_delete_case_removes_record_and_local_directories(tmp_path, monkeypatch):
    settings = SimpleNamespace(
        data_dir=tmp_path,
        db_path=tmp_path / "medray.sqlite3",
        cases_dir=tmp_path / "cases",
        exports_dir=tmp_path / "exports",
    )
    monkeypatch.setattr(db, "get_settings", lambda: settings)
    db.init_db()
    case_dir = settings.cases_dir / "case-delete"
    export_dir = settings.exports_dir / "case-delete"
    case_dir.mkdir(parents=True)
    export_dir.mkdir(parents=True)
    (case_dir / "image.png").write_bytes(b"image")
    (export_dir / "report.json").write_text("{}", encoding="utf-8")
    db.save_case({"case_id": "case-delete", "title": "Delete me"})

    result = db.delete_case("case-delete")

    assert result["deleted"] is True
    assert db.get_case("case-delete") is None
    assert not case_dir.exists()
    assert not export_dir.exists()


def test_clear_case_database_only_removes_case_data(tmp_path, monkeypatch):
    settings = SimpleNamespace(
        data_dir=tmp_path,
        db_path=tmp_path / "medray.sqlite3",
        cases_dir=tmp_path / "cases",
        exports_dir=tmp_path / "exports",
    )
    monkeypatch.setattr(db, "get_settings", lambda: settings)
    db.init_db()
    for case_id in ("case-a", "case-b"):
        db.save_case({"case_id": case_id, "title": case_id})
        (settings.cases_dir / case_id).mkdir(parents=True)
    (settings.cases_dir / "orphan-case").mkdir(parents=True)
    (settings.exports_dir / "orphan-export").mkdir(parents=True)

    result = db.clear_case_database()

    assert result["deleted_case_count"] == 2
    assert db.list_cases() == []
    assert not (settings.cases_dir / "case-a").exists()
    assert not (settings.cases_dir / "case-b").exists()
    assert not (settings.cases_dir / "orphan-case").exists()
    assert not (settings.exports_dir / "orphan-export").exists()


def test_database_folder_change_copies_existing_sqlite_file(tmp_path, monkeypatch):
    from app import config

    current_folder = tmp_path / "current"
    target_folder = tmp_path / "new-location"
    current_folder.mkdir()
    current_db = current_folder / "medray_v2.sqlite3"
    current_db.write_bytes(b"sqlite-placeholder")
    settings = SimpleNamespace(data_dir=current_folder, db_path=current_db)
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    monkeypatch.setattr(config, "DATABASE_LOCATION_CONFIG", tmp_path / "location.json")

    result = config.set_database_folder(str(target_folder))

    assert result["restart_required"] is True
    assert result["copied_existing_database"] is True
    assert (target_folder / "medray_v2.sqlite3").read_bytes() == b"sqlite-placeholder"
    assert (tmp_path / "location.json").exists()


def test_database_folder_does_not_overwrite_existing_database(tmp_path, monkeypatch):
    from app import config

    current_folder = tmp_path / "current"
    target_folder = tmp_path / "new-location"
    current_folder.mkdir()
    target_folder.mkdir()
    current_db = current_folder / "medray_v2.sqlite3"
    current_db.write_bytes(b"current")
    (target_folder / "medray_v2.sqlite3").write_bytes(b"existing")
    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(data_dir=current_folder, db_path=current_db))
    monkeypatch.setattr(config, "DATABASE_LOCATION_CONFIG", tmp_path / "location.json")

    import pytest
    with pytest.raises(ValueError, match="already exists"):
        config.set_database_folder(str(target_folder))

    assert (target_folder / "medray_v2.sqlite3").read_bytes() == b"existing"


def test_database_location_stays_active_until_restart(tmp_path, monkeypatch):
    from app import config

    current_folder = tmp_path / "current"
    target_folder = tmp_path / "new-location"
    current_folder.mkdir()
    current_db = current_folder / "medray_v2.sqlite3"
    current_db.write_bytes(b"current")
    monkeypatch.setattr(config, "DATABASE_LOCATION_CONFIG", tmp_path / "location.json")
    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(data_dir=current_folder, db_path=current_db))

    config.set_database_folder(str(target_folder))
    info = config.database_location_info()

    assert info["database_path"] == str(current_db.resolve())
    assert info["pending_database_path"] == str((target_folder / "medray_v2.sqlite3").resolve())
    assert info["restart_required"] is True
