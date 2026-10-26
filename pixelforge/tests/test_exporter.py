import io
import zipfile

import pytest

from pixelforge.schemas import Project
from pixelforge.services.demo import demo_project
from pixelforge.services.exporter import build_readme, build_zip, slugify
from pixelforge.utils.errors import ExportError


def names(data: bytes) -> list[str]:
    return zipfile.ZipFile(io.BytesIO(data)).namelist()


def test_zip_contains_files_and_readme():
    project = demo_project()
    data = build_zip(project)
    archive = zipfile.ZipFile(io.BytesIO(data))
    assert archive.testzip() is None
    root = slugify(project.title)
    assert sorted(names(data)) == sorted([f"{root}/{p}" for p in project.files] + [f"{root}/README.md"])
    assert archive.read(f"{root}/index.html").decode() == project.files["index.html"]


def test_readme_has_exact_run_instructions_and_warning():
    readme = build_readme(demo_project(), "my-project")
    assert "python -m http.server 8000" in readme and "cd my-project" in readme
    assert "Review and test" in readme and "`index.html`" in readme


def test_all_entries_are_relative_and_inside_folder():
    for name in names(build_zip(demo_project(), folder="../../Evil Folder!!")):
        assert not name.startswith("/") and ".." not in name and name.split("/")[0] == "evil-folder"


@pytest.mark.parametrize("bad", ["../x.html", "/abs.html", "a/../../b.js", "x.exe", "a\\b.js"])
def test_unsafe_paths_blocked_at_export(bad):
    with pytest.raises(ExportError):
        build_zip(Project(files={"index.html": "<p>x</p>", bad: "1"}))


def test_empty_project_rejected():
    with pytest.raises(ExportError):
        build_zip(Project(files={}))


def test_export_is_deterministic():
    project = demo_project()
    assert build_zip(project) == build_zip(project)


def test_edits_are_exported():
    project = demo_project()
    project.files["index.html"] = "<!DOCTYPE html><p>edited</p>\n"
    root = slugify(project.title)
    assert b"edited" in zipfile.ZipFile(io.BytesIO(build_zip(project))).read(f"{root}/index.html")


@pytest.mark.parametrize("title,expected", [("Hello World!", "hello-world"), ("", "pixelforge-project"), ("../..", "pixelforge-project"), ("A" * 100, "a" * 40)])
def test_slugify(title, expected):
    assert slugify(title) == expected
