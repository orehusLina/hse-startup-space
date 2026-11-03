"""Demo data: test accounts, publications and responses in every status.

Idempotent: does nothing if users already exist. Run: `python -m app.seed`.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

DEMO_PASSWORD = "demo1234"

DEMO_USERS = [
    {
        "email": "anna@club.test",
        "avatar_emoji": "📚",
        "full_name": "Анна Смирнова",
        "headline": "Основатель EdTech-стартапа",
        "city": "Москва",
        "bio": "10 лет в образовании, запускаю платформу для корпоративного обучения.",
        "skills": ["Product", "EdTech", "Fundraising", "SaaS"],
        "contact": "@anna_smirnova",
    },
    {
        "email": "boris@club.test",
        "avatar_emoji": "💻",
        "full_name": "Борис Ким",
        "headline": "Backend-разработчик, Python",
        "city": "Санкт-Петербург",
        "bio": "6 лет в финтехе. Ищу проект на стадии MVP с долей.",
        "skills": ["Python", "PostgreSQL", "FastAPI", "Docker", "Payments"],
        "contact": "@boris_kim",
    },
    {
        "email": "vera@club.test",
        "avatar_emoji": "🎨",
        "full_name": "Вера Орлова",
        "headline": "Продуктовый дизайнер",
        "city": "Казань",
        "bio": "Делаю интерфейсы для B2B-сервисов, люблю исследования.",
        "skills": ["Figma", "UX Research", "Design Systems"],
        "contact": "@vera_design",
    },
    {
        "email": "gleb@club.test",
        "avatar_emoji": "🌱",
        "full_name": "Глеб Иванов",
        "headline": "Серийный предприниматель, AgroTech",
        "city": "Краснодар",
        "bio": "Два экзита в ритейле, сейчас — сенсоры для теплиц.",
        "skills": ["Sales", "Hardware", "B2B"],
        "contact": "@gleb_agro",
    },
    {
        "email": "dina@club.test",
        "avatar_emoji": "📣",
        "full_name": "Дина Ахмедова",
        "headline": "Маркетолог, growth",
        "city": "Москва",
        "bio": "Растила две подписочные модели с нуля до 100k MAU.",
        "skills": ["Marketing", "Growth", "Analytics"],
        "contact": "+7 900 000-00-05",
    },
]


def seed(db: Session) -> bool:
    from .models import Post, Response, User
    from .security import hash_password

    if db.scalar(select(User.id).limit(1)) is not None:
        return False

    users = {}
    for data in DEMO_USERS:
        user = User(password_hash=hash_password(DEMO_PASSWORD), **data)
        db.add(user)
        users[data["email"].split("@")[0]] = user
    db.flush()

    now = datetime.now(UTC)

    def post(author: str, days_ago: float, **fields) -> Post:
        p = Post(
            author_id=users[author].id,
            created_at=now - timedelta(days=days_ago),
            updated_at=now - timedelta(days=days_ago),
            **fields,
        )
        db.add(p)
        db.flush()
        return p

    learnly = post(
        "anna", 9,
        kind="startup", title="Learnly — микрообучение для команд",
        summary="Платформа коротких уроков в мессенджерах для онбординга сотрудников.",
        description="Пилоты в 3 компаниях, 1200 активных учеников. Готовим seed-раунд.",
        looking_for="CTO с долей, инвестора на seed, пилотных клиентов из розницы.",
        skills=["EdTech", "B2B", "Python"], stage="mvp", work_format="hybrid",
        compensation="Доля 5–10%",
    )
    greenbox = post(
        "gleb", 7,
        kind="startup", title="GreenBox — умные сенсоры для теплиц",
        summary="IoT-датчики и прогноз урожая для фермерских хозяйств юга России.",
        description="Собран прототип, 2 хозяйства тестируют. Ищем партнёров и деньги.",
        looking_for="Embedded-инженера, data scientist, инвестора.",
        skills=["IoT", "Hardware", "ML"], stage="idea", work_format="office",
        compensation="Доля / обсуждается",
    )
    post(
        "dina", 3,
        kind="startup", title="Podpiska.club — подписки для локального бизнеса",
        summary="Конструктор подписок для кофеен и салонов: оплата, лояльность, аналитика.",
        description="Выручка 300 тыс. ₽/мес, 40 заведений. Растём через партнёров.",
        looking_for="Партнёров по продажам в регионах, frontend-разработчика.",
        skills=["SaaS", "Marketing", "Payments"], stage="early_revenue", work_format="remote",
        compensation="Доля + revenue share",
    )
    cto = post(
        "anna", 8,
        kind="vacancy", startup_id=learnly.id, title="CTO / ведущий backend-разработчик",
        summary="Ищем технического партнёра, который возьмёт архитектуру и команду.",
        description="Стек: Python, PostgreSQL, Telegram Bot API. Сейчас 2 подрядчика.",
        looking_for="5+ лет backend, опыт построения команды, готовность к доле.",
        skills=["Python", "PostgreSQL", "Leadership"], work_format="hybrid",
        compensation="150–200 тыс. ₽ + доля",
    )
    designer = post(
        "anna", 5,
        kind="vacancy", startup_id=learnly.id, title="Продуктовый дизайнер (part-time)",
        summary="Нужен дизайнер на редизайн кабинета администратора, 20 ч/неделю.",
        looking_for="Портфолио B2B-продуктов, Figma, умение проводить интервью.",
        skills=["Figma", "UX Research"], work_format="remote",
        compensation="120 тыс. ₽ за проект",
    )
    embedded = post(
        "gleb", 6,
        kind="vacancy", startup_id=greenbox.id, title="Embedded-инженер",
        summary="Доработка прошивки датчиков влажности и энергопотребления.",
        skills=["C", "ESP32", "Hardware"], work_format="office",
        compensation="от 180 тыс. ₽",
    )
    post(
        "boris", 2,
        kind="vacancy", title="Ищу кофаундера-продажника в финтех-проект",
        summary="Делаю сервис сверки платежей для малого бизнеса, нужен партнёр по продажам.",
        looking_for="Опыт B2B-продаж, сеть контактов среди бухгалтеров.",
        skills=["Sales", "B2B", "FinTech"], work_format="remote",
        compensation="Доля 20–30%",
    )
    post(
        "vera", 1,
        kind="vacancy", title="Нужен frontend-разработчик в дизайн-студию",
        summary="Вёрстка лендингов и интерфейсов по готовым макетам, проектная загрузка.",
        skills=["React", "TypeScript", "CSS"], work_format="remote",
        compensation="2 500 ₽/час",
    )
    post(
        "dina", 12,
        kind="vacancy", title="Аналитик на исследование рынка (закрыто)",
        summary="Разовое исследование рынка подписок в HoReCa. Уже нашли исполнителя.",
        skills=["Analytics"], work_format="remote", compensation="60 тыс. ₽",
        status="closed",
    )

    def respond(applicant: str, target: Post, message: str, status: str = "pending", note: str = ""):
        db.add(
            Response(
                post_id=target.id,
                applicant_id=users[applicant].id,
                message=message,
                status=status,
                author_note=note,
                decided_at=now if status in {"accepted", "rejected"} else None,
            )
        )

    respond("boris", cto, "Здравствуйте! 6 лет Python в финтехе, вёл команду из 4 человек. Интересна доля.")
    respond("vera", designer, "Делала редизайн LMS для крупного банка, могу показать кейс.", "accepted",
            "Отлично, давайте созвонимся на этой неделе!")
    respond("boris", greenbox, "Могу помочь с backend и обработкой телеметрии.", "rejected",
            "Спасибо! Пока ищем именно embedded-специалиста.")
    respond("dina", learnly, "Готова помочь с go-to-market в рознице, есть контакты.")
    respond("vera", greenbox, "Интересно сделать дашборд для фермеров, есть опыт в AgroTech.", "withdrawn")
    db.commit()
    return True


def main() -> None:
    from .db import SessionLocal, init_db

    init_db()
    with SessionLocal() as db:
        print("Seeded demo data" if seed(db) else "Database already has data, seed skipped")


if __name__ == "__main__":
    main()
