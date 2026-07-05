from utils.checkpoint import CheckpointWriter, checkpoint_path, load_done


def test_checkpoint_path_sanitizes_website_name(tmp_path):
    path = checkpoint_path(str(tmp_path), "My Site! (prod)")
    assert path.startswith(str(tmp_path))
    assert path.endswith(".jsonl")
    assert " " not in path.split("/")[-1]


def test_load_done_returns_empty_set_when_missing(tmp_path):
    assert load_done(str(tmp_path / "nope.jsonl")) == set()


def test_writer_and_load_done_roundtrip(tmp_path):
    path = str(tmp_path / "state" / "site.jsonl")
    writer = CheckpointWriter(path)
    writer.record("alice", "pw1")
    writer.record("bob", "pw2")
    writer.close()

    done = load_done(path)
    assert done == {("alice", "pw1"), ("bob", "pw2")}


def test_load_done_ignores_malformed_lines(tmp_path):
    path = tmp_path / "site.jsonl"
    path.write_text('{"username": "alice", "password": "pw1"}\nnot json\n{"username": "bob"}\n')
    assert load_done(str(path)) == {("alice", "pw1")}


def test_writer_appends_across_instances(tmp_path):
    path = str(tmp_path / "site.jsonl")
    writer1 = CheckpointWriter(path)
    writer1.record("alice", "pw1")
    writer1.close()
    writer2 = CheckpointWriter(path)
    writer2.record("bob", "pw2")
    writer2.close()
    assert load_done(path) == {("alice", "pw1"), ("bob", "pw2")}
