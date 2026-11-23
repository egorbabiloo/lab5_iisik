# -*- coding: utf-8 -*-
"""
E2E Integration & Invariant Tests for Lab 4 GraphQL Business Mutations.
Tests createShipment, cancelShipment, assignCourier, updateCourierStatus,
updateDeliveryCheckpoint, and verifyAndCompleteDelivery.
"""

import pytest
from tests.test_graphql_e2e.conftest import (
    GraphQLExecutor,
    KNOWN_TARIFF_ID,
    KNOWN_COURIER_ID,
    KNOWN_TRACKING_NUMBER,
)


@pytest.mark.asyncio
async def test_create_shipment_mutation(graphql_client: GraphQLExecutor):
    """Verifies shipment creation, price calculation, and automatic route & delivery orchestration."""
    mutation_str = """
    mutation CreateTestShipment($input: CreateShipmentInput!) {
      createShipment(input: $input) {
        id
        trackingNumber
        calculatedPrice
        currentStatus
        originCity
        destCity
        weightKg
        dimensions {
          lengthCm
          widthCm
          heightCm
        }
        route {
          id
          status
          stages {
            stageOrder
            stageType
            status
          }
        }
        activeDelivery {
          id
          status
          deliveryType
        }
      }
    }
    """
    variables = {
      "input": {
        "tariffId": KNOWN_TARIFF_ID,
        "weightKg": 4.5,
        "dimensions": {
          "lengthCm": 30.0,
          "widthCm": 20.0,
          "heightCm": 15.0,
        },
        "originCity": "Минск",
        "originAddress": "пр-т Независимости, 4",
        "destCity": "Витебск",
        "destAddress": "ул. Ленина, 12",
        "recipientName": "Алексеев В.И.",
        "recipientPhone": "+375291112233",
      }
    }

    res = await graphql_client.execute(mutation_str, variables=variables)
    assert "errors" not in res, f"Expected no errors, got: {res.get('errors')}"
    data = res["data"]["createShipment"]

    assert data["trackingNumber"].startswith("PKG-BY-2026-")
    assert data["currentStatus"] == "CREATED"
    assert float(data["calculatedPrice"]) > 0
    assert data["dimensions"]["lengthCm"] == 30.0
    assert data["route"] is not None
    assert data["route"]["status"] == "ACTIVE"
    assert len(data["route"]["stages"]) >= 1
    assert data["activeDelivery"] is not None
    assert data["activeDelivery"]["status"] == "PENDING_ASSIGNMENT"


@pytest.mark.asyncio
async def test_cancel_shipment_lifecycle(graphql_client: GraphQLExecutor):
    """Verifies that freshly created shipments can be cancelled, transitioning to CANCELLED."""
    # 1. Create a shipment first
    create_mutation = """
    mutation CreateForCancel($input: CreateShipmentInput!) {
      createShipment(input: $input) {
        trackingNumber
        currentStatus
      }
    }
    """
    create_res = await graphql_client.execute(
        create_mutation,
        variables={
            "input": {
                "tariffId": KNOWN_TARIFF_ID,
                "weightKg": 2.0,
                "dimensions": {"lengthCm": 10.0, "widthCm": 10.0, "heightCm": 10.0},
                "originCity": "Минск",
                "originAddress": "ул. Немига, 5",
                "destCity": "Могилев",
                "destAddress": "ул. Первомайская, 2",
                "recipientName": "Петров П.П.",
                "recipientPhone": "+375292223344",
            }
        },
    )
    tracking_num = create_res["data"]["createShipment"]["trackingNumber"]

    # 2. Cancel the shipment
    cancel_mutation = """
    mutation CancelShipment($trackingNumber: String!, $reason: String) {
      cancelShipment(trackingNumber: $trackingNumber, reason: $reason)
    }
    """
    cancel_res = await graphql_client.execute(
        cancel_mutation,
        variables={
            "trackingNumber": tracking_num,
            "reason": "Client cancelled order before pickup",
        },
    )
    assert "errors" not in cancel_res
    assert cancel_res["data"]["cancelShipment"] is True

    # 3. Verify status updated to CANCELLED
    query_str = """
    query CheckStatus($trackingNumber: String!) {
      shipment(trackingNumber: $trackingNumber) {
        currentStatus
      }
    }
    """
    query_res = await graphql_client.execute(query_str, variables={"trackingNumber": tracking_num})
    assert query_res["data"]["shipment"]["currentStatus"] == "CANCELLED"


@pytest.mark.asyncio
async def test_cancel_shipment_in_transit_rejected(graphql_client: GraphQLExecutor):
    """Business Invariant: Shipments already in transit/delivered cannot be cancelled."""
    cancel_mutation = """
    mutation CancelInTransit($trackingNumber: String!) {
      cancelShipment(trackingNumber: $trackingNumber)
    }
    """
    res = await graphql_client.execute(
        cancel_mutation, variables={"trackingNumber": KNOWN_TRACKING_NUMBER}
    )
    assert "errors" in res, "Expected business rule validation error when cancelling shipment in transit"
    error_msg = res["errors"][0]["message"].lower()
    assert "cannot cancel" in error_msg or "in transit" in error_msg or "status" in error_msg


