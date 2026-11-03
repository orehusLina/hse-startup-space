"""End-to-end: the main scenario in a real browser against a running app with fresh demo data.

    BASE_URL=http://localhost:8000 pytest e2e

Boris responds to Dina's startup → Dina accepts in her cabinet → both see each other's contacts.
"""

import os
import re

import pytest
from playwright.sync_api import Page, expect, sync_playwright

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
MESSAGE = "Здравствуйте! 6 лет делаю бэкенд платёжных сервисов, могу взять интеграции."


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    # Outside Telegram the WebApp script is not needed; keep tests independent of telegram.org.
    ctx.route("**/telegram.org/**", lambda r: r.fulfill(body="", content_type="text/javascript"))
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    yield pg
    ctx.close()
    assert errors == [], f"JS errors on the page: {errors}"


def login(page: Page, name: str) -> None:
    page.goto(BASE_URL + "/")
    page.get_by_role("button", name=re.compile(name)).click()
    expect(page.locator(".pcard").first).to_be_visible()


def test_respond_accept_and_reveal_contacts(page: Page):
    login(page, "Борис Ким")
    page.get_by_text("Podpiska.club").first.click()
    page.locator("#applyBtn").click()
    page.locator(".sheet textarea").fill(MESSAGE)
    page.locator(".sheet").get_by_role("button", name=re.compile("Отправить")).click()
    expect(page.locator(".steps")).to_be_visible()
    expect(page.get_by_text("На рассмотрении").first).to_be_visible()

    # Author side
    page.goto(BASE_URL + "/#/me/profile")
    page.locator("#logout").click()
    login(page, "Дина Ахмедова")
    page.goto(BASE_URL + "/#/me/received")
    card = page.locator("#rl .card", has_text=MESSAGE)
    expect(card).to_be_visible()
    expect(card.locator(".reveal")).to_have_count(0)  # contact hidden before the decision
    card.locator(".note").fill("Давайте созвонимся!")
    card.get_by_role("button", name=re.compile("Принять")).click()
    page.locator("#rf button[data-v=accepted]").click()
    expect(page.locator("#rl .reveal", has_text="@boris_kim")).to_be_visible()

    # Applicant sees the author's contact and the note
    page.goto(BASE_URL + "/#/me/profile")
    page.locator("#logout").click()
    login(page, "Борис Ким")
    page.goto(BASE_URL + "/#/me/sent")
    sent = page.locator("#tab .card", has_text="Podpiska.club")
    expect(sent.locator(".badge")).to_have_text("Принят")
    expect(sent.get_by_text("Давайте созвонимся!")).to_be_visible()
    expect(sent.locator(".reveal")).to_contain_text("+7 900 000-00-05")


def test_for_you_and_filters(page: Page):
    login(page, "Вера Орлова")
    page.locator("#kinds button[data-v=match]").click()
    expect(page.locator(".pill-meta.match").first).to_contain_text("Совпадает")
    page.locator("#kinds button[data-v='']").click()
    page.locator("#filtersBtn").click()
    page.locator(".fchips[data-key=work_format] .chip[data-v=office]").click()
    page.locator("#fApply").click()
    expect(page.locator("#fCount")).to_have_text("1")
    for fmt in page.locator(".pcard .pill-meta", has_text="📍").all_inner_texts():
        assert "Офис" in fmt


XSS = '<img src=x onerror="window.__pwned=1">Стартап'


def test_user_content_is_rendered_as_text_not_html(page: Page):
    """A post title with markup must show up literally and never execute in another member's browser."""
    login(page, "Глеб Иванов")
    page.goto(BASE_URL + "/#/new")
    page.locator("input[name=title]").fill(XSS)
    page.locator("textarea[name=summary]").fill('Описание с "кавычками" и <b>тегами</b> внутри')
    page.locator("input[name=skills]").fill("<svg onload=alert(1)>, Python")
    page.locator("#submitBtn").click()
    expect(page.locator(".cover h1")).to_have_text(XSS)

    page.goto(BASE_URL + "/#/me/profile")
    page.locator("#logout").click()
    login(page, "Вера Орлова")
    card = page.locator(".pcard", has_text="Стартап").first
    expect(card.locator("h3")).to_have_text(XSS)
    card.click()
    expect(page.locator(".cover h1")).to_have_text(XSS)
    assert page.evaluate("window.__pwned") is None
    assert page.locator(".cover img, .pcard img").count() == 0
