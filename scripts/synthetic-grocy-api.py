#!/usr/bin/env python3
"""Small authenticated canonical-Grocy fixture for the household UI test."""
from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

bind, port_path, requests_path = sys.argv[1:]
failure_path = os.environ.get("HADES_SYNTHETIC_GROCY_FAILURE_FILE", "")
key = "synthetic-grocy-ui-key"
products = [
    {"id": 11, "name": "milk", "qu_id_stock": 1, "qu_id_purchase": 1},
    {"id": 12, "name": "eggs", "qu_id_stock": 1, "qu_id_purchase": 1},
    {"id": 13, "name": "bread", "qu_id_stock": 1, "qu_id_purchase": 1},
    {"id": 14, "name": "bananas", "qu_id_stock": 1, "qu_id_purchase": 1},
    {"id": 15, "name": "rice", "qu_id_stock": 1, "qu_id_purchase": 3},
    {"id": 16, "name": "chicken", "qu_id_stock": 1, "qu_id_purchase": 1},
]
today = date.today()
stock = [
    {"product_id": 11, "product": {"name": "milk"}, "amount_aggregated": 2, "best_before_date": (today + timedelta(days=30)).isoformat()},
    {"product_id": 12, "product": {"name": "eggs"}, "amount_aggregated": 1, "best_before_date": (today + timedelta(days=2)).isoformat()},
    {"product_id": 13, "product": {"name": "bread"}, "amount_aggregated": 1, "best_before_date": (today - timedelta(days=1)).isoformat()},
    {"product_id": 15, "product": {"name": "rice"}, "amount_aggregated": 0.5},
]
recipes = [
    {"id": 21, "name": "Synthetic Pancakes", "base_servings": 4},
    {"id": 22, "name": "Milk Soup", "base_servings": 2},
    {"id": 23, "name": "Expired Toast", "base_servings": 1},
    {"id": 24, "name": "Unit Mismatch Bread", "base_servings": 1},
    {"id": 25, "name": "Converted Unit Rice", "base_servings": 3},
    {"id": 26, "name": "Lemon Chicken", "base_servings": 4},
]
recipe_positions = [
    {"recipe_id": 21, "product_id": 11, "amount": 2, "qu_id": 1},
    {"recipe_id": 21, "product_id": 12, "amount": 2, "qu_id": 1},
    {"recipe_id": 22, "product_id": 11, "amount": 1, "qu_id": 1},
    {"recipe_id": 23, "product_id": 13, "amount": 1, "qu_id": 1},
    {"recipe_id": 24, "product_id": 14, "amount": 1, "qu_id": 2},
    {"recipe_id": 25, "product_id": 15, "amount": 1, "qu_id": 2},
    {"recipe_id": 25, "product_id": 15, "amount": 1, "qu_id": 2},
    {"recipe_id": 26, "product_id": 16, "amount": 1, "qu_id": 1},
]
resolved_conversions = [
    {"product_id": 15, "from_qu_id": 2, "to_qu_id": 1, "factor": 0.5},
    {"product_id": 15, "from_qu_id": 1, "to_qu_id": 3, "factor": 2.0},
]
shopping: list[dict] = []
next_id = 1
next_recipe_id = 30
next_position_id = 100


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _record(self, body=None):
        row = {"method": self.command, "path": self.path, "keyValid": self.headers.get("GROCY-API-KEY") == key}
        if body is not None:
            row["body"] = body
        with Path(requests_path).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")

    def _send(self, status, value):
        payload = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802
        self._record()
        if failure_path and Path(failure_path).exists():
            self._send(503, {"error": "synthetic canonical Grocy outage"})
        elif self.headers.get("GROCY-API-KEY") != key:
            self._send(401, {"error": "unauthorized"})
        elif self.path == "/api/stock":
            self._send(200, stock)
        elif self.path == "/api/objects/products":
            self._send(200, products)
        elif urlsplit(self.path).path.startswith("/api/objects/recipes/"):
            recipe_id = urlsplit(self.path).path.rsplit("/", 1)[-1]
            recipe = next((row for row in recipes if str(row["id"]) == recipe_id), None)
            self._send(200, recipe) if recipe else self._send(404, {"error": "not found"})
        elif self.path == "/api/objects/recipes":
            self._send(200, recipes)
        elif self.path == "/api/objects/recipes_pos":
            self._send(200, recipe_positions)
        elif urlsplit(self.path).path.startswith("/api/recipes/") and urlsplit(self.path).path.endswith("/fulfillment"):
            recipe_id = int(urlsplit(self.path).path.split("/")[-2])
            positions = [row for row in recipe_positions if row["recipe_id"] == recipe_id]
            missing = 0
            for position in positions:
                available = next((row.get("amount_aggregated", 0) for row in stock if row["product_id"] == position["product_id"]), 0)
                if available < position["amount"]:
                    missing += 1
            recipe = next((row for row in recipes if row["id"] == recipe_id), {})
            self._send(200, {"recipe_name": recipe.get("name", ""), "missing_products_count": missing})
        elif urlsplit(self.path).path == "/api/objects/quantity_unit_conversions_resolved":
            query = parse_qs(urlsplit(self.path).query)
            filters = query.get("query[]", [])
            product_ids = {value.split("=", 1)[1] for value in filters if value.startswith("product_id=")}
            self._send(200, [row for row in resolved_conversions if str(row["product_id"]) in product_ids])
        elif self.path == "/api/objects/shopping_list":
            self._send(200, shopping)
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        global next_id, next_recipe_id, next_position_id
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
        self._record(body)
        if failure_path and Path(failure_path).exists():
            self._send(503, {"error": "synthetic canonical Grocy outage"})
        elif self.headers.get("GROCY-API-KEY") != key:
            self._send(401, {"error": "unauthorized"})
        elif self.path == "/api/objects/recipes":
            recipe = {"id": next_recipe_id, "name": str(body.get("name", "")), "description": str(body.get("description", "")), "base_servings": 1}
            next_recipe_id += 1
            recipes.append(recipe)
            self._send(200, {"created_object_id": recipe["id"]})
        elif self.path == "/api/objects/recipes_pos":
            recipe_id = int(body.get("recipe_id", 0))
            product_id = int(body.get("product_id", 0))
            amount = float(body.get("amount", 0))
            if not any(row["id"] == recipe_id for row in recipes) or not any(row["id"] == product_id for row in products) or amount <= 0:
                self._send(400, {"error": "invalid synthetic recipe ingredient"})
            else:
                position = {"id": next_position_id, "recipe_id": recipe_id, "product_id": product_id, "amount": amount, "qu_id": int(body.get("qu_id", 1))}
                next_position_id += 1
                recipe_positions.append(position)
                self._send(200, {"created_object_id": position["id"]})
        elif self.path.startswith("/api/recipes/") and self.path.endswith("/add-not-fulfilled-products-to-shoppinglist"):
            recipe_id = int(self.path.split("/")[3])
            needed_by_product = {}
            for position in recipe_positions:
                if position["recipe_id"] == recipe_id:
                    needed_by_product[position["product_id"]] = needed_by_product.get(position["product_id"], 0) + position["amount"]
            added = []
            for product_id, needed in needed_by_product.items():
                available = next((row.get("amount_aggregated", 0) for row in stock if row["product_id"] == product_id), 0)
                missing = max(0, needed - available)
                if missing:
                    row = {"id": next_id, "product_id": product_id, "amount": missing, "qu_id": 1, "done": False}
                    next_id += 1
                    shopping.append(row)
                    added.append(row)
            self._send(200, {"added": added})
        elif self.path != "/api/objects/shopping_list":
            self._send(404, {"error": "not found"})
        elif int(body.get("product_id", 0)) not in {11, 12, 15} or float(body.get("amount", 0)) != 1:
            self._send(400, {"error": "invalid synthetic shopping item"})
        elif int(body["product_id"]) == 15 and int(body.get("qu_id", 0)) != 3:
            self._send(400, {"error": "converted product requires its purchase unit"})
        else:
            row = {"id": next_id, "product_id": int(body["product_id"]), "amount": 1, "qu_id": int(body.get("qu_id", 1)), "done": False}
            next_id += 1
            shopping.append(row)
            self._send(200, {"created_object_id": row["id"]})

    def do_PUT(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
        self._record(body)
        if self.headers.get("GROCY-API-KEY") != key:
            self._send(401, {"error": "unauthorized"})
            return
        path = urlsplit(self.path).path
        if path.startswith("/api/objects/recipes/"):
            recipe_id = int(path.rsplit("/", 1)[-1])
            recipe = next((row for row in recipes if row["id"] == recipe_id), None)
            if recipe is None:
                self._send(404, {"error": "not found"})
            else:
                recipe.update({name: value for name, value in body.items() if name in {"name", "description", "base_servings"}})
                self._send(200, dict(recipe))
            return
        if not path.startswith("/api/objects/recipes/"):
            self._send(404, {"error": "not found"})
            return
        recipe_id = path.rsplit("/", 1)[-1]
        recipe = next((row for row in recipes if str(row["id"]) == recipe_id), None)
        servings = body.get("base_servings")
        if recipe is None:
            self._send(404, {"error": "not found"})
        elif isinstance(servings, bool) or not isinstance(servings, int) or not 1 <= servings <= 1000:
            self._send(400, {"error": "invalid serving count"})
        else:
            recipe["base_servings"] = servings
            self._send(200, dict(recipe))

    def do_DELETE(self):  # noqa: N802
        self._record()
        if self.headers.get("GROCY-API-KEY") != key:
            self._send(401, {"error": "unauthorized"})
            return
        path = urlsplit(self.path).path
        if path.startswith("/api/objects/recipes_pos/"):
            position_id = int(path.rsplit("/", 1)[-1])
            before = len(recipe_positions)
            recipe_positions[:] = [row for row in recipe_positions if row.get("id") != position_id]
            self._send(200, {"deleted": before != len(recipe_positions)})
        else:
            self._send(404, {"error": "not found"})


server = ThreadingHTTPServer((bind, 0), Handler)
Path(port_path).write_text(str(server.server_port), encoding="ascii")
server.serve_forever()
