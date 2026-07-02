"""
Register2Park browser automation for visitor vehicle registration.

The automation is intentionally conservative: it stops on CAPTCHA, OTP,
login, payment, or unexpected popup signals and returns a normal failure for
missing fields/buttons or validation problems. It does not try to bypass any
security mechanism.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from playwright.sync_api import (
    Dialog,
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

LocatorFactory = Callable[[], Locator]
AutomationEventCallback = Callable[[str, str, Optional[str]], None]


class RegistrationAutomationError(Exception):
    """Base class for automation errors that should be recorded as failures."""

    def __init__(self, message: str, screenshot_path: Optional[str] = None):
        super().__init__(message)
        self.screenshot_path = screenshot_path


class BlockedByGateError(RegistrationAutomationError):
    """Raised when a CAPTCHA, OTP, login, or payment wall is detected."""


class SelectorNotFoundError(RegistrationAutomationError):
    """Raised when a required form field or button cannot be located."""


class ValidationErrorDetected(RegistrationAutomationError):
    """Raised when the site shows a validation error after submit/next."""


class UnexpectedPopupError(RegistrationAutomationError):
    """Raised when a browser dialog appears during automation."""


@dataclass
class RegistrationInput:
    website_url: str
    apartment_name: str
    apartment_number: str
    email: str
    plate_number: str
    plate_state: str
    vehicle_make: str = ""
    vehicle_model: str = ""
    vehicle_year: Optional[int] = None
    vehicle_color: str = ""

    @property
    def property_name(self) -> str:
        return settings.register2park_property_name or self.apartment_name


@dataclass
class RegistrationResult:
    success: bool
    message: str
    screenshot_path: Optional[str] = None
    confirmation_text: Optional[str] = None
    retryable: bool = True
    email_submitted: bool = False


_BLOCKING_TEXT_MARKERS = [
    "captcha",
    "recaptcha",
    "verify you are human",
    "one-time passcode",
    "one time passcode",
    "enter otp",
    "verification code",
    "sign in",
    "log in",
    "login",
    "payment method",
    "credit card",
    "card number",
    "billing address",
]

_VALIDATION_TEXT_MARKERS = [
    "required",
    "invalid",
    "please enter",
    "please select",
    "does not match",
    "license plates do not match",
]

_SUCCESS_TEXT_MARKERS = [
    "approved for 24 hours",
    "approved to park",
    "registration successful",
    "successfully registered",
    "confirmation",
    "confirmation code",
    "thank you",
    "your vehicle has been registered",
    "guest parking registered",
    "visitor parking registered",
    "permit has been registered",
]

_CAPTCHA_TEXT_MARKERS = [
    "captcha",
    "recaptcha",
    "verify you are human",
]

_CAPTCHA_SELECTORS = [
    "iframe[src*='recaptcha']",
    "iframe[title*='captcha' i]",
    "div.g-recaptcha",
    "div[class*='captcha' i]",
]


def _take_screenshot(page: Page, label: str) -> str:
    settings.screenshot_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    full_path = settings.screenshot_path / f"{label}_{timestamp}.png"
    try:
        page.screenshot(path=str(full_path), full_page=True)
        logger.info("Saved screenshot: %s", full_path)
        return str(full_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to save screenshot for %s: %s", label, exc)
        return ""


def _wait_for_page_ready(page: Page, step_name: str) -> None:
    logger.info("Waiting for page readiness after %s", step_name)
    page.wait_for_load_state("domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PlaywrightTimeoutError:
        logger.info("Network did not become idle after %s; continuing", step_name)


def _body_text(page: Page) -> str:
    try:
        return page.locator("body").inner_text(timeout=3000).lower()
    except Exception:  # noqa: BLE001
        return ""


def _detect_captcha_gate(page: Page) -> Optional[str]:
    body_text = _body_text(page)
    for marker in _CAPTCHA_TEXT_MARKERS:
        if marker in body_text:
            return f"Detected page text matching '{marker}'"

    for selector in _CAPTCHA_SELECTORS:
        try:
            locator = page.locator(selector)
            if locator.count() > 0 and locator.first.is_visible(timeout=500):
                return f"Detected CAPTCHA element matching selector '{selector}'"
        except Exception:  # noqa: BLE001
            continue
    return None


def _detect_blocking_gate(page: Page) -> Optional[str]:
    captcha = _detect_captcha_gate(page)
    if captcha:
        return captcha

    body_text = _body_text(page)
    for marker in _BLOCKING_TEXT_MARKERS:
        if marker in body_text:
            return f"Detected page text matching '{marker}'"
    return None


def _wait_for_manual_captcha_completion(
    page: Page,
    label: str,
    gate: str,
    event_callback: AutomationEventCallback | None,
) -> None:
    screenshot = _take_screenshot(page, f"{label}_captcha_manual_required")
    message = (
        "Manual CAPTCHA completion required. Complete it in the open browser; "
        "automation will resume automatically afterward."
    )
    logger.warning("%s during %s. Pausing automation for manual completion.", gate, label)
    if event_callback:
        event_callback("captcha_paused", message, screenshot)

    started = time.monotonic()
    timeout_seconds = settings.manual_captcha_timeout_seconds
    while time.monotonic() - started < timeout_seconds:
        page.wait_for_timeout(2000)
        try:
            _wait_for_page_ready(page, f"manual captcha check for {label}")
        except Exception:  # noqa: BLE001
            pass

        if _detect_captcha_gate(page) is None or _page_has_registration_content(page):
            resume_screenshot = _take_screenshot(page, f"{label}_captcha_resolved")
            resume_message = "Manual CAPTCHA completed. Automation resumed."
            logger.info("Manual CAPTCHA completed during %s. Resuming automation.", label)
            if event_callback:
                event_callback("captcha_resumed", resume_message, resume_screenshot)
            return

    timeout_screenshot = _take_screenshot(page, f"{label}_captcha_timeout")
    raise BlockedByGateError(
        f"Timed out waiting for manual CAPTCHA completion during {label}",
        timeout_screenshot,
    )


def _assert_no_blocking_gate(
    page: Page,
    label: str,
    event_callback: AutomationEventCallback | None = None,
) -> None:
    captcha = _detect_captcha_gate(page)
    if captcha:
        _wait_for_manual_captcha_completion(page, label, captcha, event_callback)
        return

    gate = _detect_blocking_gate(page)
    if gate:
        screenshot = _take_screenshot(page, f"{label}_blocked")
        raise BlockedByGateError(f"{gate} during {label}", screenshot)


def _detect_validation_error(page: Page) -> Optional[str]:
    body_text = _body_text(page)
    for marker in _VALIDATION_TEXT_MARKERS:
        if marker in body_text:
            return f"Detected validation text matching '{marker}'"
    return None


def _page_has_registration_content(page: Page) -> bool:
    resume_markers = [
        "visitor parking",
        "license plate",
        "plate number",
        "vehicle make",
        "vehicle model",
        "email",
        "confirmation",
    ]
    body_text = _body_text(page)
    return any(marker in body_text for marker in resume_markers)


def _raise_with_screenshot(
    page: Page,
    error_type: type[RegistrationAutomationError],
    message: str,
    label: str,
) -> None:
    screenshot = _take_screenshot(page, label)
    logger.error("%s: %s", label, message)
    raise error_type(message, screenshot)


def _first_visible(candidates: list[tuple[str, LocatorFactory]], timeout_ms: int = 2500) -> tuple[str, Locator]:
    for description, locator_factory in candidates:
        try:
            locator = locator_factory().first
            locator.wait_for(state="visible", timeout=timeout_ms)
            return description, locator
        except Exception:  # noqa: BLE001
            continue
    candidate_names = ", ".join(description for description, _ in candidates)
    raise SelectorNotFoundError(f"None of these selectors became visible: {candidate_names}")


def _click_first(page: Page, label: str, candidates: list[tuple[str, LocatorFactory]]) -> None:
    try:
        description, locator = _first_visible(candidates)
        logger.info("Clicking %s using %s", label, description)
        locator.click()
    except RegistrationAutomationError as exc:
        _raise_with_screenshot(page, SelectorNotFoundError, f"Could not find {label}: {exc}", f"{label}_missing")


def _try_click_first(
    page: Page,
    label: str,
    candidates: list[tuple[str, LocatorFactory]],
    timeout_ms: int = 2500,
) -> bool:
    try:
        description, locator = _first_visible(candidates, timeout_ms=timeout_ms)
        logger.info("Clicking %s using %s", label, description)
        locator.click()
        return True
    except RegistrationAutomationError as exc:
        logger.info("Optional %s was not visible: %s", label, exc)
        return False


def _fill_first(
    page: Page,
    label: str,
    value: str,
    candidates: list[tuple[str, LocatorFactory]],
) -> None:
    try:
        description, locator = _first_visible(candidates)
        logger.info("Filling %s using %s", label, description)
        locator.fill(value)
    except RegistrationAutomationError as exc:
        _raise_with_screenshot(page, SelectorNotFoundError, f"Could not find {label}: {exc}", f"{label}_missing")


def _try_fill_first(
    page: Page,
    label: str,
    value: str,
    candidates: list[tuple[str, LocatorFactory]],
    timeout_ms: int = 2500,
) -> bool:
    try:
        description, locator = _first_visible(candidates, timeout_ms=timeout_ms)
        logger.info("Filling %s using %s", label, description)
        locator.fill(value)
        return True
    except RegistrationAutomationError as exc:
        logger.info("Optional %s was not visible: %s", label, exc)
        return False


def _select_first(
    page: Page,
    label: str,
    value: str,
    candidates: list[tuple[str, LocatorFactory]],
) -> bool:
    try:
        description, locator = _first_visible(candidates)
        logger.info("Selecting %s using %s", label, description)
        try:
            locator.select_option(label=value)
        except Exception:  # noqa: BLE001
            locator.select_option(value=value)
        return True
    except RegistrationAutomationError:
        return False


def open_homepage(
    page: Page,
    data: RegistrationInput,
    event_callback: AutomationEventCallback | None = None,
) -> str:
    logger.info("Opening Register2Park homepage")
    try:
        page.goto(data.website_url or settings.register2park_url, wait_until="domcontentloaded")
        _wait_for_page_ready(page, "homepage load")
        _assert_no_blocking_gate(page, "homepage", event_callback)
        return _take_screenshot(page, "step_1_homepage")
    except RegistrationAutomationError:
        raise
    except Exception as exc:  # noqa: BLE001
        _raise_with_screenshot(page, RegistrationAutomationError, f"Failed to open homepage: {exc}", "homepage_error")


def click_register_vehicle(
    page: Page,
    event_callback: AutomationEventCallback | None = None,
) -> str:
    logger.info("Clicking Register Vehicle")
    _assert_no_blocking_gate(page, "before_register_vehicle", event_callback)
    _click_first(
        page,
        "register_vehicle",
        [
            ("link role named Register Vehicle", lambda: page.get_by_role("link", name=re.compile("register vehicle", re.I))),
            ("button role named Register Vehicle", lambda: page.get_by_role("button", name=re.compile("register vehicle", re.I))),
            ("visible Register Vehicle text", lambda: page.get_by_text(re.compile("register vehicle", re.I))),
            ("href containing register", lambda: page.locator("a[href*='register' i]")),
        ],
    )
    _wait_for_page_ready(page, "register vehicle click")
    _assert_no_blocking_gate(page, "after_register_vehicle", event_callback)
    return _take_screenshot(page, "step_2_register_vehicle")


def select_property(
    page: Page,
    property_name: str,
    event_callback: AutomationEventCallback | None = None,
) -> str:
    logger.info("Selecting property: %s", property_name)
    _assert_no_blocking_gate(page, "before_property_select", event_callback)
    _fill_first(
        page,
        "property search field",
        property_name,
        [
            ("property label", lambda: page.get_by_label(re.compile("property|community|apartment", re.I))),
            ("property placeholder", lambda: page.get_by_placeholder(re.compile("property|community|apartment|search|name", re.I))),
            ("search textbox role", lambda: page.get_by_role("textbox", name=re.compile("property|community|apartment|search", re.I))),
            ("property id/name input", lambda: page.locator("input[id*='property' i], input[name*='property' i], input[type='search']")),
        ],
    )

    suggestion_clicked = _try_click_first(
        page,
        "matching_property_suggestion",
        [
            ("option role with property name", lambda: page.get_by_role("option", name=re.compile(re.escape(property_name), re.I))),
            ("list item with property name", lambda: page.get_by_role("listitem").filter(has_text=re.compile(re.escape(property_name), re.I))),
            ("text matching property name", lambda: page.get_by_text(re.compile(re.escape(property_name), re.I))),
        ],
        timeout_ms=5000,
    )
    if not suggestion_clicked:
        logger.info(
            "No property suggestion appeared for %s; continuing because the search field kept the typed value",
            property_name,
        )

    _click_first(
        page,
        "property_next_button",
        [
            ("button role named Next", lambda: page.get_by_role("button", name=re.compile(r"^next$", re.I))),
            ("link role named Next", lambda: page.get_by_role("link", name=re.compile(r"^next$", re.I))),
            ("input value Next", lambda: page.locator("input[type='submit' i][value*='next' i], input[type='button' i][value*='next' i]")),
        ],
    )
    _wait_for_page_ready(page, "property next")
    _assert_no_blocking_gate(page, "after_property_select", event_callback)

    selected_matching_property = _try_click_first(
        page,
        "matching_property_select_button",
        [
            ("button role named Select", lambda: page.get_by_role("button", name=re.compile(r"^select$", re.I))),
            ("link role named Select", lambda: page.get_by_role("link", name=re.compile(r"^select$", re.I))),
            ("input value Select", lambda: page.locator("input[type='submit' i][value*='select' i], input[type='button' i][value*='select' i]")),
            ("visible Select text", lambda: page.get_by_text(re.compile(r"^select$", re.I))),
        ],
        timeout_ms=3000,
    )
    if selected_matching_property:
        logger.info("Selected matching property confirmation")
        _wait_for_page_ready(page, "matching property select")
        _assert_no_blocking_gate(page, "after_matching_property_select", event_callback)

    return _take_screenshot(page, "step_3_property_selected")


def choose_visitor_parking(
    page: Page,
    event_callback: AutomationEventCallback | None = None,
) -> str:
    logger.info("Choosing Visitor Parking")
    _assert_no_blocking_gate(page, "before_visitor_parking", event_callback)
    _click_first(
        page,
        "visitor_parking",
        [
            ("radio role named Visitor Parking", lambda: page.get_by_role("radio", name=re.compile("visitor parking", re.I))),
            ("button role named Visitor Parking", lambda: page.get_by_role("button", name=re.compile("visitor parking", re.I))),
            ("link role named Visitor Parking", lambda: page.get_by_role("link", name=re.compile("visitor parking", re.I))),
            ("label/text Visitor Parking", lambda: page.get_by_text(re.compile("visitor parking", re.I))),
        ],
    )
    _wait_for_page_ready(page, "visitor parking choice")
    _assert_no_blocking_gate(page, "after_visitor_parking", event_callback)
    return _take_screenshot(page, "step_4_visitor_parking")


def fill_vehicle_information(
    page: Page,
    data: RegistrationInput,
    event_callback: AutomationEventCallback | None = None,
) -> str:
    logger.info("Filling visitor vehicle information")
    _assert_no_blocking_gate(page, "before_vehicle_information", event_callback)

    _fill_first(
        page,
        "apartment number",
        data.apartment_number,
        [
            ("apartment label", lambda: page.get_by_label(re.compile("apartment|unit", re.I))),
            ("apartment placeholder", lambda: page.get_by_placeholder(re.compile("apartment|unit", re.I))),
            ("apartment id/name input", lambda: page.locator("input[id*='apartment' i], input[name*='apartment' i], input[id*='unit' i], input[name*='unit' i]")),
        ],
    )
    _fill_first(
        page,
        "vehicle make",
        data.vehicle_make,
        [
            ("make label", lambda: page.get_by_label(re.compile(r"\bmake\b", re.I))),
            ("make placeholder", lambda: page.get_by_placeholder(re.compile(r"\bmake\b", re.I))),
            ("make id/name input", lambda: page.locator("input[id*='make' i], input[name*='make' i]")),
        ],
    )
    _fill_first(
        page,
        "vehicle model",
        data.vehicle_model,
        [
            ("model label", lambda: page.get_by_label(re.compile(r"\bmodel\b", re.I))),
            ("model placeholder", lambda: page.get_by_placeholder(re.compile(r"\bmodel\b", re.I))),
            ("model id/name input", lambda: page.locator("input[id*='model' i], input[name*='model' i]")),
        ],
    )
    _fill_first(
        page,
        "license plate",
        data.plate_number,
        [
            ("license plate label", lambda: page.get_by_label(re.compile("license plate|plate number|plate", re.I)).first),
            ("license plate placeholder", lambda: page.get_by_placeholder(re.compile("license plate|plate", re.I)).first),
            ("plate id/name input", lambda: page.locator("input[id*='plate' i], input[name*='plate' i]").first),
        ],
    )
    _fill_first(
        page,
        "confirm license plate",
        data.plate_number,
        [
            ("confirm license plate label", lambda: page.get_by_label(re.compile("confirm.*plate|plate.*confirm", re.I))),
            ("confirm license plate placeholder", lambda: page.get_by_placeholder(re.compile("confirm.*plate|plate.*confirm", re.I))),
            ("confirm plate id/name input", lambda: page.locator("input[id*='confirm' i][id*='plate' i], input[name*='confirm' i][name*='plate' i]")),
        ],
    )

    _select_first(
        page,
        "plate state",
        data.plate_state,
        [
            ("state label", lambda: page.get_by_label(re.compile("state", re.I))),
            ("state id/name select", lambda: page.locator("select[id*='state' i], select[name*='state' i]")),
        ],
    )
    return _take_screenshot(page, "step_5_vehicle_information_filled")


def submit_vehicle_information(
    page: Page,
    event_callback: AutomationEventCallback | None = None,
) -> str:
    logger.info("Submitting visitor vehicle information")
    _assert_no_blocking_gate(page, "before_vehicle_next", event_callback)
    _click_first(
        page,
        "vehicle_next_button",
        [
            ("button role named Next", lambda: page.get_by_role("button", name=re.compile(r"^next$", re.I))),
            ("link role named Next", lambda: page.get_by_role("link", name=re.compile(r"^next$", re.I))),
            ("submit input value Next", lambda: page.locator("input[type='submit' i][value*='next' i], input[type='button' i][value*='next' i]")),
            ("button role named Continue", lambda: page.get_by_role("button", name=re.compile("continue", re.I))),
        ],
    )
    _wait_for_page_ready(page, "vehicle information submit")
    _assert_no_blocking_gate(page, "after_vehicle_next", event_callback)
    validation = _detect_validation_error(page)
    if validation:
        _raise_with_screenshot(page, ValidationErrorDetected, validation, "vehicle_validation_error")
    return _take_screenshot(page, "step_5_vehicle_information_submitted")


def enter_email(
    page: Page,
    email: str,
    event_callback: AutomationEventCallback | None = None,
) -> str:
    logger.info("Entering confirmation email")
    _assert_no_blocking_gate(page, "before_email", event_callback)

    email_field_candidates = [
        ("email label", lambda: page.get_by_label(re.compile("email", re.I))),
        ("email placeholder", lambda: page.get_by_placeholder(re.compile("email", re.I))),
        ("email input type", lambda: page.locator("input[type='email']")),
        ("email id/name input", lambda: page.locator("input[id*='email' i], input[name*='email' i]")),
        ("email text input near email text", lambda: page.locator("input[type='text'][id*='email' i], input[type='text'][name*='email' i]")),
    ]

    email_filled = _try_fill_first(
        page,
        "email",
        email,
        email_field_candidates,
        timeout_ms=3000,
    )
    if not email_filled:
        body_text = _body_text(page)
        if any(marker in body_text for marker in _SUCCESS_TEXT_MARKERS):
            logger.info("Registration confirmation is visible; opening E-Mail Confirmation flow")

        _click_first(
            page,
            "email_confirmation_button",
            [
                ("button role named E-Mail Confirmation", lambda: page.get_by_role("button", name=re.compile("e-?mail confirmation", re.I))),
                ("link role named E-Mail Confirmation", lambda: page.get_by_role("link", name=re.compile("e-?mail confirmation", re.I))),
                ("visible E-Mail Confirmation text", lambda: page.get_by_text(re.compile("e-?mail confirmation", re.I))),
            ],
        )
        _wait_for_page_ready(page, "email confirmation click")
        _assert_no_blocking_gate(page, "after_email_confirmation_click", event_callback)
        _fill_first(
            page,
            "email",
            email,
            email_field_candidates,
        )

    _click_first(
        page,
        "email_continue_button",
        [
            ("button role named Next", lambda: page.get_by_role("button", name=re.compile(r"^next$", re.I))),
            ("button role named Continue", lambda: page.get_by_role("button", name=re.compile("continue", re.I))),
            ("button role named Send", lambda: page.get_by_role("button", name=re.compile("send|email|submit|register", re.I))),
            ("link role named Send", lambda: page.get_by_role("link", name=re.compile("send|email|submit|register", re.I))),
            ("submit/send input", lambda: page.locator("input[type='submit' i], input[type='button' i][value*='next' i], input[type='button' i][value*='send' i], input[type='button' i][value*='email' i]")),
        ],
    )
    _wait_for_page_ready(page, "email submit")
    _assert_no_blocking_gate(page, "after_email", event_callback)
    validation = _detect_validation_error(page)
    if validation:
        _raise_with_screenshot(page, ValidationErrorDetected, validation, "email_validation_error")
    return _take_screenshot(page, "step_6_email_submitted")


def verify_registration_success(
    page: Page,
    event_callback: AutomationEventCallback | None = None,
) -> RegistrationResult:
    logger.info("Verifying registration success")
    _assert_no_blocking_gate(page, "success_verification", event_callback)
    screenshot = _take_screenshot(page, "step_7_confirmation")
    body_text = _body_text(page)

    for marker in _SUCCESS_TEXT_MARKERS:
        if marker in body_text:
            confirmation_text = body_text[:1000].strip()
            logger.info("Registration success detected using marker: %s", marker)
            return RegistrationResult(
                success=True,
                message=f"Registration completed at {datetime.utcnow().isoformat()}Z. {confirmation_text}",
                screenshot_path=screenshot,
                confirmation_text=confirmation_text,
            )

    validation = _detect_validation_error(page)
    if validation:
        raise ValidationErrorDetected(validation, screenshot)

    raise RegistrationAutomationError(
        "Registration submission completed, but no known success confirmation text was found.",
        screenshot,
    )


def run_registration(
    data: RegistrationInput,
    headless: Optional[bool] = None,
    timeout_ms: Optional[int] = None,
    event_callback: AutomationEventCallback | None = None,
) -> RegistrationResult:
    """
    Run a single Register2Park visitor vehicle registration attempt.

    Raises BlockedByGateError if a CAPTCHA/OTP/login/payment wall is hit.
    Returns a RegistrationResult describing success or failure otherwise.
    """
    headless = settings.playwright_headless if headless is None else headless
    timeout_ms = settings.playwright_timeout_ms if timeout_ms is None else timeout_ms

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        unexpected_dialog: dict[str, str] = {}

        def on_dialog(dialog: Dialog) -> None:
            unexpected_dialog["message"] = dialog.message
            logger.error("Unexpected browser dialog appeared: %s", dialog.message)
            dialog.dismiss()

        page.on("dialog", on_dialog)

        email_submitted = False
        try:
            if event_callback:
                event_callback("running", "Automation is running.", None)

            open_homepage(page, data, event_callback)
            click_register_vehicle(page, event_callback)
            select_property(page, data.property_name, event_callback)
            choose_visitor_parking(page, event_callback)
            fill_vehicle_information(page, data, event_callback)
            submit_vehicle_information(page, event_callback)
            enter_email(page, data.email, event_callback)
            email_submitted = True

            if unexpected_dialog:
                screenshot = _take_screenshot(page, "unexpected_popup")
                raise UnexpectedPopupError(
                    f"Unexpected popup appeared: {unexpected_dialog['message']}",
                    screenshot,
                )

            return verify_registration_success(page, event_callback)
        except BlockedByGateError as exc:
            logger.error("Blocked by gate: %s", exc)
            raise
        except RegistrationAutomationError as exc:
            logger.error("Registration automation failed: %s", exc)
            if email_submitted:
                message = (
                    "Email confirmation was submitted, but final success could not be "
                    f"verified: {exc}. Automatic retries are paused to avoid sending "
                    "duplicate confirmation emails. Review the latest screenshot/status "
                    "and manually retry only if another email should be sent."
                )
                return RegistrationResult(
                    False,
                    message,
                    exc.screenshot_path,
                    retryable=False,
                    email_submitted=True,
                )
            return RegistrationResult(False, str(exc), exc.screenshot_path)
        except Exception as exc:  # noqa: BLE001
            screenshot = _take_screenshot(page, "unexpected_error")
            logger.exception("Unexpected error during registration automation")
            if email_submitted:
                message = (
                    "Email confirmation was submitted, but an unexpected error occurred "
                    f"before final success was verified: {exc}. Automatic retries are "
                    "paused to avoid sending duplicate confirmation emails."
                )
                return RegistrationResult(
                    False,
                    message,
                    screenshot,
                    retryable=False,
                    email_submitted=True,
                )
            return RegistrationResult(False, str(exc), screenshot)
        finally:
            context.close()
            browser.close()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manually run a Register2Park visitor registration attempt.")
    parser.add_argument("--url", default=settings.register2park_url, dest="website_url")
    parser.add_argument("--property", default=settings.register2park_property_name, dest="apartment_name")
    parser.add_argument("--apartment", required=True, dest="apartment_number")
    parser.add_argument("--email", required=True)
    parser.add_argument("--plate", required=True, dest="plate_number")
    parser.add_argument("--state", required=True, dest="plate_state")
    parser.add_argument("--make", required=True, dest="vehicle_make")
    parser.add_argument("--model", required=True, dest="vehicle_model")
    parser.add_argument("--year", default=None, type=int, dest="vehicle_year")
    parser.add_argument("--color", default="", dest="vehicle_color")
    parser.add_argument("--headless", action="store_true", help="Run Chromium headless; default is visible")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    data = RegistrationInput(
        website_url=args.website_url,
        apartment_name=args.apartment_name,
        apartment_number=args.apartment_number,
        email=args.email,
        plate_number=args.plate_number,
        plate_state=args.plate_state,
        vehicle_make=args.vehicle_make,
        vehicle_model=args.vehicle_model,
        vehicle_year=args.vehicle_year,
        vehicle_color=args.vehicle_color,
    )
    try:
        result = run_registration(data, headless=args.headless)
    except BlockedByGateError as exc:
        print(f"BLOCKED: {exc} screenshot={exc.screenshot_path}")
        return 2

    print(f"success={result.success} message={result.message!r} screenshot={result.screenshot_path}")
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
