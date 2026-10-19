# Campus Event Booking

A hands-on **Software Verification and Validation** practical. The website has **five known defects**. The 27 tests that ship with the project pass anyway, because they do not check those defects. Your team picks one GitHub issue, reproduces the bug, writes a Playwright test that fails because of it, fixes the bug, and opens a pull request.

* **Application:** Campus Event Booking. View events, enter a name and email, book a seat, see the price, and get a confirmation.
* **Stack:** plain HTML, CSS, and JavaScript (no framework and no database), plus Python, pytest, Playwright, and GitHub Actions.
* **Specification:** [`docs/app-spec.md`](docs/app-spec.md) is the source of truth. If the app and the specification disagree, the app is wrong.
* **Test plan:** [`docs/test-plan.md`](docs/test-plan.md)

**Windows 10 and 11 are the primary platform.** Ubuntu instructions are in [section 2](#2-ubuntu). Most classmates should follow section 1 and can skip section 2.

Use a short folder such as `C:\src` on Windows or `~/src` on Ubuntu. Do not put the project inside OneDrive, iCloud, or a network drive. Those folders can lock the many small files inside `.venv`.

---

## 1. Windows 10 and 11

Work in **PowerShell** unless a step says otherwise. Open it from the Start menu by typing `powershell`.

PowerShell 5.1, which is the version built into Windows 10 and 11, does not accept `&&` between commands. Run each command on its own line.

### 1.1 Install Python, Git, and a GitHub account

1. Install **Python 3.12** from the [Windows downloads page](https://www.python.org/downloads/windows/). Under **Stable Releases**, choose the newest **Python 3.12.x** installer. The large download button on the Python home page may offer a newer release. Use 3.12 for this class. On the first installer screen, tick **Add python.exe to PATH**, then choose **Install Now**. If you already have Python 3.10, 3.11, or 3.13, you may keep it. Python 3.9 and older will not work.
2. Install **Git** from <https://git-scm.com/download/win>. The default options are fine. This includes Git Credential Manager, which signs you in to GitHub.
3. Create a free **GitHub** account if you do not have one.

Close PowerShell, open a **new** PowerShell window, and check:

```powershell
python --version
git --version
```

`python --version` must print `Python 3.12.x` (or 3.10, 3.11, or 3.13 if you already had one of those). If `python` opens the Microsoft Store, Python is not really installed yet. See [Troubleshooting](#9-troubleshooting).

Tell Git your name and the email address on your GitHub account. You only do this once per computer:

```powershell
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

Use the quotes. Replace the example name and email with your own.

### 1.2 Get the code

Your instructor will say which path to use. If they have not, use the **fork** path. A fork is your own copy of the repository. You need it so that you can push a branch and open a pull request.

**Fork path (usual)**

1. Open the class repository in a browser while you are signed in to GitHub.
2. Click **Fork**, then **Create fork**. Leave the name as it is.
3. Click the green **Code** button on **your** fork and copy the HTTPS address. It looks like `https://github.com/<YOUR-USERNAME>/<REPO-NAME>.git`.

```powershell
cd C:\src
git clone https://github.com/<YOUR-USERNAME>/<REPO-NAME>.git
cd <REPO-NAME>
```

`cd <REPO-NAME>` means the folder Git just created. Its name matches the repository name.

**Collaborator path (only if your instructor added your GitHub account to the class repository)**

```powershell
cd C:\src
git clone https://github.com/<INSTRUCTOR>/<REPO-NAME>.git
cd <REPO-NAME>
```

If `git push` later says you do not have permission, you cloned the class repository without write access. Go back and fork it.

### 1.3 Create the virtual environment and install Playwright

Run this from the project folder. The prompt must show that folder before you continue.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

If PowerShell says `running scripts is disabled on this system`, run this once, then run the `Activate.ps1` line again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

If `py` is not recognized, create the environment with `python -m venv .venv` instead of `py -3.12 -m venv .venv`.

Prefer Command Prompt? Use `.venv\Scripts\activate.bat` instead of `Activate.ps1`. Every other command stays the same.

What the commands do:

| Command | Meaning |
|---------|---------|
| `py -3.12 -m venv .venv` | Creates a private Python environment in the `.venv` folder |
| `.venv\Scripts\Activate.ps1` | Turns that environment on. The prompt starts with `(.venv)` |
| `python -m pip install -r requirements.txt` | Installs pytest and Playwright |
| `python -m playwright install chromium` | Downloads the Chromium browser Playwright controls (about 150 MB, once) |

The browser download can take a few minutes. Wait until the command finishes.

Every **new** terminal must activate the environment again:

```powershell
cd C:\src\<REPO-NAME>
.venv\Scripts\Activate.ps1
```

### 1.4 Run the tests

```powershell
python -m pytest
```

Success looks like `27 passed` on the last line. The website does not need to be running. The tests start their own temporary server.

### 1.5 Start the website

```powershell
python serve.py
```

Open <http://127.0.0.1:8000> in your browser. Leave this terminal running while you explore. Press `Ctrl+C` to stop the site.

Use `127.0.0.1`, not `localhost`. The server listens only on your own computer, which avoids a Windows Firewall prompt. On some Windows PCs, `localhost` points at IPv6 and the page does not load.

If port 8000 is busy:

```powershell
python serve.py 8001
```

Then open <http://127.0.0.1:8001>.

### 1.6 Create a branch

Do this in a **second** terminal, with `.venv` activated. Do not commit on `main`.

Replace `3` and `student-discount` with your issue number and a short name:

```powershell
git switch -c issue-3-student-discount
```

If `git switch` is not recognized, use `git checkout -b issue-3-student-discount`.

### 1.7 Commit and push

After you have reproduced the bug, added a failing test, fixed it, and seen `python -m pytest` pass:

```powershell
git status
git add -A
git status
git commit -m "Fix #3: student discount"
git push -u origin issue-3-student-discount
```

Read both `git status` listings. You should **not** see `.venv` or `test-results`. Those folders are ignored on purpose.

The first `git push` opens a browser window so you can sign in to GitHub. Sign in there. Do not type your GitHub password into the terminal. If the terminal asks for a password, create a classic personal access token with the **repo** scope at <https://github.com/settings/tokens> and paste the token.

`git commit -m` keeps Git from opening an editor. Put your own issue number in the message. `Fix #3` links the commit to issue 3.

### 1.8 Open a pull request

1. Open your fork on GitHub (or the class repository, if you are a collaborator).
2. If you see a yellow banner **Compare & pull request**, click it. Otherwise open **Pull requests**, then **New pull request**.
3. Set **base repository** to the class repository and **base** to `main`.
4. Set **head repository** to your fork and **compare** to your branch, such as `issue-3-student-discount`. If you pushed straight to the class repository, head and base are the same repository and only the branch differs.
5. Click **Create pull request**. The template appears by itself. Fill it in, including the pytest output from before and after the fix, and keep `Closes #3` with your issue number.
6. Screenshots of the bug and the fix, or a short recording, are appreciated when the defect is visible. You can drag images into the pull request box. A note that your team can demonstrate the fix in class is also fine. The pytest output is still required.
7. Click **Create pull request**.
8. Open the **Actions** tab, or the checks on the pull request. Two jobs must pass: `pytest (windows-latest)` and `pytest (ubuntu-latest)`.

On a fork, GitHub sometimes waits for the instructor to approve the first workflow run. If Actions does not start, say so on the pull request.

---

## 2. Ubuntu

Ubuntu 24.04 includes Python 3.12. Ubuntu 22.04 includes Python 3.10. Both are new enough. Python 3.12 is still the version to use when you can install it. These commands are for Terminal.

### 2.1 Install Python and Git

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
python3 --version
git --version
```

`python3 -m venv` fails until the `python3-venv` package is installed. That is why it is in the command above.

Set your Git name once, using the email on your GitHub account:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

### 2.2 Get the code

Fork the class repository on GitHub first (Fork, then Create fork), unless your instructor added you as a collaborator. Clone **your fork**:

```bash
mkdir -p ~/src
cd ~/src
git clone https://github.com/<YOUR-USERNAME>/<REPO-NAME>.git
cd <REPO-NAME>
```

Collaborators who were told to clone the class repository directly can use `https://github.com/<INSTRUCTOR>/<REPO-NAME>.git` instead.

### 2.3 Create the virtual environment and install Playwright

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install --with-deps chromium
```

`--with-deps` installs system libraries Chromium needs and asks for your sudo password. Activate the environment in every new terminal:

```bash
cd ~/src/<REPO-NAME>
source .venv/bin/activate
```

### 2.4 Run the tests

```bash
python -m pytest
```

Success looks like `27 passed`.

### 2.5 Start the website

```bash
python serve.py
```

Open <http://127.0.0.1:8000>. Press `Ctrl+C` to stop. If port 8000 is busy, run `python serve.py 8001` and open <http://127.0.0.1:8001>.

### 2.6 Create a branch, commit, and push

```bash
git switch -c issue-3-student-discount
git status
git add -A
git commit -m "Fix #3: student discount"
git push -u origin issue-3-student-discount
```

Change `3` and `student-discount` to match your issue. If Git asks for a password, paste a GitHub personal access token, not your GitHub password. Create one at <https://github.com/settings/tokens> with the **repo** scope.

### 2.7 Open a pull request

The GitHub website steps are the same as [section 1.8](#18-open-a-pull-request):

1. Open the fork and use **Compare & pull request**, or **Pull requests** then **New pull request**.
2. Base repository: the class repository. Base: `main`. Compare: your branch.
3. Fill in the template, including before-and-after pytest output and `Closes #<issue number>`.
4. Add screenshots or a short demonstration when they help show the fix.
5. Confirm both Actions jobs are green: `pytest (windows-latest)` and `pytest (ubuntu-latest)`.

---

## 3. Commands you will use often

The environment must be active (`(.venv)` in the prompt). These commands are the same on Windows and Ubuntu.

| Goal | Command |
|------|---------|
| Run everything | `python -m pytest` |
| Show each test name | `python -m pytest -v` |
| One file | `python -m pytest tests/test_smoke.py` |
| Tests whose name contains a word | `python -m pytest -k price` |
| Watch the browser | `python -m pytest --headed --slowmo 500` |
| Stop at the first failure | `python -m pytest -x` |
| Screenshot of each failure | `python -m pytest --screenshot only-on-failure` |
| Record a trace | `python -m pytest --tracing retain-on-failure`, then `python -m playwright show-trace test-results/<test-folder>/trace.zip` |
| Record clicks as test code | `python -m playwright codegen http://127.0.0.1:8000` (the server must be running) |
| Point tests at a server you started | `python -m pytest --base-url http://127.0.0.1:8000` |

Screenshots and traces are saved in `test-results/`, which Git ignores. A failing assertion waits up to 5 seconds, so a run with failures is slower than a clean run.

**The 27 starter tests pass, and the app still has five bugs.** A passing test only proves the behaviour it checks.

---

## 4. Repository layout

```text
app/                           the website (index.html, styles.css, app.js)
tests/
  helpers.py                   helper functions used by the tests
  test_smoke.py                "does the app load?" checks
  test_unaffected_behavior.py  behaviour that already works (your regression safety net)
docs/
  app-spec.md                  expected behaviour, rules V-*, C-*, P-*, F-*, D-*
  test-plan.md                 test approach, traceability, and what to attach to a pull request
.github/workflows/tests.yml    runs the tests on Windows and Ubuntu for every push and pull request
.github/pull_request_template.md
serve.py                       starts the website on your computer
conftest.py                    starts a temporary web server for the tests
pytest.ini                     pytest settings
requirements.txt               pinned Python packages
```

---

## 5. Writing a test

Put the new file in `tests/`, for example `tests/test_issue_3_discount.py`. Every test has three parts: **Arrange** (open the page and fill in the form), **Act** (click), and **Assert** (check what a person sees). Playwright's `expect(...)` waits up to 5 seconds, so you rarely need `sleep`.

```python
from playwright.sync_api import Page, expect
from tests.helpers import book, open_app


def test_valid_booking_shows_confirmation(page: Page):
    open_app(page)
    book(page, "Alice Khan", "alice@example.com", "python-workshop")
    expect(page.get_by_test_id("confirmation-name")).to_have_text("Alice Khan")
```

**Helpers** in `tests/helpers.py`:

| Function | What it does |
|----------|--------------|
| `open_app(page)` | Opens the home page |
| `fill_form(page, name, email, event_id="", student=False)` | Fills the form without submitting |
| `submit_form(page)` | Clicks "Book my seat" once |
| `book(page, name, email, event_id, student=False)` | Fills, submits, and waits for the confirmation |
| `booking_items(page)` | The rows in "My bookings" |
| `seats_label(page, event_id)` | The "N of M seats left" or "Sold out" text of an event |

Find elements with `page.get_by_test_id("...")`. Useful ids: `name-input`, `email-input`, `event-select`, `student-checkbox`, `submit-button`, `price-display`, `form-error`, `name-error`, `email-error`, `confirmation`, `confirmation-name`, `confirmation-event`, `confirmation-email`, `confirmation-amount`, `booking-item`, `event-seats-<event-id>`.

Event ids: `python-workshop`, `hackathon`, `robotics-night`.

---

## 6. Team workflow

1. Comment "we are taking this" on one GitHub issue. Read the issue and the rule ids it names in `docs/app-spec.md`.
2. Set up the project with section 1 or section 2. On a fork, open the **Actions** tab and enable workflows if GitHub asks.
3. Create a branch (section 1.6 or 2.6).
4. Reproduce the defect by hand with `python serve.py` and the steps in the issue. Write down what you see.
5. Write the test first. Cover the acceptance criteria, including a few inputs that should keep working. Test several values, not one lucky value.
6. Run the new test and watch it fail for the right reason. The message should describe the defect, not a typo in the test.
7. Fix only that defect, in `app/app.js`. Keep the change small.
8. Run the new test, then the whole suite (`python -m pytest`). Everything must pass.
9. Commit, push, and open a pull request. The template asks for the before-and-after test output. Screenshots or a short demonstration are appreciated when they make the fix obvious.

### Ground rules

* Do not edit an expected value so that it matches the broken app. If the specification says `$40.00`, the test expects `$40.00`.
* Do not delete, skip, or `xfail` existing tests to get a green result.
* A test you have only seen pass is not evidence yet. It must fail on the unfixed code and pass after your fix.
* Fix only your issue. If you notice another defect, mention it in the pull request and leave it alone.
* Issues 1, 2, and 5 all change the checks that run when someone submits the form. If another team merges first, you may need to update your branch. That conflict is part of the exercise.
* For issue 2, test booking number `capacity + 1`. That is the first booking the specification forbids.
* For issue 4, book Campus Hackathon or Robotics Demo Night. A test that only books Python Workshop can pass while the confirmation defect is still there.

---

## 7. How the app stores data

Bookings are saved in the browser's `localStorage` under the key `svv.campus-events.bookings.v1`. There is no server database. Seat counts survive a reload, a private window starts empty, and every Playwright test starts with no bookings because each test gets a new browser context. **Reset demo data** clears the key. Details are in `docs/app-spec.md`.

---

## 8. What the pull request should contain

The template in `.github/pull_request_template.md` is filled in on GitHub. Reviewers expect:

* the issue number, as `Closes #3`
* what was wrong, in your own words
* pytest output from the failing test **before** the fix
* pytest output showing the full suite **after** the fix
* the acceptance criteria from the issue, ticked

Screenshots of the incorrect screen and the corrected screen, a short screen recording, or a note that you can demonstrate the fix in class are appreciated. Attach them when the bug is something a person can see, such as a wrong price or the wrong confirmation. They support the test output. They do not replace it.

---

## 9. Troubleshooting

| Problem | Fix |
|---------|-----|
| Typing `python` opens the **Microsoft Store** | Install Python 3.12 from python.org with **Add python.exe to PATH** ticked. Then open **Settings → Apps → Advanced app settings → App execution aliases** and turn off `python.exe` and `python3.exe`. Open a new terminal. |
| `py` is not recognized | Use `python -m venv .venv` instead of `py -3.12 -m venv .venv` |
| `running scripts is disabled on this system` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or use Command Prompt and `.venv\Scripts\activate.bat` |
| `Requires-Python >=3.10` or `No matching distribution` | `python --version` is older than 3.10, or you installed a version this project does not use. Install Python 3.12, delete the `.venv` folder, and create it again. |
| `No module named pytest` or `No module named playwright` | The environment is not active. You need `(.venv)` in the prompt. Activate it again. |
| `Executable doesn't exist` at `playwright install` | Run `python -m playwright install chromium`. On Ubuntu, use `python -m playwright install --with-deps chromium`. |
| `ensurepip is not available` (Ubuntu) | `sudo apt install python3-venv`, delete `.venv`, and create it again |
| `No module named 'tests'` | Run `python -m pytest` from the project folder, not from inside `tests/` |
| The page does not load | Open <http://127.0.0.1:8000>, not `localhost`. The server must still be running. |
| `Could not start on port 8000` | `python serve.py 8001` and open <http://127.0.0.1:8001> |
| A test hangs, then fails after 5 seconds | Read the **Call log** in the output. It names the element Playwright was waiting for. |
| `git push` says **Permission denied** or **403** | You cloned the class repository instead of your fork, or you are not signed in. Fork the repository, clone the fork, and push again. Sign in through the browser window. |
| Git asks for a password | Paste a personal access token, not your GitHub password. Create one at <https://github.com/settings/tokens>. |
| `Please tell me who you are` during commit | Run the `git config --global user.name` and `user.email` commands in section 1.1 or 2.1 |
| GitHub Actions did not start on a fork | Open the fork's **Actions** tab and enable workflows. The instructor may also need to approve the first run from your account. |
| Git says `LF will be replaced by CRLF` | Harmless on Windows. `.gitattributes` keeps line endings consistent. |
| Playwright says the path is too long (Windows) | Move the project to a short path such as `C:\src\<REPO-NAME>` and install again |
