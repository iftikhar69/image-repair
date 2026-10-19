# Campus Event Booking: Specification

This document defines how the application **should** behave. It is the *test oracle*: when a test and the
running app disagree, you compare both against this document. If the document says the app is wrong, the
app is fixed. **Never change a test's expected value to match behaviour that this document says is wrong.**

Each rule has an ID (for example `V-2`) that issues, tests, and pull requests refer to.

## Events

| Event id          | Title               | Date         | Price  | Capacity |
|-------------------|---------------------|--------------|--------|----------|
| `python-workshop` | Python Workshop     | Nov 5, 2026  | $20.00 | 10       |
| `hackathon`       | Campus Hackathon    | Nov 12, 2026 | $50.00 | 5        |
| `robotics-night`  | Robotics Demo Night | Nov 19, 2026 | $12.00 | 2        |

Each event card shows title, date, price, and seats: `N of M seats left`, or `Sold out` when no seats remain.

## Booking flow

1. The student enters **name** and **email**, chooses an **event**, and optionally ticks **I am a student**.
2. The student clicks **Book my seat**.
3. The input is validated (rules `V-*`). On failure, error messages appear and nothing is booked.
4. Otherwise the app shows "Processing your booking..." for about 0.3 seconds (a simulated payment step).
5. The booking is saved, the form is cleared, seat counts and "My bookings" update, and the confirmation appears.

Checks run in this order: **validation, then duplicate check, then capacity check.**

## Rules

### Validation (Issue 1)

| ID  | Rule |
|-----|------|
| V-1 | Name is required. Leading and trailing spaces are ignored, so a name of only spaces counts as empty. Message: `Please enter your name.` |
| V-2 | After trimming, the name must be **2 to 60 characters**. Messages: `Name must be at least 2 characters.` / `Name must be 60 characters or fewer.` |
| V-3 | Email is required (spaces ignored). Message: `Please enter your email address.` |
| V-4 | Email must look like `local@domain.tld`: exactly one `@`, no spaces, and a `.` in the domain with text on both sides. Message: `Please enter a valid email address.` |
| V-5 | An event must be selected. Message: `Please select an event.` |
| V-6 | If any validation rule fails: show every applicable message next to its field, create **no** booking, and show **no** confirmation. |

### Capacity (Issue 2)

| ID  | Rule |
|-----|------|
| C-1 | Seats left = capacity minus existing bookings for that event. At 0 the card shows `Sold out`. |
| C-2 | If an event has no seats left, a booking attempt is rejected with `Sorry, this event is sold out.` No booking is created and no confirmation is shown. |
| C-3 | Capacity is per event, and it is still enforced after the page is reloaded. A sold-out event never blocks other events. |

### Pricing (Issue 3)

| ID  | Rule |
|-----|------|
| P-1 | A regular ticket costs the event's list price. |
| P-2 | A student ticket costs **20% less** than the list price, rounded to the nearest cent. `$20.00 → $16.00`, `$50.00 → $40.00`, `$12.00 → $9.60`. |
| P-3 | The price display updates immediately when the event or the student checkbox changes. It shows `—` while no event is selected. |
| P-4 | A price is never negative. The amount in the confirmation and in "My bookings" equals the price that was displayed when the student booked. |

### Confirmation (Issue 4)

| ID  | Rule |
|-----|------|
| F-1 | The confirmation shows exactly what was submitted: the **name** (trimmed), the **email** (trimmed), the **event booked**, and the **amount charged**. |
| F-2 | The confirmation is hidden when a new submission starts and shown only after a booking succeeds. |
| F-3 | The matching row in "My bookings" shows the same name, email, event, and amount. |

### Duplicates (Issue 5)

| ID  | Rule |
|-----|------|
| D-1 | One submission creates exactly one booking, even if the button is clicked twice quickly. |
| D-2 | The same email (ignoring upper/lower case and surrounding spaces) may hold only **one** booking per event. A second attempt is rejected with `You have already booked this event with this email.` |
| D-3 | The same email **may** book different events, and different emails **may** book the same event. |

## How the app stores data (localStorage)

* Bookings are saved in the browser's `localStorage` under the key `svv.campus-events.bookings.v1`, as a JSON array.
* Each booking: `id`, `name`, `email`, `eventId`, `student`, `amount`, `createdAt`.
* There is no server and no database, so data exists **only in that browser profile**. Another browser, or a
  private window, starts empty.
* Data survives a page reload (this is required for capacity to work across reloads).
* The **Reset demo data** button deletes the key.
* Playwright gives every test a fresh browser context, so tests never share bookings.
* To inspect it manually: browser DevTools, *Application* tab, *Local Storage*.

## Out of scope

Real payments, authentication, e-mail sending, accessibility audit, performance, other browsers than Chromium,
and any server-side behaviour.
