from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    BigInteger,
    DateTime,
    Date,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(BigInteger, primary_key=True)  # Telegram ID
    username = Column(String)
    balance = Column(Integer, default=0)  # Внутренний баланс
    created_at = Column(DateTime, default=datetime.now)
    language_code = Column(String, default="en")
    is_trial_used = Column(Boolean, default=False)
    referrer_id = Column(BigInteger, nullable=True)  # 邀请人ID
    referral_count = Column(Integer, default=0)  # 成功邀请数
    referral_earnings = Column(Integer, default=0)  # 累计返佣余额

    # Связи
    subscriptions = relationship("Subscription", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")
    daily_stats = relationship("UserDailyStat", back_populates="user")

class Server(Base):
    __tablename__ = 'servers'
    
    id = Column(Integer, primary_key=True)
    name = Column(String)  # Например "Netherlands-1"
    ip_address = Column(String)
    api_url = Column(String)  # Ссылка на API Marzban
    api_credentials = Column(JSON)  # Логин/пароль админа панели
    location = Column(String)  # "NL", "DE"
    max_users = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)

    # Связи
    subscriptions = relationship("Subscription", back_populates="server")
    daily_stats = relationship("UserDailyStat", back_populates="server")

class Plan(Base):
    __tablename__ = 'plans'
    
    id = Column(Integer, primary_key=True)
    name = Column(String)  # "1 Месяц - Скорость Макс"
    price = Column(Integer)  # Цена в рублях/звездах
    duration_days = Column(Integer)  # 30, 90...
    traffic_limit_gb = Column(Integer)  # 0 = безлимит

    # Связи
    subscriptions = relationship("Subscription", back_populates="plan")

class Subscription(Base):
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'))
    server_id = Column(Integer, ForeignKey('servers.id'))
    plan_id = Column(Integer, ForeignKey('plans.id'))
    
    marzban_username = Column(String)  # Логин в панели Marzban
    uuid = Column(String)  # Уникальный ключ
    vless_key = Column(String)  # Сама строка подключения vless://...
    subscription_url = Column(String, nullable=True)
    plan_type = Column(String, default='time')  # 'time' 时间套餐 / 'traffic' 流量包
    traffic_gb = Column(Integer, default=0)  # 流量包GB数
    
    status = Column(String)  # 'active', 'expired', 'banned'
    expires_at = Column(DateTime)  # Когда отключать
    last_traffic_usage = Column(BigInteger, default=0)  # Последнее зафиксированное значение трафика (байт)
    device_limit = Column(Integer, default=0)  # Лимит устройств (0 = безлимит)

    # Связи
    user = relationship("User", back_populates="subscriptions")
    server = relationship("Server", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'))
    amount = Column(Integer)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.now)

    # Связи
    user = relationship("User", back_populates="transactions")

class UserDailyStat(Base):
    """
    Таблица для хранения ежедневной статистики.
    Заполняется фоновой задачей (cron) раз в сутки.
    """
    __tablename__ = 'user_daily_stats'

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'))
    server_id = Column(Integer, ForeignKey('servers.id'))
    date = Column(Date, default=datetime.now().date)  # За какой день статистика
    traffic_bytes = Column(BigInteger, default=0)  # Объем трафика за этот день (скачано + отдано)

    # Связи
    user = relationship("User", back_populates="daily_stats")
    server = relationship("Server", back_populates="daily_stats")

class PromoCode(Base):
    __tablename__ = 'promo_codes'
    
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True)  # Сам код, например "SUMMER2024"
    type = Column(String)  # 'balance' (деньги), 'days' (дни подписки)
    value = Column(Integer)  # Сумма пополнения или кол-во дней
    extra_data = Column(JSON, nullable=True)
    max_uses = Column(Integer, default=0)  # 0 = безлимит
    current_uses = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

class PromoUsage(Base):
    __tablename__ = 'promo_usages'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'))
    promo_id = Column(Integer, ForeignKey('promo_codes.id'))
    created_at = Column(DateTime, default=datetime.now)

    # Связи
    # Можно добавить relationship при необходимости