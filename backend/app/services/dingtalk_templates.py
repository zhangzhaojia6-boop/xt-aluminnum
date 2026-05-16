def build_fill_reminder(worker_name: str, shift: str, deadline: str) -> dict:
    return {
        'msgtype': 'action_card',
        'action_card': {
            'title': f'填报提醒 - {shift}',
            'markdown': f'**{worker_name}**，{shift}班次数据尚未填报。\n\n截止时间：{deadline}',
            'single_title': '立即填报',
            'single_url': 'dingtalk://dingtalkclient/page/link?url=/mobile',
        },
    }


def build_anomaly_alert(workshop: str, metric: str, value: float, threshold: float) -> dict:
    return {
        'msgtype': 'action_card',
        'action_card': {
            'title': f'异常告警 - {workshop}',
            'markdown': f'**{workshop}** {metric} 异常\n\n当前值：{value}\n阈值：{threshold}',
            'single_title': '查看详情',
            'single_url': 'dingtalk://dingtalkclient/page/link?url=/manage',
        },
    }


def build_approval_notice(report_id: int, submitter: str, action: str) -> dict:
    return {
        'msgtype': 'text',
        'text': {'content': f'报表 #{report_id}（{submitter}提交）已{action}'},
    }
