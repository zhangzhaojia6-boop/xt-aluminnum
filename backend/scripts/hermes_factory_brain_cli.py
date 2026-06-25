from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('scenario', choices=['daily_report', 'anomaly_analysis', 'business_question'])
    parser.add_argument('--text', required=True)
    args = parser.parse_args()
    print(f'Hermes factory brain smoke: scenario={args.scenario} text={args.text}')


if __name__ == '__main__':
    main()
