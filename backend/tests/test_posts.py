def test_create_post_validation(author):
    r = author.post("/api/posts", {"kind": "startup", "title": "ab", "summary": "short"})
    assert r.status_code == 422
    r = author.post("/api/posts", {"kind": "job", "title": "Title", "summary": "Long enough summary"})
    assert r.status_code == 422


def test_created_post_appears_in_others_feed_not_own(author, applicant):
    post = author.create_post(title="Сервис доставки")
    assert post["status"] == "active" and post["is_own"]

    feed = applicant.get("/api/posts").json()
    assert [p["id"] for p in feed["items"]] == [post["id"]]
    assert feed["items"][0]["is_own"] is False
    assert feed["items"][0]["responses_total"] is None  # counters are author-only

    assert author.get("/api/posts").json()["total"] == 0
    assert author.get("/api/posts", params={"include_own": True}).json()["total"] == 1


def test_feed_filters_search_and_pagination(author, applicant):
    author.create_post(kind="startup", title="AgroTech сенсоры", skills=["IoT"])
    author.create_post(kind="vacancy", title="Python разработчик", skills=["Python", "FastAPI"])
    author.create_post(kind="vacancy", title="Дизайнер", summary="Нужен дизайнер интерфейсов", skills=["Figma"])

    assert applicant.get("/api/posts", params={"kind": "vacancy"}).json()["total"] == 2
    assert applicant.get("/api/posts", params={"kind": "startup"}).json()["total"] == 1

    found = applicant.get("/api/posts", params={"q": "интерфейс"}).json()["items"]
    assert [p["title"] for p in found] == ["Дизайнер"]
    assert applicant.get("/api/posts", params={"q": "fastapi"}).json()["total"] == 1  # searches skills
    assert applicant.get("/api/posts", params={"q": "100%"}).json()["total"] == 0  # % is escaped

    assert applicant.get("/api/posts", params={"skill": "python"}).json()["total"] == 1

    page1 = applicant.get("/api/posts", params={"page_size": 2, "page": 1}).json()
    page2 = applicant.get("/api/posts", params={"page_size": 2, "page": 2}).json()
    assert page1["total"] == 3 and len(page1["items"]) == 2 and len(page2["items"]) == 1
    assert page1["items"][0]["title"] == "Дизайнер"  # newest first


def test_vacancy_can_link_only_to_own_startup(author, applicant):
    startup = author.create_post(kind="startup", title="Мой стартап")
    vacancy = author.create_post(kind="vacancy", title="CTO", startup_id=startup["id"])
    assert vacancy["startup"]["id"] == startup["id"]

    r = applicant.post(
        "/api/posts",
        {"kind": "vacancy", "title": "Чужой", "summary": "Попытка привязки к чужому", "startup_id": startup["id"]},
    )
    assert r.status_code == 422
    r = author.post(
        "/api/posts",
        {"kind": "startup", "title": "Стартап", "summary": "Стартап к стартапу нельзя", "startup_id": startup["id"]},
    )
    assert r.status_code == 422

    detail = applicant.get(f"/api/posts/{startup['id']}").json()
    assert [v["id"] for v in detail["vacancies"]] == [vacancy["id"]]


def test_only_author_can_edit(author, applicant):
    post = author.create_post()
    assert applicant.patch(f"/api/posts/{post['id']}", {"title": "Взлом"}).status_code == 403
    r = author.patch(f"/api/posts/{post['id']}", {"title": "Новое название", "stage": "growth"})
    assert r.status_code == 200
    assert r.json()["title"] == "Новое название" and r.json()["stage"] == "growth"


def test_paused_post_hidden_from_feed_and_closed_is_final(author, applicant):
    post = author.create_post()
    assert author.patch(f"/api/posts/{post['id']}", {"status": "paused"}).status_code == 200
    assert applicant.get("/api/posts").json()["total"] == 0
    assert applicant.get(f"/api/posts/{post['id']}").status_code == 404

    assert author.patch(f"/api/posts/{post['id']}", {"status": "active"}).status_code == 200
    assert applicant.get("/api/posts").json()["total"] == 1

    assert author.patch(f"/api/posts/{post['id']}", {"status": "closed"}).status_code == 200
    assert author.patch(f"/api/posts/{post['id']}", {"status": "active"}).status_code == 409
    assert author.patch(f"/api/posts/{post['id']}", {"title": "Ещё правка"}).status_code == 409


def test_my_posts_include_response_counters(author, applicant, make_member):
    post = author.create_post()
    other = make_member()
    applicant.post(f"/api/posts/{post['id']}/responses", {"message": "Хочу присоединиться к команде"})
    other.post(f"/api/posts/{post['id']}/responses", {"message": "Тоже интересно, есть опыт"})

    mine = author.get("/api/me/posts").json()
    assert mine[0]["responses_total"] == 2 and mine[0]["responses_pending"] == 2


def test_feed_filters_by_format_stage_and_compensation(author, applicant):
    mvp = author.create_post(kind="startup", title="MVP-стартап", stage="mvp", work_format="remote")
    author.create_post(kind="startup", title="Идея", stage="idea", work_format="office")
    author.create_post(kind="vacancy", title="Вакансия MVP", startup_id=mvp["id"], work_format="remote",
                       compensation="150 тыс. ₽")
    author.create_post(kind="vacancy", title="Без условий", work_format="hybrid", compensation="   ")

    titles = lambda **p: sorted(x["title"] for x in applicant.get("/api/posts", params=p).json()["items"])  # noqa: E731
    assert titles(work_format="remote") == ["MVP-стартап", "Вакансия MVP"]
    # a vacancy inherits the stage of its startup
    assert titles(stage="mvp") == ["MVP-стартап", "Вакансия MVP"]
    assert titles(with_compensation=True) == ["Вакансия MVP"]
    assert titles(kind="vacancy", work_format="hybrid") == ["Без условий"]
    assert applicant.get("/api/posts", params={"work_format": "moon"}).status_code == 422
