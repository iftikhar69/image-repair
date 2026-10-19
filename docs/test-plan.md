# Test Plan: Campus Event Booking

| Item | Value |
|------|-------|
| Application under test | Campus Event Booking (static HTML/CSS/JavaScript, `app/`) |
| Test tools | Python 3, pytest, Playwright for Python (synchronous API), Chromium |
| Specification | `docs/app-spec.md` |
| Test level | System-level, black-box browser tests |

## 1. Purpose: Verification and Validation

* **Verification** asks: *"Are we building the product right?"* We check the app against the written specification
  (`docs/app-spec.md`). Every automated test in this project is a verification test: it compares observed behaviour with a
  specific rule such as `V-2` or `C-2`.
* **Validation** asks: *"Are we building the right product?"* We check that the app actually serves its users. In this
  exercise validation is practised by **manual exploratory testing** (section 6): put yourself in a student's shoes and
  ask whether the booking flow makes sense and whether a confusing result (such as a price of `$-8.00`) would be acceptable.

This project also demonstrates **regression testing**: after a fix, the unaffected tests must still pass.

## 2. Scope

**In scope:** viewing events, booking form validation, seat capacity, student pricing, booking confirmation,
duplicate prevention, persistence in `localStorage`, reset of demo data.

**Out of scope:** real payments, authentication, e-mail sending, server-side behaviour, performance, security testing,
accessibility audit, browsers other than Chromium, mobile layouts.

## 3. Test approach

| Technique | Where it is used |
|-----------|------------------|
| Equivalence partitioning | Valid vs invalid names and emails (Issue 1); regular vs student tickets (Issue 3) |
| Boundary value analysis | Name length 1/2/60/61; seats `capacity - 1`, `capacity`, `capacity + 1` (Issues 1, 2) |
| Decision-based checks | Rule ordering: validation, then duplicate, then capacity |
| State-based testing | Seat counts after each booking; persistence after reload; reset (Issue 2 and unaffected tests) |
| Error guessing | Double click, same email in different letter case (Issue 5) |
| Oracle comparison | Confirmation compared with the data that was typed (Issue 4) |
| Regression testing | The `tests/` folder, re-run after every fix |

**Design rules for the automated tests**

1. One behaviour per test; the test name says what is expected.
2. Arrange, Act, Assert: set up, perform the action, check what the user can see.
3. Elements are found with `data-testid` attributes (stable even when the layout changes).
4. Use Playwright's auto-waiting `expect(...)` assertions. Do not use fixed `sleep` calls, with one documented exception:
   proving that something did **not** happen (Issue 5, double click) needs a short deliberate wait.
5. Tests are independent: every test gets a fresh browser context, so `localStorage` starts empty.
6. **Expected values come from the specification, never from what the app currently does.**

## 4. Test environment

* **Python 3.12 recommended; 3.10 or newer is required** (pytest 9 and pytest-playwright 0.10 need 3.10+).
  Packages come from `requirements.txt`, pinned to the versions this project was verified with.
* Chromium installed with `python -m playwright install chromium`.
* The website is served locally. The test run starts its own server automatically (`conftest.py`); you may also start one
  yourself with `python serve.py` and run `python -m pytest --base-url http://127.0.0.1:8000`.
* GitHub Actions runs `python -m pytest` on **Windows and Ubuntu** on every push to `main` and on every pull request.

## 5. Entry and exit criteria

