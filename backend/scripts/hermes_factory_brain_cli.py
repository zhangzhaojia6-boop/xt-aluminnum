from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.hermes_langgraph_app import build_factory_brain_graph, initial_factory_brain_state


def _ask(text: str) -> dict:
    graph = build_factory_brain_graph(checkpointer=None)
    return dict(
        graph.invoke(
            initial_factory_brain_state(
                trace_id='cli-factory-brain',
                text=text,
                actor_user_id=None,
                channel='cli',
            )
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('scenario', choices=['daily_report', 'anomaly_analysis', 'business_question', 'ask'])
    parser.add_argument('ask_text', nargs='?')
    parser.add_argument('--text')
    parser.add_argument('--business-date')
    args = parser.parse_args()
    if args.scenario == 'ask':
        text = str(args.ask_text or args.text or '').strip()
        if not text:
            parser.error('ask requires text')
        print(json.dumps(_ask(text), ensure_ascii=False, default=str))
        return
    if args.business_date and args.scenario != 'daily_report':
        parser.error('--business-date is only supported for daily_report')
    if args.text:
        text = args.text
    elif args.business_date:
        text = f'生成 {args.business_date} 正式日报'
    else:
        parser.error('one of --text or --business-date is required')
    print(f'Hermes factory brain smoke: scenario={args.scenario} text={text}')


if __name__ == '__main__':
    main()
