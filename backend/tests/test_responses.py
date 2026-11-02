MSG = "Здравствуйте! Мне интересен ваш проект, есть релевантный опыт."


def _respond(member, post_id, message=MSG):
    return member.post(f"/api/posts/{post_id}/responses", {"message": message})


def test_full_flow_respond_review_accept_reveals_contacts(author, applicant):
    post = author.create_post(kind="vacancy", title="Backend-разработчик")

    r = _respond(applicant, post["id"])
    assert r.status_code == 201
    response = r.json()
    assert response["status"] == "pending" and response["author_contact"] is None

    # Feed and detail show the applicant's own response status.
    item = applicant.get("/api/posts").json()["items"][0]
    assert item["my_response"]["status"] == "pending"

    # Author sees the response, but not the applicant's contact yet.
    received = author.get("/api/me/responses/received").json()
    assert len(received) == 1 and received[0]["message"] == MSG
    assert received[0]["applicant"]["contact"] is None
    assert author.get(f"/api/posts/{post['id']}/responses").json()[0]["id"] == response["id"]

    r = author.post(f"/api/responses/{response['id']}/decision", {"status": "accepted", "note": "Созвонимся!"})
    assert r.status_code == 200
    assert r.json()["applicant"]["contact"] == "@applicant_tg"

    sent = applicant.get("/api/me/responses/sent").json()[0]
    assert sent["status"] == "accepted"
    assert sent["author_note"] == "Созвонимся!"
    assert sent["author_contact"] == "@author_tg"
    detail = applicant.get(f"/api/posts/{post['id']}").json()
    assert detail["my_response"]["author_contact"] == "@author_tg"


def test_duplicate_response_is_conflict(author, applicant):
    post = author.create_post()
    assert _respond(applicant, post["id"]).status_code == 201
    assert _respond(applicant, post["id"]).status_code == 409


def test_cannot_respond_to_own_post(author):
    post = author.create_post()
    assert _respond(author, post["id"]).status_code == 403


def test_cannot_respond_to_paused_or_missing_post(author, applicant):
    post = author.create_post()
    author.patch(f"/api/posts/{post['id']}", {"status": "paused"})
    assert _respond(applicant, post["id"]).status_code == 409
    assert _respond(applicant, 999999).status_code == 404


def test_response_message_is_required(author, applicant):
    post = author.create_post()
    assert _respond(applicant, post["id"], "   hi    ").status_code == 422


def test_withdraw_and_reapply(author, applicant):
    post = author.create_post()
    rid = _respond(applicant, post["id"]).json()["id"]

    assert author.post(f"/api/responses/{rid}/withdraw").status_code == 404  # not author's
    r = applicant.post(f"/api/responses/{rid}/withdraw")
    assert r.status_code == 200 and r.json()["status"] == "withdrawn"
    assert author.get("/api/me/responses/received").json() == []  # withdrawn hidden from author
    assert applicant.post(f"/api/responses/{rid}/withdraw").status_code == 409

    r = _respond(applicant, post["id"], "Передумал, всё-таки очень интересно!")
    assert r.status_code == 201
    assert r.json()["id"] == rid and r.json()["status"] == "pending"


def test_only_author_decides_and_only_once(author, applicant, make_member):
    post = author.create_post()
    rid = _respond(applicant, post["id"]).json()["id"]
    stranger = make_member()

    assert stranger.post(f"/api/responses/{rid}/decision", {"status": "accepted"}).status_code == 403
    assert applicant.post(f"/api/responses/{rid}/decision", {"status": "accepted"}).status_code == 403
    assert stranger.get(f"/api/posts/{post['id']}/responses").status_code == 403

    assert author.post(f"/api/responses/{rid}/decision", {"status": "rejected"}).status_code == 200
    assert author.post(f"/api/responses/{rid}/decision", {"status": "accepted"}).status_code == 409
    # Rejected cannot be withdrawn, nor re-submitted.
    assert applicant.post(f"/api/responses/{rid}/withdraw").status_code == 409
    assert _respond(applicant, post["id"]).status_code == 409

    sent = applicant.get("/api/me/responses/sent").json()[0]
    assert sent["status"] == "rejected" and sent["author_contact"] is None


def test_closing_post_rejects_pending_but_keeps_accepted(author, applicant, make_member):
    post = author.create_post()
    accepted_id = _respond(applicant, post["id"]).json()["id"]
    author.post(f"/api/responses/{accepted_id}/decision", {"status": "accepted"})
    other = make_member()
    pending_id = _respond(other, post["id"]).json()["id"]

    assert author.patch(f"/api/posts/{post['id']}", {"status": "closed"}).status_code == 200

    statuses = {r["id"]: r["status"] for r in author.get("/api/me/responses/received").json()}
    assert statuses == {accepted_id: "accepted", pending_id: "rejected"}
    # The applicant still sees the closed post they responded to.
    detail = other.get(f"/api/posts/{post['id']}")
    assert detail.status_code == 200 and detail.json()["status"] == "closed"


def test_received_responses_filter_by_status(author, applicant, make_member):
    post = author.create_post()
    rid = _respond(applicant, post["id"]).json()["id"]
    _respond(make_member(), post["id"])
    author.post(f"/api/responses/{rid}/decision", {"status": "accepted"})

    pending = author.get("/api/me/responses/received", params={"status": "pending"}).json()
    accepted = author.get("/api/me/responses/received", params={"status": "accepted"}).json()
    assert len(pending) == 1 and [r["id"] for r in accepted] == [rid]
