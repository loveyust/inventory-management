"""
Tests for purchase order API endpoints.
"""
from datetime import datetime

import pytest


class TestPurchaseOrdersEndpoints:
    """Test suite for purchase-order-related endpoints."""

    def test_create_purchase_order_success(self, client):
        """Test creating a purchase order with two line items."""
        payload = {
            "items": [
                {"sku": "PCB-002", "name": "Dual Layer PCB Assembly", "quantity": 100, "unit_cost": 29.99},
                {"sku": "PLY-901", "name": "Drive Pulley", "quantity": 70, "unit_cost": 45.5}
            ]
        }
        response = client.post("/api/purchase-orders", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert "id" in data
        assert data["order_number"].startswith("PO-2025-")
        assert data["items"][0]["sku"] == "PCB-002"
        assert data["items"][1]["sku"] == "PLY-901"
        assert data["status"] == "Processing"
        assert 7 <= data["lead_time_days"] <= 14

    def test_create_purchase_order_appears_in_get_all(self, client):
        """Test that a newly created purchase order shows up in the full list."""
        payload = {"items": [{"sku": "STP-303", "name": "Stepper Motor NEMA 17", "quantity": 28, "unit_cost": 325.0}]}
        created = client.post("/api/purchase-orders", json=payload).json()

        response = client.get("/api/purchase-orders")
        assert response.status_code == 200

        all_ids = [po["id"] for po in response.json()]
        assert created["id"] in all_ids

    def test_create_purchase_order_missing_items_field(self, client):
        """Test that omitting the items field fails validation."""
        response = client.post("/api/purchase-orders", json={})
        assert response.status_code == 422

    def test_create_purchase_order_empty_items_list(self, client):
        """Test that submitting an empty items list is rejected."""
        response = client.post("/api/purchase-orders", json={"items": []})
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data

    def test_get_all_purchase_orders_structure(self, client):
        """Test that the purchase orders list has the expected structure."""
        client.post("/api/purchase-orders", json={
            "items": [{"sku": "GYR-207", "name": "Gyroscope Module", "quantity": 60, "unit_cost": 95.0}]
        })

        response = client.get("/api/purchase-orders")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        required_fields = [
            "id", "order_number", "items", "total_cost", "status",
            "created_date", "expected_delivery_date", "lead_time_days"
        ]
        for po in data:
            for field in required_fields:
                assert field in po, f"Missing field: {field}"

    def test_purchase_order_line_item_structure(self, client):
        """Test that each line item on a purchase order has the expected fields and types."""
        response = client.get("/api/purchase-orders")
        data = response.json()

        for po in data:
            for item in po["items"]:
                assert "sku" in item
                assert "name" in item
                assert "quantity" in item
                assert "unit_cost" in item
                assert isinstance(item["quantity"], int)
                assert isinstance(item["unit_cost"], (int, float))

    def test_purchase_order_total_cost_calculation(self, client):
        """Test that total_cost equals the sum of quantity * unit_cost across line items."""
        payload = {
            "items": [
                {"sku": "TMP-201", "name": "Temperature Sensor Module", "quantity": 75, "unit_cost": 89.5},
                {"sku": "PSU-507", "name": "Adjustable Bench Power Supply", "quantity": 35, "unit_cost": 125.0}
            ]
        }
        response = client.post("/api/purchase-orders", json=payload)
        data = response.json()

        expected_total = sum(item["quantity"] * item["unit_cost"] for item in payload["items"])
        assert abs(data["total_cost"] - expected_total) < 0.01

    def test_purchase_order_expected_delivery_matches_lead_time(self, client):
        """Test that expected_delivery_date is exactly lead_time_days after created_date."""
        payload = {"items": [{"sku": "PCB-002", "name": "Dual Layer PCB Assembly", "quantity": 10, "unit_cost": 29.99}]}
        response = client.post("/api/purchase-orders", json=payload)
        data = response.json()

        created = datetime.strptime(data["created_date"], "%Y-%m-%dT%H:%M:%S")
        expected = datetime.strptime(data["expected_delivery_date"], "%Y-%m-%dT%H:%M:%S")
        assert (expected - created).days == data["lead_time_days"]

    def test_backlog_endpoint_not_broken_by_purchase_orders(self, client):
        """Regression test: purchase orders with no backlog_item_id must not break /api/backlog."""
        client.post("/api/purchase-orders", json={
            "items": [{"sku": "PCB-002", "name": "Dual Layer PCB Assembly", "quantity": 10, "unit_cost": 29.99}]
        })

        response = client.get("/api/backlog")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        for item in data:
            assert isinstance(item["has_purchase_order"], bool)
