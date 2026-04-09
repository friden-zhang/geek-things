import importlib.util
import tempfile
import unittest
from pathlib import Path
import yaml


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
    def test_repo_discovers_esp32s3_devkit_board(self):
        module = load_monorepo_module()
        repo_root = Path(__file__).resolve().parents[1]

        boards = module.discover_boards(repo_root)

        self.assertIn("esp32s3_devkit", [board.name for board in boards])

    def test_repo_has_usb_c_power_package(self):
        repo_root = Path(__file__).resolve().parents[1]

        self.assertTrue(
            (repo_root / "hardware" / "packages" / "power" / "usb_c_5v_input.ato").is_file()
        )

    def test_repo_uses_concrete_3v3_ldo_package(self):
        repo_root = Path(__file__).resolve().parents[1]

        self.assertTrue(
            (repo_root / "hardware" / "packages" / "power" / "ap2112k_3v3_ldo.ato").is_file()
        )

        board_main = (
            repo_root / "hardware" / "boards" / "esp32s3_devkit" / "src" / "main.ato"
        ).read_text(encoding="utf-8")

        self.assertIn("Ap2112K3V3Ldo", board_main)
        self.assertNotIn("new Regulator", board_main)

    def test_repo_has_esp32s3_core_package(self):
        repo_root = Path(__file__).resolve().parents[1]

        self.assertTrue(
            (repo_root / "hardware" / "packages" / "common" / "esp32s3_module_core.ato").is_file()
        )

    def test_repo_has_esp32s3_devkit_io_package(self):
        repo_root = Path(__file__).resolve().parents[1]

        self.assertTrue(
            (repo_root / "hardware" / "packages" / "common" / "esp32s3_devkit_io.ato").is_file()
        )

    def test_repo_contract_declares_devkit_interfaces_and_gpio_usage(self):
        repo_root = Path(__file__).resolve().parents[1]
        contract_path = (
            repo_root / "hardware" / "contracts" / "esp32s3_devkit.yaml"
        )
        contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))

        self.assertEqual(contract["board"], "esp32s3_devkit")
        self.assertIn("usb", contract["interfaces"])
        self.assertIn("i2c", contract["interfaces"])
        self.assertIn("spi", contract["interfaces"])
        self.assertIn("uart0", contract["interfaces"])
        self.assertIn("occupied-gpios", contract)
        self.assertIn("status_rgb_data", contract["occupied-gpios"])
        self.assertEqual(contract["interfaces"]["usb"]["gpio-map"]["d_minus"], 19)
        self.assertEqual(contract["interfaces"]["usb"]["gpio-map"]["d_plus"], 20)
        self.assertEqual(contract["interfaces"]["i2c"]["gpio-map"]["sda"], 8)
        self.assertEqual(contract["interfaces"]["i2c"]["gpio-map"]["scl"], 9)
        self.assertEqual(contract["interfaces"]["spi"]["gpio-map"]["cs"], 10)
        self.assertEqual(contract["interfaces"]["spi"]["gpio-map"]["mosi"], 11)
        self.assertEqual(contract["interfaces"]["spi"]["gpio-map"]["sclk"], 12)
        self.assertEqual(contract["interfaces"]["spi"]["gpio-map"]["miso"], 13)
        self.assertEqual(contract["occupied-gpios"]["boot_mode"], 0)
        self.assertEqual(contract["occupied-gpios"]["user_button"], 47)
        self.assertEqual(contract["occupied-gpios"]["status_rgb_data"], 48)

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

    def test_build_board_passes_frozen_flag_to_ato(self):
        module = load_monorepo_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            make_shared_structure(repo_root)
            make_board(repo_root, "esp32s3_devkit")
            calls: list[tuple[list[str], Path, bool]] = []

            def fake_run(cmd, cwd, check):
                calls.append((cmd, cwd, check))

                class Result:
                    returncode = 0

                return Result()

            original_run = module.subprocess.run
            module.subprocess.run = fake_run
            try:
                exit_code = module.build_board(repo_root, "esp32s3_devkit", frozen=True)
            finally:
                module.subprocess.run = original_run

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                calls,
                [
                    (
                        ["ato", "build", "--frozen"],
                        repo_root / "hardware" / "boards" / "esp32s3_devkit",
                        False,
                    )
                ],
            )


if __name__ == "__main__":
    unittest.main()
