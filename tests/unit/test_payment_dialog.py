"""
Unit & UI tests for PaymentDialog customer registration and layout responsiveness.
"""
from __future__ import annotations

from decimal import Decimal
import pytest
from PySide6.QtWidgets import QApplication
from unittest.mock import patch, MagicMock

from pakpos.database.models.customer import Customer
from pakpos.database.models.sale import PaymentMethod
from pakpos.ui.dialogs.payment_dialog import PaymentDialog
from pakpos.ui.dialogs.customer_dialog import QuickCustomerDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    yield app


def test_payment_dialog_credit_khata_customer_box_visibility(qapp):
    customers = [
        Customer(id=1, name="Ali Ahmad", phone="0300-1111111"),
        Customer(id=2, name="Usman Raza", phone="0300-2222222"),
    ]
    dlg = PaymentDialog(total_amount=Decimal("1500.00"), customers=customers)

    # Cash selected by default: customer box hidden
    assert dlg.box_customer.isHidden()

    # Change to Credit / Khata
    dlg.combo_method.setCurrentIndex(1)
    assert dlg.payment_method == PaymentMethod.CREDIT
    assert not dlg.box_customer.isHidden()
    assert dlg.combo_customer.count() == 3  # Header + 2 customers


def test_quick_customer_dialog_validation_and_creation(qapp, db_session):
    dlg = QuickCustomerDialog(session=db_session)
    dlg.input_name.setText("Bilal Hassani")
    dlg.input_phone.setText("0300-9988776")
    dlg.input_address.setText("Gulberg, Lahore")
    dlg.input_balance.setText("500")

    dlg._on_save()

    assert dlg.created_customer is not None
    assert dlg.created_customer.name == "Bilal Hassani"
    assert dlg.created_customer.phone == "0300-9988776"
    assert dlg.created_customer.opening_balance == Decimal("500.00")


def test_payment_dialog_on_add_quick_customer(qapp, db_session):
    customers = []
    dlg = PaymentDialog(total_amount=Decimal("2360.00"), customers=customers, session=db_session)

    new_cust = Customer(id=99, name="Kashif Khan", phone="0312-3456789")

    def mock_exec(self_dlg):
        self_dlg.created_customer = new_cust
        return 1

    with patch.object(QuickCustomerDialog, "exec", mock_exec):
        dlg._on_add_quick_customer()

    assert len(dlg.customers) == 1
    assert dlg.combo_customer.count() == 2
    assert dlg.combo_customer.currentData() == 99
