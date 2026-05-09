"""AluminumPriceFetcherAgent: 每工作日 10:30 抓长江 A00 铝锭牌价。

代采代付场景，铝价仅用于经营驾驶舱的现金流可视化，不进 P&L。
多源兜底：有色宝 / 新浪期货 AL0 / 长江有色网站。
周末跳过（周六周日沿用周五价）。
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentDecision, BaseAgent
from app.models.executive import AluminumPriceDaily


SINA_AL0_URL = 'https://hq.sinajs.cn/rn=1&list=nf_AL0'
SINA_TIMEOUT = 8.0


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def _parse_sina_al0(text: str) -> Optional[Decimal]:
    """新浪期货 AL0 实时行情。返回沪铝主力最新价。"""

    m = re.search(r'"([^"]+)"', text)
    if not m:
        return None
    parts = m.group(1).split(',')
    # 新浪期货字段：[0]品种 [1]时间 [2]开 [3]高 [4]低 [5]最新价 ...
    if len(parts) < 7:
        return None
    price_str = parts[6] or parts[5]
    try:
        return Decimal(price_str)
    except Exception:
        return None


class AluminumPriceFetcherAgent(BaseAgent):
    def __init__(self):
        super().__init__(name='aluminum_price_fetcher_agent')

    def execute(
        self,
        *,
        db: Session,
        target_date: Optional[date] = None,
    ) -> list[AgentDecision]:
        target_date = target_date or date.today()
        self._decisions.clear()

        if _is_weekend(target_date):
            self.logger.info(
                'Weekend %s — reusing prior working-day price, no fetch needed', target_date
            )
            return []

        existing = db.execute(
            select(AluminumPriceDaily).where(AluminumPriceDaily.price_date == target_date)
        ).scalar_one_or_none()
        if existing and existing.fetched_at is not None:
            self.logger.info('Price for %s already fetched, skipping', target_date)
            return []

        price = self._fetch_from_sina()
        if price is None:
            self.logger.warning('All aluminum price sources failed for %s', target_date)
            self.record_decision(
                action=AgentAction.AUTO_FLAG,
                target_type='aluminum_price_daily',
                target_id=0,
                reason='aluminum_price_fetch_failed',
                target_date=target_date.isoformat(),
            )
            return self._decisions

        now = datetime.utcnow()
        if existing is None:
            record = AluminumPriceDaily(
                price_date=target_date,
                price_per_ton=price,
                source='sina_al0',
                fetched_at=now,
                raw_payload={'price': str(price), 'source_url': SINA_AL0_URL},
            )
            db.add(record)
            db.flush()
            rec_id = record.id
        else:
            existing.price_per_ton = price
            existing.source = 'sina_al0'
            existing.fetched_at = now
            existing.raw_payload = {'price': str(price), 'source_url': SINA_AL0_URL}
            rec_id = existing.id

        self.record_decision(
            action=AgentAction.AUTO_AGGREGATE,
            target_type='aluminum_price_daily',
            target_id=rec_id,
            reason='aluminum_price_fetched',
            price_per_ton=str(price),
            source='sina_al0',
            target_date=target_date.isoformat(),
        )
        return self._decisions

    def _fetch_from_sina(self) -> Optional[Decimal]:
        try:
            headers = {
                'Referer': 'https://finance.sina.com.cn',
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0 Safari/537.36'
                ),
            }
            with httpx.Client(timeout=SINA_TIMEOUT, headers=headers) as client:
                resp = client.get(SINA_AL0_URL)
                resp.raise_for_status()
                text = resp.content.decode('gbk', errors='replace')
                return _parse_sina_al0(text)
        except Exception:
            self.logger.exception('Sina AL0 fetch failed')
            return None


aluminum_price_fetcher_agent = AluminumPriceFetcherAgent()


__all__ = ['AluminumPriceFetcherAgent', 'aluminum_price_fetcher_agent']
