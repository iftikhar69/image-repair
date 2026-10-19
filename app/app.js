/*
 * Campus Event Booking - classroom demo application.
 *
 * No framework, no build step, no server code. Bookings are stored in the
 * browser's localStorage so seat counts survive a page reload.
 *
 * Business rules are described in docs/app-spec.md.
 */
(function () {
  'use strict';

  // ---------------------------------------------------------------------
  // Configuration and data
  // ---------------------------------------------------------------------
  var STORAGE_KEY = 'svv.campus-events.bookings.v1';
  var STUDENT_DISCOUNT_PERCENT = 20;
  var PROCESSING_DELAY_MS = 300; // simulates a slow "payment" step

  var EVENTS = [
    { id: 'python-workshop', title: 'Python Workshop',     date: 'Nov 5, 2026',  price: 20, capacity: 10 },
    { id: 'hackathon',       title: 'Campus Hackathon',    date: 'Nov 12, 2026', price: 50, capacity: 5 },
    { id: 'robotics-night',  title: 'Robotics Demo Night', date: 'Nov 19, 2026', price: 12, capacity: 2 }
  ];

  // ---------------------------------------------------------------------
  // Small helpers
  // ---------------------------------------------------------------------
  function byId(id) { return document.getElementById(id); }

  function byTestId(testId) { return document.querySelector('[data-testid="' + testId + '"]'); }

  function makeElement(tag, text, testId, className) {
    var node = document.createElement(tag);
    if (text !== undefined && text !== null) { node.textContent = text; } // textContent: never parse user input as HTML
    if (testId) { node.setAttribute('data-testid', testId); }
    if (className) { node.className = className; }
    return node;
  }

  function formatMoney(amount) { return '$' + amount.toFixed(2); }

  function findEvent(eventId) {
    for (var i = 0; i < EVENTS.length; i++) {
      if (EVENTS[i].id === eventId) { return EVENTS[i]; }
    }
    return null;
  }

  // ---------------------------------------------------------------------
  // Storage
  // ---------------------------------------------------------------------
  function loadBookings() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
    } catch (error) {
      return [];
    }
  }

  function saveBookings(bookings) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(bookings));
  }

  function seatsLeft(event) {
    var taken = loadBookings().filter(function (b) { return b.eventId === event.id; }).length;
    return event.capacity - taken;
  }

  // ---------------------------------------------------------------------
  // Business rules
  // ---------------------------------------------------------------------
  function calculatePrice(event, isStudent) {
    if (!isStudent) { return event.price; }
    return event.price - STUDENT_DISCOUNT_PERCENT;
  }

  function validate(data) {
    var errors = {};
    if (data.name === '') { errors.name = 'Please enter your name.'; }
    if (data.email === '') { errors.email = 'Please enter your email address.'; }
    if (data.eventId === '') { errors.event = 'Please select an event.'; }
    return errors;
  }

  function isSoldOut(event) {
    return seatsLeft(event) < 0;
  }

  // ---------------------------------------------------------------------
  // Rendering
  // ---------------------------------------------------------------------
  function renderEvents() {
    var container = byId('event-list');
    container.textContent = '';

    EVENTS.forEach(function (ev) {
      var left = seatsLeft(ev);
      var card = makeElement('article', null, 'event-card-' + ev.id, 'event-card');
      card.appendChild(makeElement('h3', ev.title, 'event-title-' + ev.id));
      card.appendChild(makeElement('p', ev.date, 'event-date-' + ev.id));
      card.appendChild(makeElement('p', formatMoney(ev.price), 'event-price-' + ev.id, 'price'));
      if (left <= 0) {
        card.appendChild(makeElement('p', 'Sold out', 'event-seats-' + ev.id, 'sold-out'));
      } else {
        card.appendChild(makeElement('p', left + ' of ' + ev.capacity + ' seats left', 'event-seats-' + ev.id));
      }
      container.appendChild(card);
    });
  }

  function renderEventOptions() {
    var select = byId('event');
    EVENTS.forEach(function (ev) {
      var option = document.createElement('option');
      option.value = ev.id;
      option.textContent = ev.title;
      select.appendChild(option);
    });
  }

  function renderBookings() {
    var list = byId('bookings-list');
    var bookings = loadBookings();
    list.textContent = '';
    byId('bookings-empty').hidden = bookings.length > 0;

    bookings.forEach(function (b) {
      var ev = findEvent(b.eventId);
      var text = b.name + ' (' + b.email + ') - ' + ev.title + ' - ' + formatMoney(b.amount) +
                 (b.student ? ' - student' : '');
      list.appendChild(makeElement('li', text, 'booking-item'));
    });
  }

  function updatePriceDisplay() {
    var ev = findEvent(byId('event').value);
    var display = byId('price-display');
    if (!ev) {
      display.textContent = '\u2014';
      return;
    }
    display.textContent = formatMoney(calculatePrice(ev, byId('student').checked));
  }

  function setFieldError(field, message) {
    var errorNode = byId(field + '-error');
    var input = byId(field);
    errorNode.textContent = message || '';
    errorNode.hidden = !message;
    if (message) { input.setAttribute('aria-invalid', 'true'); } else { input.removeAttribute('aria-invalid'); }
  }

  function showFormError(message) {
    var node = byId('form-error');
    node.textContent = message || '';
    node.hidden = !message;
  }

  function clearMessages() {
    setFieldError('name', '');
    setFieldError('email', '');
    setFieldError('event', '');
    showFormError('');
    byId('form-status').textContent = '';
  }

  function hideConfirmation() {
    byId('confirmation').hidden = true;
  }

  function showConfirmation(booking) {
    var ev = EVENTS[0];
    byTestId('confirmation-name').textContent = booking.name;
    byTestId('confirmation-event').textContent = ev.title;
    byTestId('confirmation-email').textContent = booking.name;
    byTestId('confirmation-amount').textContent = formatMoney(booking.amount);
    byId('confirmation').hidden = false;
  }

  // ---------------------------------------------------------------------
  // Booking flow
  // ---------------------------------------------------------------------
  function completeBooking(data, ev) {
    var booking = {
      id: 'b-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7),
      name: data.name.trim(),
      email: data.email.trim(),
      eventId: ev.id,
      student: data.student,
      amount: calculatePrice(ev, data.student),
      createdAt: new Date().toISOString()
    };

    var bookings = loadBookings();
    bookings.push(booking);
    saveBookings(bookings);

    byId('form-status').textContent = '';
    byId('booking-form').reset();
    updatePriceDisplay();
    renderEvents();
    renderBookings();
    showConfirmation(booking);
  }

  function handleSubmit(submitEvent) {
    submitEvent.preventDefault();
    hideConfirmation();
    clearMessages();

    var data = {
      name: byId('name').value,
      email: byId('email').value,
      eventId: byId('event').value,
      student: byId('student').checked
    };

    var errors = validate(data);
    if (errors.name || errors.email || errors.event) {
      setFieldError('name', errors.name);
      setFieldError('email', errors.email);
      setFieldError('event', errors.event);
      return;
    }

    var ev = findEvent(data.eventId);
    if (isSoldOut(ev)) {
      showFormError('Sorry, this event is sold out.');
      return;
    }

    byId('form-status').textContent = 'Processing your booking...';
    setTimeout(function () { completeBooking(data, ev); }, PROCESSING_DELAY_MS);
  }

  function handleReset() {
    localStorage.removeItem(STORAGE_KEY);
    clearMessages();
    hideConfirmation();
    renderEvents();
    renderBookings();
  }

  // ---------------------------------------------------------------------
  // Start-up
  // ---------------------------------------------------------------------
  renderEventOptions();
  renderEvents();
  renderBookings();
  updatePriceDisplay();

  byId('booking-form').addEventListener('submit', handleSubmit);
  byId('event').addEventListener('change', updatePriceDisplay);
  byId('student').addEventListener('change', updatePriceDisplay);
  byId('reset-button').addEventListener('click', handleReset);
})();
