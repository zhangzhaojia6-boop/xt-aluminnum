from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('scenario', choices=['daily_report', 'anomaly_analysis', 'business_question'])
    parser.add_argument('--text')
    parser.add_argument('--business-date')
    args = parser.parse_args()
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
