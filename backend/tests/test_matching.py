def test_match_label_on_feed_cards(make_member):
    author = make_member("Author")
    viewer = make_member("Viewer", skills=["python", "Docker"])
    author.create_post(title="Бэкенд", skills=["Python", "PostgreSQL", "Docker"])
    author.create_post(title="Без навыков", skills=[])

    items = {p["title"]: p for p in viewer.get("/api/posts").json()["items"]}
    assert items["Бэкенд"]["match"] == {"matched": ["Python", "Docker"], "total": 3}
    assert items["Без навыков"]["match"] is None


def test_for_you_feed_ranks_by_shared_skills(make_member):
    author = make_member("Author")
    viewer = make_member("Viewer", skills=["Python", "SQL", "Figma"])
    author.create_post(title="Одно совпадение", skills=["Python", "Go"])
    author.create_post(title="Два совпадения", skills=["Python", "SQL"])
    author.create_post(title="Мимо", skills=["Rust"])

    page = viewer.get("/api/posts", params={"sort": "match"}).json()
    assert [p["title"] for p in page["items"]] == ["Два совпадения", "Одно совпадение"]
    assert page["total"] == 2  # posts without shared skills are not "for you"

    paged = viewer.get("/api/posts", params={"sort": "match", "page_size": 1, "page": 2}).json()
    assert [p["title"] for p in paged["items"]] == ["Одно совпадение"]


def test_for_you_is_empty_without_profile_skills(make_member):
    make_member("Author").create_post(skills=["Python"])
    assert make_member("Newbie").get("/api/posts", params={"sort": "match"}).json()["total"] == 0


def test_author_sees_how_applicant_fits(make_member):
    author = make_member("Author")
    applicant = make_member("Applicant", skills=["Python"])
    post = author.create_post(skills=["Python", "Kafka"])
    applicant.post(f"/api/posts/{post['id']}/responses", {"message": "Хочу в команду, есть опыт"})
    received = author.get("/api/me/responses/received").json()[0]
    assert received["match"] == {"matched": ["Python"], "total": 2}


def test_candidates_suggest_fitting_members_and_invite_once(make_member, sent):
    author = make_member("Author")
    strong = make_member("Strong", skills=["Python", "SQL"], telegram_id=101)
    weak = make_member("Weak", skills=["SQL"])
    make_member("Other", skills=["Figma"])
    responded = make_member("Responded", skills=["Python", "SQL"])
    post = author.create_post(skills=["Python", "SQL"])
    responded.post(f"/api/posts/{post['id']}/responses", {"message": "Уже откликаюсь на проект"})

    cands = author.get(f"/api/posts/{post['id']}/candidates").json()
    assert [c["user"]["full_name"] for c in cands] == ["Strong", "Weak"]  # responded & unmatched excluded
    assert cands[0]["can_notify"] is True and cands[1]["can_notify"] is False
    assert "contact" not in cands[0]["user"]  # suggestions never leak contacts

    r = author.post(f"/api/posts/{post['id']}/invite/{strong.user.id}")
    assert r.status_code == 200 and r.json() == {"invited": True, "notified": True}
    assert sent[-1]["chat_id"] == 101 and "приглашает вас откликнуться" in sent[-1]["text"]
    assert author.post(f"/api/posts/{post['id']}/invite/{strong.user.id}").status_code == 409
    assert author.get(f"/api/posts/{post['id']}/candidates").json()[0]["invited"] is True

    # the invited member sees it on the card
    assert strong.get(f"/api/posts/{post['id']}").json()["invited"] is True
    # only the author can use it, and not for people who already responded
    assert strong.get(f"/api/posts/{post['id']}/candidates").status_code == 403
    assert author.post(f"/api/posts/{post['id']}/invite/{responded.user.id}").status_code == 409
    assert author.post(f"/api/posts/{post['id']}/invite/{author.user.id}").status_code == 404
