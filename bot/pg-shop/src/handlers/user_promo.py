from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.database.requests import activate_promo, get_promo, get_user_subscriptions, is_promo_used_by_user
from src.utils.translations import get_text
from src.services.marzban_api import api
from src.keyboards.builders import instruction_links_kb, promo_sub_select_kb

router = Router()

class PromoState(StatesGroup):
    waiting_for_code = State()
    waiting_for_sub_selection = State()

@router.callback_query(F.data == "activate_promo")
async def ask_promo_code(callback: CallbackQuery, state: FSMContext, t):
    await callback.message.answer(t("enter_promo"), parse_mode="HTML")
    await state.set_state(PromoState.waiting_for_code)
    await callback.answer()

@router.message(PromoState.waiting_for_code)
async def process_promo_code(message: Message, state: FSMContext, t, lang):
    code = message.text.strip()
    user_id = message.from_user.id
    
    # Предварительная проверка типа промокода
    promo = await get_promo(code)
    
    if not promo:
        await state.clear()
        await message.answer(t("promo_not_found"), parse_mode="HTML")
        return

    # Проверки валидности ДО выбора подписки
    if promo.expires_at and promo.expires_at < datetime.now():
        await state.clear()
        await message.answer(t("promo_expired"), parse_mode="HTML")
        return
        
    if await is_promo_used_by_user(user_id, promo.id):
        await state.clear()
        await message.answer(t("promo_used"), parse_mode="HTML")
        return

    key_data = None
    marzban_username = None
    
    if promo: # promo is guaranteed not None here, but keeping structure
        if promo.type == 'subscription':
            # Генерируем ключ перед активацией
            marzban_username = f"promo_{user_id}_{code}"
            key_data = await api.create_key(username=marzban_username)
        
        elif promo.type == 'days':
            # Проверяем количество подписок у пользователя
            subs = await get_user_subscriptions(user_id)
            valid_subs = [s for s in subs if s.status != 'banned'] # Исключаем забаненные, если нужно
            
            if False and len(valid_subs) > 1:
                # 禁用多订阅选择，直接用最新的时间套餐
                await message.answer(t("choose_sub_promo"), reply_markup=promo_sub_select_kb(valid_subs, lang), parse_mode="HTML")
                await state.update_data(promo_code=code)
                await state.set_state(PromoState.waiting_for_sub_selection)
                return
            elif len(valid_subs) == 1:
                # Если одна — применяем к ней
                # Передадим ID в activate_promo
                subscription_id = valid_subs[0].id
                return await apply_promo(message, user_id, code, key_data, marzban_username, t, state, subscription_id)
    
    await apply_promo(message, user_id, code, key_data, marzban_username, t, state)

@router.callback_query(PromoState.waiting_for_sub_selection, F.data.startswith("select_promo_sub_"))
async def promo_sub_selected(callback: CallbackQuery, state: FSMContext, t):
    sub_id = int(callback.data.split("_")[3])
    data = await state.get_data()
    code = data.get("promo_code")
    
    # Применяем промокод к выбранной подписке
    await apply_promo(callback.message, callback.from_user.id, code, None, None, t, state, sub_id)
    await callback.answer()

async def apply_promo(message: Message, user_id: int, code: str, key_data: str, marzban_username: str, t, state: FSMContext, sub_id: int = None):
    """Вспомогательная функция для финальной активации и ответа"""
    success, msg_key, p_type, value, extra = await activate_promo(user_id, code, key_data, marzban_username, subscription_id=sub_id)
    
    if success:
        if p_type == 'balance':
            await message.answer(t("promo_success_balance", value=value), parse_mode="HTML")
        elif p_type == 'days':
            await message.answer(t("promo_success_days", value=value), parse_mode="HTML")
        elif p_type == 'subscription':
            days = extra.get('days', 30)
            limit = extra.get('limit', 1)
            location = extra.get('location', 'multi')
            await message.answer(t("promo_success_sub", location=location, days=days, limit=limit), parse_mode="HTML")
            await message.answer(f"<code>{key_data}</code>", parse_mode="HTML", reply_markup=instruction_links_kb().as_markup())
    else:
        # Обработка ошибок
        error_map = {
            "not_found": "promo_not_found",
            "expired": "promo_expired",
            "limit_reached": "promo_limit",
            "already_used": "promo_used",
            "no_sub_to_extend": "promo_no_sub"
        }
        text_key = error_map.get(msg_key, "error")
        await message.answer(t(text_key), parse_mode="HTML")
    
    # Сбрасываем состояние
    await state.clear()