@pytest.mark.asyncio
async def test_assign_courier_and_capacity_check(graphql_client: GraphQLExecutor):
    """Verifies courier assignment and checks payload capacity validation."""
    # 1. Create shipment with 80 kg weight (exceeds bicycle/foot couriers)
    create_res = await graphql_client.execute(
        """
        mutation CreateHeavy($input: CreateShipmentInput!) {
          createShipment(input: $input) {
            id
            activeDelivery { id }
          }
        }
        """,
        variables={
            "input": {
                "tariffId": KNOWN_TARIFF_ID,
                "weightKg": 80.0,
                "dimensions": {"lengthCm": 50.0, "widthCm": 50.0, "heightCm": 50.0},
                "originCity": "Минск",
                "originAddress": "Склад-Юг",
                "destCity": "Минск",
                "destAddress": "Завод",
                "recipientName": "Заказчик",
                "recipientPhone": "+375295556677",
            }
        },
    )
    delivery_id = create_res["data"]["createShipment"]["activeDelivery"]["id"]

    # 2. Try to assign bike courier (maxPayload 15kg or 25kg) -> Should reject
    couriers_res = await graphql_client.execute(
        """
        query GetSmallCourier {
          couriers(filter: { transportType: BICYCLE }) {
            id
            maxPayloadKg
          }
        }
        """
    )
    small_couriers = couriers_res["data"]["couriers"]
    if small_couriers:
        small_courier_id = small_couriers[0]["id"]
        assign_res = await graphql_client.execute(
            """
            mutation AssignOverweight($input: AssignCourierInput!) {
              assignCourier(input: $input) { id }
            }
            """,
            variables={"input": {"deliveryId": delivery_id, "courierId": small_courier_id}},
        )
        assert "errors" in assign_res
        assert "payload capacity" in assign_res["errors"][0]["message"].lower() or "exceeds" in assign_res["errors"][0]["message"].lower()

    # 3. Create a lightweight parcel (2 kg) and assign available courier
    light_res = await graphql_client.execute(
        """
        mutation CreateLight($input: CreateShipmentInput!) {
          createShipment(input: $input) {
            id
            activeDelivery { id }
          }
        }
        """,
        variables={
            "input": {
                "tariffId": KNOWN_TARIFF_ID,
                "weightKg": 2.0,
                "dimensions": {"lengthCm": 10.0, "widthCm": 10.0, "heightCm": 10.0},
                "originCity": "Минск",
                "originAddress": "ул. Сурганова, 1",
                "destCity": "Минск",
                "destAddress": "ул. Я.Коласа, 5",
                "recipientName": "Студент",
                "recipientPhone": "+375297778899",
            }
        },
    )
    light_delivery_id = light_res["data"]["createShipment"]["activeDelivery"]["id"]

    # Pick an AVAILABLE courier
    avail_res = await graphql_client.execute(
        """
        query GetAvail {
          couriers(filter: { status: AVAILABLE }) { id currentStatus }
        }
        """
    )
    avail_list = avail_res["data"]["couriers"]
    if not avail_list:
        # Reset a courier to AVAILABLE for testing
        await graphql_client.execute(
            """
            mutation ResetCourier($input: UpdateCourierStatusInput!) {
              updateCourierStatus(input: $input) { id currentStatus }
            }
            """,
            variables={"input": {"courierId": KNOWN_COURIER_ID, "status": "AVAILABLE"}},
        )
        test_courier_id = KNOWN_COURIER_ID
    else:
        test_courier_id = avail_list[0]["id"]

    # Assign courier
    assign_success = await graphql_client.execute(
        """
        mutation AssignValid($input: AssignCourierInput!) {
          assignCourier(input: $input) {
            id
            status
            courier { id currentStatus }
          }
        }
        """,
        variables={"input": {"deliveryId": light_delivery_id, "courierId": test_courier_id}},
    )
    assert "errors" not in assign_success, f"Assign failed: {assign_success.get('errors')}"
    deliv_data = assign_success["data"]["assignCourier"]
    assert deliv_data["status"] == "ASSIGNED"
    assert deliv_data["courier"]["currentStatus"] == "BUSY"

    # Reset courier back to AVAILABLE for subsequent test isolation
    await graphql_client.execute(
        """
        mutation ResetBack($input: UpdateCourierStatusInput!) {
          updateCourierStatus(input: $input) { id currentStatus }
        }
        """,
        variables={"input": {"courierId": test_courier_id, "status": "AVAILABLE"}},
    )