| | Criteria |
|-|----------|
| **Entry** | Repository cloned; dependencies and Chromium installed; `python -m pytest` passes on the untouched starter. |
| **Exit (for a team's pull request)** | New test(s) failed before the fix and pass after it; full `python -m pytest` passes locally and in GitHub Actions; every acceptance criterion in the issue is ticked; no existing test's expected value was weakened. The pull request includes the before/after pytest output. Screenshots, that output, or a short demonstration of the working fix are appreciated when the defect is visible on screen. |

## 6. Manual exploratory session (validation)

Before writing automated tests, spend 10 minutes on a **charter**: *"Explore the booking form as a first-year student who
is in a hurry, to find anything that is wrong or confusing."* Write down what you tried, what you saw, and what you
expected. Try at least: empty form, odd names, odd emails, all three events, student ticket on every event, booking until
an event is full, reloading the page, double-clicking the button, booking twice with the same email.

## 7. Test inventory (starter)

| File | Tests | What it covers |
|------|------:|----------------|
| `tests/test_smoke.py` | 8 | Page loads, title, no JavaScript errors, three events with correct title and price, form fields present, clean initial state |
| `tests/test_unaffected_behavior.py` | 19 | Empty-field validation, regular prices, valid booking, trimming, booking list, form reset, seat counting below capacity, last seat, persistence across reload, reset button, test isolation |
| **Total** | **27** | All pass on the starter by design, even though the starter contains five defects. |

## 8. Traceability matrix

| Requirement | Default tests (pass on starter) | Issue |
|-------------|---------------------------------|-------|
| Events listed with title and price | `test_smoke.py` | n/a |
| V-1, V-3, V-5 (empty fields rejected) | `test_empty_name_is_rejected`, `test_empty_email_is_rejected`, `test_missing_event_is_rejected` | |
| V-1, V-2, V-4 (spaces, length, format) | none (defect) | #1 |
| C-1 (seats shown, sold out label) | `test_seat_count_goes_down...`, `test_last_available_seat...` | |
| C-2, C-3 (reject over capacity) | none (defect). Test booking number `capacity + 1` (the first booking the spec forbids), not only a much later attempt. | #2 |
| P-1, P-3 (regular price, live update) | `test_regular_price_is_shown_for_each_event`, `test_price_updates_when_...` | |
| P-2, P-4 (student price) | none (defect) | #3 |
| F-1 (name, amount), F-3 (booking list) | `test_valid_booking_shows_confirmation...`, `test_booking_appears_in_my_bookings...` | |
| F-1 (event, email) | none (defect). A check that only books Python Workshop can still pass. Book Campus Hackathon or Robotics Demo Night as well. | #4 |
| D-3 (different events / emails allowed) | `test_two_different_students_can_book_the_same_event` | |
| D-1, D-2 (no duplicates) | none (defect) | #5 |
| localStorage persistence and reset | `test_bookings_survive_a_page_reload`, `test_reset_button_clears_all_bookings` | |

## 9. Defect log (known defects in the starter)

| # | Defect | Severity | Spec rules |
|---|--------|----------|------------|
| 1 | Invalid booking details accepted | High: bad data stored | V-1, V-2, V-4, V-6 |
| 2 | Capacity exceeded | High: overbooking | C-2, C-3 |
| 3 | Wrong student discount (can be negative) | High: wrong money amount | P-2, P-4 |
| 4 | Confirmation shows wrong event and email | Medium: misleading, data stored correctly | F-1, F-3 |
| 5 | Duplicate bookings | High: wasted seats, wrong totals | D-1, D-2 |

## 10. Risks and limitations

* Only Chromium is tested. Behaviour in Firefox and WebKit is not verified.
* The 0.3 second simulated processing delay makes tests slightly slower and is what makes the double click defect reproducible.
* Test data lives in `localStorage` only, so there is no cleanup problem, but also nothing is shared between browsers.
* GitHub Actions runs the same `python -m pytest` command on Windows and on Ubuntu. A pull request is ready for review when both jobs are green.

## 11. Evidence to attach to the pull request

| Evidence | Required? |
|----------|-----------|
| Pytest output showing the new test **failed before** the fix | Yes |
| Pytest output showing the new test and the full suite **pass after** the fix | Yes |
| The issue's acceptance criteria, each one ticked | Yes |
| A screenshot of the wrong screen and of the corrected screen | Appreciated when the defect is visible |
| A short demonstration: a screen recording, or a note that the team can show the fix in class | Appreciated |

Screenshots and a demonstration help a reviewer see the defect. They do not replace the automated test. Paste images into the pull request, or drag them onto the GitHub comment box.
