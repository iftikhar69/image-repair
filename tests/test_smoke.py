"""Smoke tests: "Does the app start and show the basics?"

A smoke test is a quick, shallow check that the most important things work.
If a smoke test fails there is no point running deeper tests.
"""
import pytest
from playwright.sync_api import Page, expect

from tests.helpers import EVENTS, open_app


def test_home_page_loads_with_correct_title(page: Page):
    open_app(page)
    expect(page).to_have_title("Campus Event Booking")
    expect(page.get_by_test_id("app-title")).to_have_text("Campus Event Booking")


def test_page_has_no_javascript_errors_on_load(page: Page):
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))  # collect any JS errors
    open_app(page)
    assert errors == [], f"JavaScript errors on page load: {errors}"


def test_three_events_are_listed(page: Page):
    open_app(page)
    cards = page.locator("[data-testid^='event-card-']")
    expect(cards).to_have_count(3)


@pytest.mark.parametrize("event_id", list(EVENTS))
def test_each_event_card_shows_its_title_and_price(page: Page, event_id):
    open_app(page)
    expected = EVENTS[event_id]
    expect(page.get_by_test_id(f"event-title-{event_id}")).to_have_text(expected["title"])
    expect(page.get_by_test_id(f"event-price-{event_id}")).to_have_text(expected["price"])


def test_booking_form_shows_all_fields(page: Page):
    open_app(page)
    for test_id in ["name-input", "email-input", "event-select", "student-checkbox", "submit-button"]:
        expect(page.get_by_test_id(test_id)).to_be_visible()


def test_new_visitor_sees_no_bookings_and_no_confirmation(page: Page):
    open_app(page)
    expect(page.get_by_test_id("bookings-empty")).to_be_visible()
    expect(page.get_by_test_id("booking-item")).to_have_count(0)
    expect(page.get_by_test_id("confirmation")).to_be_hidden()
