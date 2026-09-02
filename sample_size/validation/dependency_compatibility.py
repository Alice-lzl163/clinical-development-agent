"""Evidence-backed dependency qualification lookup; never infers compatibility."""

import platform
from pathlib import Path

import yaml


REGISTRY = Path(__file__).with_name("dependency_compatibility.yaml")


def classify_runtime(package: str, package_version: str, r_version: str, *, operating_system: str | None = None, architecture: str | None = None) -> str:
    document = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    os_name = operating_system or platform.system()
    machine = architecture or platform.machine()
    matching = [entry for entry in document["qualifications"] if entry["dependency"] == package and entry["version"] == package_version and entry["operating_system"] == os_name and entry["architecture"].lower() == machine.lower()]
    if not matching:
        return "UNVALIDATED_VERSION"
    entry = matching[0]
    expected_r = str(entry["runtime"]["R"])
    if not r_version.startswith(f"R version {expected_r}"):
        return "UNVALIDATED_VERSION"
    return entry["qualification_status"]
