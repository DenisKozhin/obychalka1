from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, JSON, UniqueConstraint
from sqlalchemy.orm import relationship

from bot.database.database import Base

# Таблица пользователей
class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)  # Telegram user_id
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    city_id = Column(Integer, ForeignKey("cities.city_id"), nullable=True)
    store_id = Column(Integer, ForeignKey("stores.store_id"), nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Отношения
    city = relationship("City", back_populates="users")
    store = relationship("Store", back_populates="users")
    test_attempts = relationship("TestAttempt", back_populates="user")
    announcement_deliveries = relationship("AnnouncementDelivery", back_populates="user")
    admin_logs = relationship("AdminLog", back_populates="admin")
    articles_created = relationship("Article", foreign_keys="Article.created_by", back_populates="author")
    tests_created = relationship("Test", foreign_keys="Test.created_by", back_populates="author")
    announcements_created = relationship("Announcement", foreign_keys="Announcement.created_by", back_populates="author")

# Таблица городов
class City(Base):
    __tablename__ = "cities"

    city_id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)

    # Отношения
    users = relationship("User", back_populates="city")
    stores = relationship("Store", back_populates="city")

# Таблица магазинов
class Store(Base):
    __tablename__ = "stores"

    store_id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    city_id = Column(Integer, ForeignKey("cities.city_id", ondelete="CASCADE"))

    # Уникальность имени магазина в пределах города
    __table_args__ = (UniqueConstraint('name', 'city_id', name='_store_city_uc'),)

    # Отношения
    city = relationship("City", back_populates="stores")
    users = relationship("User", back_populates="store")

# Категории для библиотеки знаний
class Category(Base):
    __tablename__ = "categories"

    category_id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.category_id", ondelete="SET NULL"), nullable=True)
    level = Column(Integer, nullable=False)  # 1: тип товара, 2: категория, 3: группа товаров

    # Отношения
    parent = relationship("Category", remote_side=[category_id], backref="children")
    articles = relationship("Article", back_populates="category")

# Статьи в библиотеке знаний
class Article(Base):
    __tablename__ = "articles"

    article_id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.category_id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))

    # Отношения
    category = relationship("Category", back_populates="articles")
    images = relationship("ArticleImage", back_populates="article", cascade="all, delete-orphan")
    tests = relationship("Test", back_populates="article", cascade="all, delete-orphan")
    author = relationship("User", foreign_keys=[created_by], back_populates="articles_created")

# Изображения для статей
class ArticleImage(Base):
    __tablename__ = "article_images"

    image_id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.article_id", ondelete="CASCADE"))
    file_id = Column(String(255), nullable=False)  # Telegram file_id
    file_unique_id = Column(String(255), nullable=False)  # Для проверки дубликатов
    position = Column(Integer, nullable=False)  # Порядок отображения

    # Отношения
    article = relationship("Article", back_populates="images")

# Тесты
class Test(Base):
    __tablename__ = "tests"

    test_id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.article_id", ondelete="CASCADE"))
    pass_threshold = Column(Integer, default=80, nullable=False)  # % для прохождения
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))

    # Отношения
    article = relationship("Article", back_populates="tests")
    questions = relationship("Question", back_populates="test", cascade="all, delete-orphan")
    attempts = relationship("TestAttempt", back_populates="test")
    author = relationship("User", foreign_keys=[created_by], back_populates="tests_created")

# Вопросы для тестов
class Question(Base):
    __tablename__ = "questions"

    question_id = Column(Integer, primary_key=True)
    test_id = Column(Integer, ForeignKey("tests.test_id", ondelete="CASCADE"))
    question_text = Column(Text, nullable=False)
    points = Column(Integer, default=1, nullable=False)  # Вес вопроса

    # Отношения
    test = relationship("Test", back_populates="questions")
    answers = relationship("Answer", back_populates="question", cascade="all, delete-orphan")
    user_answers = relationship("UserAnswer", back_populates="question")

# Варианты ответов
class Answer(Base):
    __tablename__ = "answers"

    answer_id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.question_id", ondelete="CASCADE"))
    answer_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    position = Column(Integer, nullable=False)  # Порядок отображения

    # Отношения
    question = relationship("Question", back_populates="answers")
    user_answers = relationship("UserAnswer", back_populates="answer")

# Прохождение тестов пользователями
class TestAttempt(Base):
    __tablename__ = "test_attempts"

    attempt_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"))
    test_id = Column(Integer, ForeignKey("tests.test_id", ondelete="CASCADE"))
    score = Column(Integer, nullable=False)
    is_passed = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Отношения
    user = relationship("User", back_populates="test_attempts")
    test = relationship("Test", back_populates="attempts")
    user_answers = relationship("UserAnswer", back_populates="attempt", cascade="all, delete-orphan")

# Ответы пользователей на вопросы
class UserAnswer(Base):
    __tablename__ = "user_answers"

    user_answer_id = Column(Integer, primary_key=True)
    attempt_id = Column(Integer, ForeignKey("test_attempts.attempt_id", ondelete="CASCADE"))
    question_id = Column(Integer, ForeignKey("questions.question_id", ondelete="CASCADE"))
    answer_id = Column(Integer, ForeignKey("answers.answer_id", ondelete="CASCADE"))
    is_correct = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Отношения
    attempt = relationship("TestAttempt", back_populates="user_answers")
    question = relationship("Question", back_populates="user_answers")
    answer = relationship("Answer", back_populates="user_answers")

# Уведомления/объявления
class Announcement(Base):
    __tablename__ = "announcements"

    announcement_id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))

    # Отношения
    author = relationship("User", foreign_keys=[created_by], back_populates="announcements_created")
    deliveries = relationship("AnnouncementDelivery", back_populates="announcement", cascade="all, delete-orphan")

# Рассылка уведомлений
class AnnouncementDelivery(Base):
    __tablename__ = "announcement_deliveries"

    delivery_id = Column(Integer, primary_key=True)
    announcement_id = Column(Integer, ForeignKey("announcements.announcement_id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"))
    is_delivered = Column(Boolean, default=False)
    delivered_at = Column(DateTime, nullable=True)

    # Отношения
    announcement = relationship("Announcement", back_populates="deliveries")
    user = relationship("User", back_populates="announcement_deliveries")

# Логирование действий администраторов
class AdminLog(Base):
    __tablename__ = "admin_logs"

    log_id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))
    action_type = Column(String(255), nullable=False)  # ADD, EDIT, DELETE, SEND
    entity_type = Column(String(255), nullable=False)  # ARTICLE, TEST, CITY, STORE
    entity_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)  # Дополнительная информация
    created_at = Column(DateTime, default=datetime.utcnow)

    # Отношения
    admin = relationship("User", back_populates="admin_logs")
    