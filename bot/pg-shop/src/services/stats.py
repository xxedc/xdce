import asyncio
import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.config import settings
from src.database.models import Subscription, UserDailyStat
from src.services.marzban_api import api

logger = logging.getLogger(__name__)

# Инициализация подключения к БД для фоновых задач
engine = create_async_engine(settings.DB_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False)

async def collect_daily_stats():
    """
    Фоновая задача: собирает статистику трафика по всем активным подпискам.
    Должна запускаться планировщиком (например, раз в сутки).
    """
    logger.info("Starting daily traffic stats collection...")
    
    async with async_session() as session:
        # Получаем все активные подписки
        stmt = select(Subscription).where(Subscription.status == 'active')
        result = await session.execute(stmt)
        subscriptions = result.scalars().all()

        today = datetime.now().date()
        
        for sub in subscriptions:
            try:
                # Запрашиваем актуальный трафик из Marzban
                # Если используется несколько серверов, здесь нужно выбирать API клиент 
                # на основе sub.server_id
                current_usage = await api.get_user_usage(sub.marzban_username)
                
                if current_usage is None:
                    continue

                # Рассчитываем разницу (delta)
                last_usage = sub.last_traffic_usage or 0
                
                if current_usage >= last_usage:
                    delta = current_usage - last_usage
                else:
                    # Если текущее использование меньше последнего сохраненного,
                    # значит на сервере был сброс статистики.
                    # Считаем весь текущий трафик как новый.
                    delta = current_usage

                if delta == 0:
                    continue

                # Ищем или создаем запись статистики за сегодня
                stat_stmt = select(UserDailyStat).where(
                    UserDailyStat.user_id == sub.user_id,
                    UserDailyStat.server_id == sub.server_id,
                    UserDailyStat.date == today
                )
                stat_result = await session.execute(stat_stmt)
                daily_stat = stat_result.scalar_one_or_none()

                if daily_stat:
                    daily_stat.traffic_bytes += delta
                else:
                    daily_stat = UserDailyStat(
                        user_id=sub.user_id,
                        server_id=sub.server_id,
                        date=today,
                        traffic_bytes=delta
                    )
                    session.add(daily_stat)

                # Обновляем "якорь" в подписке
                sub.last_traffic_usage = current_usage
                
            except Exception as e:
                logger.error(f"Failed to collect stats for user {sub.marzban_username}: {e}")
        
        await session.commit()
    
    logger.info("Daily traffic stats collection finished.")