@pytest.mark.asyncio
async def test_courier_cannot_go_offline_while_busy(graphql_client: GraphQLExecutor):
    """Business Invariant: Courier with active deliveries (BUSY) cannot switch to OFFLINE."""
    # Find or set a courier to BUSY
    couriers_res = await graphql_client.execute(
        """
        query GetBusyCourier {
          couriers(filter: { status: BUSY }) { id }
        }
        """
    )
    busy_list = couriers_res["data"]["couriers"]
    if not busy_list:
        # Set KNOWN_COURIER_ID to BUSY
        await graphql_client.execute(
            """
            mutation SetBusy($input: UpdateCourierStatusInput!) {
              updateCourierStatus(input: $input) { id currentStatus }
            }
            """,
            variables={"input": {"courierId": KNOWN_COURIER_ID, "status": "BUSY"}},
        )
        busy_courier_id = KNOWN_COURIER_ID
    else:
        busy_courier_id = busy_list[0]["id"]

    # Attempt to transition BUSY courier to OFFLINE
    offline_res = await graphql_client.execute(
        """
        mutation TryOffline($input: UpdateCourierStatusInput!) {
          updateCourierStatus(input: $input) { id currentStatus }
        }
        """,
        variables={"input": {"courierId": busy_courier_id, "status": "OFFLINE"}},
    )
    assert "errors" in offline_res
    err_text = offline_res["errors"][0]["message"].lower()
    assert "offline" in err_text or "active" in err_text or "busy" in err_text

    # Reset courier back to AVAILABLE
    await graphql_client.execute(
        """
        mutation ResetBusyBack($input: UpdateCourierStatusInput!) {
          updateCourierStatus(input: $input) { id currentStatus }
        }
        """,
        variables={"input": {"courierId": busy_courier_id, "status": "AVAILABLE"}},
    )


@pytest.mark.asyncio
async def test_delivery_checkpoint_and_otp_completion(graphql_client: GraphQLExecutor):
    """Verifies logging delivery checkpoints and OTP verification on delivery completion."""
    # 1. Create and assign shipment
    create_res = await graphql_client.execute(
        """
        mutation CreateForOTP($input: CreateShipmentInput!) {
          createShipment(input: $input) {
            id
            trackingNumber
            activeDelivery { id }
          }
        }
        """,
        variables={
            "input": {
                "tariffId": KNOWN_TARIFF_ID,
                "weightKg": 1.5,
                "dimensions": {"lengthCm": 10.0, "widthCm": 10.0, "heightCm": 10.0},
                "originCity": "Минск",
                "originAddress": "ул. Кульман, 3",
                "destCity": "Минск",
                "destAddress": "ул. Веры Хоружей, 25",
                "recipientName": "Получатель OTP",
                "recipientPhone": "+375298889900",
            }
        },
    )
    deliv_id = create_res["data"]["createShipment"]["activeDelivery"]["id"]
    track_num = create_res["data"]["createShipment"]["trackingNumber"]

    # 2. Add checkpoint: PICKED_UP
    cp_res = await graphql_client.execute(
        """
        mutation AddCheckpoint($input: UpdateDeliveryCheckpointInput!) {
          updateDeliveryCheckpoint(input: $input) {
            id
            status
            locationName
            notes
          }
        }
        """,
        variables={
            "input": {
                "deliveryId": deliv_id,
                "status": "PICKED_UP",
                "locationName": "Минск Сортировочный",
                "notes": "Посылка успешно принята курьером",
            }
        },
    )
    assert "errors" not in cp_res
    assert cp_res["data"]["updateDeliveryCheckpoint"]["status"] == "PICKED_UP"

    # 3. Test wrong OTP code -> Should be rejected
    wrong_otp_res = await graphql_client.execute(
        """
        mutation CompleteWrong($input: VerifyDeliveryCodeInput!) {
          verifyAndCompleteDelivery(input: $input) { id status }
        }
        """,
        variables={"input": {"deliveryId": deliv_id, "plainOtpCode": "999999"}},
    )
    assert "errors" in wrong_otp_res
    assert "otp" in wrong_otp_res["errors"][0]["message"].lower()

    # 4. Complete with valid OTP code ("123456")
    correct_otp_res = await graphql_client.execute(
        """
        mutation CompleteCorrect($input: VerifyDeliveryCodeInput!) {
          verifyAndCompleteDelivery(input: $input) {
            id
            status
            actualDeliveredAt
          }
        }
        """,
        variables={"input": {"deliveryId": deliv_id, "plainOtpCode": "123456"}},
    )
    assert "errors" not in correct_otp_res
    completed_data = correct_otp_res["data"]["verifyAndCompleteDelivery"]
    assert completed_data["status"] == "DELIVERED"
    assert completed_data["actualDeliveredAt"] is not None

    # 5. Check shipment status is now DELIVERED
    check_shipment = await graphql_client.execute(
        """
        query VerifyFinalShipment($trackingNumber: String!) {
          shipment(trackingNumber: $trackingNumber) {
            currentStatus
          }
        }
        """,
        variables={"trackingNumber": track_num},
    )
    assert check_shipment["data"]["shipment"]["currentStatus"] == "DELIVERED"
