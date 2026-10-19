"""Small helper functions that keep the tests short and readable.

Every function takes Playwright's `page` object as its first argument.
Elements are found with `data-testid` attributes, which stay stable even when
the page layout or wording changes.
"""
from playwright.sync_api import Page, expect

# Expected event data (see docs/app-spec.md). Used to build expected values.
EVENTS = {
    "python-workshop": {"title": "Python Workshop", "price": "$20.00", "capacity": 10},
    "hackathon": {"title": "Campus Hackathon", "price": "$50.00", "capacity": 5},
    "robotics-night": {"title": "Robotics Demo Night", "price": "$12.00", "capacity": 2},
}


def open_app(page: Page) -> None:
    """Open the home page and wait until it has rendered."""
    page.goto("/")
    expect(page.get_by_test_id("app-title")).to_be_visible()


def fill_form(page: Page, name: str, email: str, event_id: str = "", student: bool = False) -> None:
    """Fill in the booking form WITHOUT submitting it."""
    page.get_by_test_id("name-input").fill(name)
    page.get_by_test_id("email-input").fill(email)
    if event_id:
        page.get_by_test_id("event-select").select_option(event_id)
    if student:
        page.get_by_test_id("student-checkbox").check()


def submit_form(page: Page) -> None:
    """Click the "Book my seat" button once."""
    page.get_by_test_id("submit-button").click()


def book(page: Page, name: str, email: str, event_id: str = "", student: bool = False,
         wait_for_confirmation: bool = True) -> None:
    """Fill in the form, submit it and (by default) wait for the confirmation.

    The app simulates a slow payment step, so a booking only finishes after a
    short delay. Waiting for the confirmation makes sure the booking is saved
    before the next line of the test runs.
    """
    fill_form(page, name, email, event_id, student)
    submit_form(page)
    if wait_for_confirmation:
        expect(page.get_by_test_id("confirmation")).to_be_visible()


def booking_items(page: Page):
    """Locator for every row in the "My bookings" list."""
    return page.get_by_test_id("booking-item")


def seats_label(page: Page, event_id: str):
    """Locator for the 'X of Y seats left' / 'Sold out' text of an event card."""
    return page.get_by_test_id(f"event-seats-{event_id}")
