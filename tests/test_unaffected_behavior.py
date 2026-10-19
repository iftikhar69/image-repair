"""Tests for behaviour that already works correctly in the starter project.

These tests are your safety net. After you fix your defect, run them again to
prove that you did not break anything else (this is called regression testing).

Each test follows the same three steps:
    1. Arrange - open the page / fill in the form
    2. Act     - click the button
    3. Assert  - check what the user can see
"""
import pytest
from playwright.sync_api import Page, expect

from tests.helpers import EVENTS, book, booking_items, fill_form, open_app, seats_label, submit_form


# --------------------------------------------------------------------------
# Required fields: an EMPTY field is rejected (this part of validation works)
# --------------------------------------------------------------------------
def test_empty_name_is_rejected(page: Page):
    open_app(page)
    fill_form(page, name="", email="alice@example.com", event_id="python-workshop")
    submit_form(page)

    expect(page.get_by_test_id("name-error")).to_have_text("Please enter your name.")
    expect(page.get_by_test_id("confirmation")).to_be_hidden()
    expect(booking_items(page)).to_have_count(0)


def test_empty_email_is_rejected(page: Page):
    open_app(page)
    fill_form(page, name="Alice Khan", email="", event_id="python-workshop")
    submit_form(page)

    expect(page.get_by_test_id("email-error")).to_have_text("Please enter your email address.")
    expect(page.get_by_test_id("confirmation")).to_be_hidden()
    expect(booking_items(page)).to_have_count(0)


def test_missing_event_is_rejected(page: Page):
    open_app(page)
    fill_form(page, name="Alice Khan", email="alice@example.com")  # no event chosen
    submit_form(page)

    expect(page.get_by_test_id("event-error")).to_have_text("Please select an event.")
    expect(page.get_by_test_id("confirmation")).to_be_hidden()
    expect(booking_items(page)).to_have_count(0)


# --------------------------------------------------------------------------
# Price display for a regular (non-student) ticket
# --------------------------------------------------------------------------
def test_price_shows_placeholder_before_an_event_is_chosen(page: Page):
    open_app(page)
    expect(page.get_by_test_id("price-display")).to_have_text("\u2014")


@pytest.mark.parametrize("event_id", list(EVENTS))
def test_regular_price_is_shown_for_each_event(page: Page, event_id):
    open_app(page)
    page.get_by_test_id("event-select").select_option(event_id)
    expect(page.get_by_test_id("price-display")).to_have_text(EVENTS[event_id]["price"])


def test_price_updates_when_a_different_event_is_chosen(page: Page):
    open_app(page)
    page.get_by_test_id("event-select").select_option("python-workshop")
    expect(page.get_by_test_id("price-display")).to_have_text("$20.00")
    page.get_by_test_id("event-select").select_option("hackathon")
    expect(page.get_by_test_id("price-display")).to_have_text("$50.00")


# --------------------------------------------------------------------------
# A valid booking works
# --------------------------------------------------------------------------
def test_valid_booking_shows_confirmation_with_name_and_amount(page: Page):
    open_app(page)
    book(page, "Alice Khan", "alice@example.com", "python-workshop")

    expect(page.get_by_test_id("confirmation-title")).to_have_text("Booking confirmed!")
    expect(page.get_by_test_id("confirmation-name")).to_have_text("Alice Khan")
    expect(page.get_by_test_id("confirmation-amount")).to_have_text("$20.00")


def test_surrounding_spaces_are_trimmed_from_the_name(page: Page):
    open_app(page)
    book(page, "  Alice Khan  ", "alice@example.com", "python-workshop")
    expect(page.get_by_test_id("confirmation-name")).to_have_text("Alice Khan")


def test_booking_appears_in_my_bookings_with_correct_details(page: Page):
    open_app(page)
    book(page, "Bilal Ahmed", "bilal@example.com", "hackathon")

    expect(booking_items(page)).to_have_count(1)
    row = booking_items(page).first
    expect(row).to_contain_text("Bilal Ahmed")
    expect(row).to_contain_text("bilal@example.com")
    expect(row).to_contain_text("Campus Hackathon")  # correct event name in the list
    expect(row).to_contain_text("$50.00")
    expect(page.get_by_test_id("bookings-empty")).to_be_hidden()


def test_form_is_cleared_after_a_successful_booking(page: Page):
    open_app(page)
    book(page, "Alice Khan", "alice@example.com", "python-workshop")

    expect(page.get_by_test_id("name-input")).to_have_value("")
    expect(page.get_by_test_id("email-input")).to_have_value("")
    expect(page.get_by_test_id("event-select")).to_have_value("")
    expect(page.get_by_test_id("price-display")).to_have_text("\u2014")


# --------------------------------------------------------------------------
# Seat counting (below capacity)
# --------------------------------------------------------------------------
def test_seat_count_goes_down_by_one_after_a_booking(page: Page):
    open_app(page)
    expect(seats_label(page, "python-workshop")).to_have_text("10 of 10 seats left")
    book(page, "Alice Khan", "alice@example.com", "python-workshop")
    expect(seats_label(page, "python-workshop")).to_have_text("9 of 10 seats left")


def test_booking_one_event_does_not_change_seats_of_other_events(page: Page):
    open_app(page)
    book(page, "Alice Khan", "alice@example.com", "python-workshop")
    expect(seats_label(page, "hackathon")).to_have_text("5 of 5 seats left")
    expect(seats_label(page, "robotics-night")).to_have_text("2 of 2 seats left")


def test_two_different_students_can_book_the_same_event(page: Page):
    open_app(page)
    book(page, "Alice Khan", "alice@example.com", "python-workshop")
    book(page, "Bilal Ahmed", "bilal@example.com", "python-workshop")
    expect(booking_items(page)).to_have_count(2)
    expect(seats_label(page, "python-workshop")).to_have_text("8 of 10 seats left")


def test_last_available_seat_can_still_be_booked(page: Page):
    open_app(page)
    book(page, "Alice Khan", "alice@example.com", "robotics-night")
    book(page, "Bilal Ahmed", "bilal@example.com", "robotics-night")  # seat 2 of 2
    expect(booking_items(page)).to_have_count(2)
    expect(seats_label(page, "robotics-night")).to_have_text("Sold out")


# --------------------------------------------------------------------------
# localStorage behaviour (see README "How the app stores data")
# --------------------------------------------------------------------------
def test_bookings_survive_a_page_reload(page: Page):
    open_app(page)
    book(page, "Alice Khan", "alice@example.com", "python-workshop")

    page.reload()

    expect(booking_items(page)).to_have_count(1)
    expect(seats_label(page, "python-workshop")).to_have_text("9 of 10 seats left")


def test_reset_button_clears_all_bookings(page: Page):
    open_app(page)
    book(page, "Alice Khan", "alice@example.com", "python-workshop")

    page.get_by_test_id("reset-button").click()

    expect(booking_items(page)).to_have_count(0)
    expect(page.get_by_test_id("bookings-empty")).to_be_visible()
    expect(seats_label(page, "python-workshop")).to_have_text("10 of 10 seats left")


def test_each_test_starts_with_a_clean_browser_state(page: Page):
    """pytest-playwright gives every test a brand-new browser context, so
    bookings made in one test never leak into another."""
    open_app(page)
    expect(booking_items(page)).to_have_count(0)
