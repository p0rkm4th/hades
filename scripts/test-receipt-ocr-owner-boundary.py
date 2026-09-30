#!/usr/bin/env python3
"""Prove receipt endpoints reject household identities before processing input."""

from __future__ import annotations

import ast
import asyncio
import os
from pathlib import Path


class FakeApp:
    def __init__(self):
        self.routes = {}

    def post(self, path):
        return lambda function: self.routes.setdefault(path, function)

    def get(self, path):
        return lambda function: self.routes.setdefault(path, function)


class FakeHTTPException(Exception):
    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class FakeJSONResponse:
    def __init__(self, value, status_code=200):
        self.value = value
        self.status_code = status_code


class GuardedRequest:
    async def form(self, **_kwargs):
        raise AssertionError("preview parsed upload before the owner gate")

    async def json(self):
        raise AssertionError("apply parsed confirmation before the owner gate")


def load_routes():
    tree = ast.parse(Path("webui/receipt_upload_compat.py").read_text(encoding="utf-8"))
    route = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "ROUTE" for target in node.targets)
    )
    app = FakeApp()
    namespace = {
        "app": app,
        "Request": object,
        "Depends": lambda value: value,
        "get_verified_user": lambda: None,
        "HTTPException": FakeHTTPException,
        "JSONResponse": FakeJSONResponse,
    }
    exec(compile(route, "receipt-owner-boundary-fixture", "exec"), namespace)
    return app.routes


async def expect_denied(route, user, expected_detail):
    try:
        await route(GuardedRequest(), user)
    except FakeHTTPException as error:
        assert error.status_code == 403, (error.status_code, error.detail)
        assert error.detail == expected_detail, error.detail
    else:
        raise AssertionError("receipt endpoint accepted a non-owner identity")


async def expect_owner_reaches_input_validation(route, user, request, expected_detail):
    try:
        await route(request, user)
    except FakeHTTPException as error:
        assert error.status_code == 400, (error.status_code, error.detail)
        assert error.detail == expected_detail, error.detail
    else:
        raise AssertionError("invalid synthetic request unexpectedly passed validation")


class EmptyPreviewRequest:
    async def form(self, **_kwargs):
        return {}


class UnconfirmedApplyRequest:
    async def json(self):
        return {"confirm": False}


async def main():
    os.environ["HADES_RECEIPT_OWNER_USER_ID"] = "synthetic-alpha"
    os.environ.pop("HADES_ACCEPTANCE_OWNER_USER_IDS", None)
    routes = load_routes()
    household = type("SyntheticBeta", (), {"id": "synthetic-beta", "role": "user"})()
    unmapped_admin = type("UnmappedAdmin", (), {"id": "synthetic-gamma", "role": "admin"})()
    owner = type("SyntheticAlpha", (), {"id": "synthetic-alpha", "role": "admin"})()

    access = routes["/api/v1/hades/receipt/access"]
    assert (await access(household)).value == {"allowed": False}
    assert (await access(unmapped_admin)).value == {"allowed": False}
    assert (await access(owner)).value == {"allowed": True}

    await expect_denied(
        routes["/api/v1/hades/receipt/preview"], household,
        "Receipt OCR preview is owner-only.",
    )
    await expect_denied(
        routes["/api/v1/hades/receipt/apply"], household,
        "Receipt pantry updates are owner-only.",
    )
    await expect_denied(
        routes["/api/v1/hades/receipt/preview"], unmapped_admin,
        "Receipt OCR preview is owner-only.",
    )
    await expect_owner_reaches_input_validation(
        routes["/api/v1/hades/receipt/preview"], owner, EmptyPreviewRequest(),
        "An image file is required.",
    )
    await expect_owner_reaches_input_validation(
        routes["/api/v1/hades/receipt/apply"], owner, UnconfirmedApplyRequest(),
        "Explicit confirmation is required before adding pantry items.",
    )
    print("PASS household and unmapped admin receipt requests fail before upload, OCR, ledger, or Grocy access")
    print("PASS mapped synthetic owner reaches upload and explicit-confirmation validation")


if __name__ == "__main__":
    asyncio.run(main())
