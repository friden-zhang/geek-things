import importlib.util
import tempfile
import unittest
from pathlib import Path


def load_monorepo_module():
    module_path = (
        Path(__file__).resolve().parents[1] / "tools" / "ci" / "monorepo.py"
    )
    spec = importlib.util.spec_from_file_location("monorepo_ci", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_board(repo_root: Path, name: str) -> None:
    write_file(
        repo_root / "hardware" / "boards" / name / "ato.yaml",
        "\n".join(
            [
                'requires-atopile: "^0.15.3"',
                "",
                "paths:",
                "  src: ./src",
                "  layout: ./layouts",
                "",
                "builds:",
                "  default:",
                "    entry: src/main.ato:App",
                "",
            ]
        ),
    )
    write_file(
        repo_root / "hardware" / "boards" / name / "src" / "main.ato",
        '"""Board entry"""\n\nmodule App:\n    pass\n',
    )
    write_file(
        repo_root / "hardware" / "boards" / name / "README.md",
        f"# {name}\n",
    )
    write_file(repo_root / "hardware" / "boards" / name / "layouts" / ".gitkeep", "")
    write_file(
        repo_root / "hardware" / "contracts" / f"{name}.yaml",
        f"board: {name}\n",
    )
    write_file(repo_root / "firmware" / "boards" / name / "README.md", f"# {name}\n")


def make_shared_structure(repo_root: Path) -> None:
    write_file(repo_root / "VERSION", "0.1.0\n")
    write_file(repo_root / "hardware" / "packages" / "interfaces" / "README.md", "# x\n")
    write_file(repo_root / "hardware" / "packages" / "power" / "README.md", "# x\n")
    write_file(repo_root / "hardware" / "packages" / "common" / "README.md", "# x\n")
    write_file(repo_root / "firmware" / "shared" / "README.md", "# shared\n")
    write_file(repo_root / "software" / "tools" / "README.md", "# tools\n")
    write_file(repo_root / "docs" / "architecture" / "monorepo.md", "# docs\n")
    write_file(repo_root / "tools" / "ci" / ".gitkeep", "")


class MonorepoCiTests(unittest.TestCase):
    def test_discover_boards_returns_sorted_names(self):
        module = load_monorepo_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            make_shared_structure(repo_root)
            make_board(repo_root, "beta")
            make_board(repo_root, "alpha")

            boards = module.discover_boards(repo_root)

            self.assertEqual([board.name for board in boards], ["alpha", "beta"])

    def test_validate_repo_reports_missing_contracts_and_firmware(self):
        module = load_monorepo_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            make_shared_structure(repo_root)
            write_file(
                repo_root / "hardware" / "boards" / "app" / "ato.yaml",
                'requires-atopile: "^0.15.3"\n',
            )

            errors = module.validate_repo(repo_root)

            self.assertTrue(any("hardware/contracts/app.yaml" in error for error in errors))
            self.assertTrue(any("firmware/boards/app" in error for error in errors))

    def test_validate_repo_accepts_minimal_monorepo_shape(self):
        module = load_monorepo_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            make_shared_structure(repo_root)
            make_board(repo_root, "app")

            errors = module.validate_repo(repo_root)

            self.assertEqual(errors, [])

    def test_validate_repo_reports_missing_manifest_entry_file(self):
        module = load_monorepo_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            make_shared_structure(repo_root)
            make_board(repo_root, "app")
            write_file(
                repo_root / "hardware" / "boards" / "app" / "ato.yaml",
                "\n".join(
                    [
                        'requires-atopile: "^0.15.3"',
                        "",
                        "paths:",
                        "  src: ./src",
                        "  layout: ./layouts",
                        "",
                        "builds:",
                        "  default:",
                        "    entry: main.ato:App",
                        "",
                    ]
                ),
            )

            errors = module.validate_repo(repo_root)

            self.assertTrue(any("entry file" in error for error in errors))

    def test_validate_repo_uses_default_build_entry(self):
        module = load_monorepo_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            make_shared_structure(repo_root)
            make_board(repo_root, "app")
            write_file(
                repo_root / "hardware" / "boards" / "app" / "ato.yaml",
                "\n".join(
                    [
                        'requires-atopile: "^0.15.3"',
                        "",
                        "paths:",
                        "  src: ./src",
                        "  layout: ./layouts",
                        "",
                        "builds:",
                        "  panel:",
                        "    entry: src/panel.ato:Panel",
                        "  default:",
                        "    entry: src/main.ato:App",
                        "",
                    ]
                ),
            )

            errors = module.validate_repo(repo_root)

            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
