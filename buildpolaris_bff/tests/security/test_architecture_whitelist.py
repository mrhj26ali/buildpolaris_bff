"""
Architecture test: enforce the single API boundary convention.

Every function decorated with @frappe.whitelist() must be importable
from a module path starting with `buildpolaris_bff.api.`.

This prevents convention drift (Convention B/C resurgence) in all
future phases.
"""

import importlib
import inspect
import pkgutil

import frappe
from frappe.tests.utils import FrappeTestCase

import buildpolaris_bff


class TestArchitectureWhitelistBoundary(FrappeTestCase):
    def test_all_whitelisted_functions_live_under_api_package(self):
        """
        Walk every submodule of buildpolaris_bff. For each function
        that has the `whitelisted` flag set by @frappe.whitelist(),
        assert its module starts with 'buildpolaris_bff.api'.
        """
        violations = []

        # Walk all submodules of buildpolaris_bff
        package_path = buildpolaris_bff.__path__
        prefix = buildpolaris_bff.__name__ + "."

        for importer, modname, ispkg in pkgutil.walk_packages(
            path=package_path,
            prefix=prefix,
        ):
            # Skip test modules themselves
            if ".tests." in modname:
                continue

            try:
                module = importlib.import_module(modname)
            except Exception:
                continue

            for name, obj in inspect.getmembers(module, inspect.isfunction):
                # Frappe sets `whitelisted = True` on decorated functions
                if getattr(obj, "whitelisted", False):
                    if not modname.startswith("buildpolaris_bff.api."):
                        violations.append(f"{modname}.{name}")

        self.assertEqual(
            violations,
            [],
            f"Whitelisted functions found outside buildpolaris_bff.api.*: {violations}",
        )
