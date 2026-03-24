import requests
import json
import os
import logging
import datetime
from typing import Dict, List, Optional, Tuple
from pypushdeer import PushDeer


def beijing_time_converter(timestamp):
    utc_dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
    beijing_tz = datetime.timezone(datetime.timedelta(hours=8))
    beijing_dt = utc_dt.astimezone(beijing_tz)
    return beijing_dt.timetuple()


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

root_logger = logging.getLogger()
for handler in root_logger.handlers:
    if hasattr(handler, 'formatter') and handler.formatter is not None:
        handler.formatter.converter = beijing_time_converter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Environment variable names
# ---------------------------------------------------------------------------
ENV_PUSH_KEY = "SENDKEY"
ENV_COOKIES = "COOKIES"
ENV_EXCHANGE_PLAN = "EXCHANGE_PLAN"

# ---------------------------------------------------------------------------
# API URLs
# ---------------------------------------------------------------------------
CHECKIN_URL = "https://glados.cloud/api/user/checkin"
STATUS_URL = "https://glados.cloud/api/user/status"
POINTS_URL = "https://glados.cloud/api/user/points"
EXCHANGE_URL = "https://glados.cloud/api/user/exchange"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CHECKIN_DATA = {"token": "glados.cloud"}

HEADERS_TEMPLATE = {
    'referer': 'https://glados.cloud/console/checkin',
    'origin': "https://glados.cloud",
    'user-agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    'content-type': 'application/json;charset=UTF-8',
}

# Exchange plan → required points
EXCHANGE_POINTS = {"plan100": 100, "plan200": 200, "plan500": 500}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_config() -> Tuple[str, List[str], str]:
    push_key = os.environ.get(ENV_PUSH_KEY, "")
    raw_cookies = os.environ.get(ENV_COOKIES, "")
    exchange_plan_env = os.environ.get(ENV_EXCHANGE_PLAN, "")

    cookies_list = [c.strip() for c in raw_cookies.split("&") if c.strip()] if raw_cookies else []
    if not cookies_list:
        logger.warning(f"环境变量 '{ENV_COOKIES}' 未设置或为空。")

    if exchange_plan_env in EXCHANGE_POINTS:
        exchange_plan = exchange_plan_env
    else:
        if exchange_plan_env:
            logger.warning(f"'{ENV_EXCHANGE_PLAN}' 的值 '{exchange_plan_env}' 无效，使用默认 'plan500'。")
        exchange_plan = "plan500"

    logger.info(f"共加载 {len(cookies_list)} 个 Cookie，兑换计划: {exchange_plan}")
    return push_key, cookies_list, exchange_plan


def make_request(url: str, method: str, headers: Dict[str, str],
                 data: Optional[Dict] = None, cookies: str = "") -> Optional[requests.Response]:
    session_headers = {**headers, 'cookie': cookies}
    try:
        if method.upper() == 'POST':
            resp = requests.post(url, headers=session_headers, data=json.dumps(data))
        elif method.upper() == 'GET':
            resp = requests.get(url, headers=session_headers)
        else:
            logger.error(f"不支持的 HTTP 方法: {method}")
            return None
        if not resp.ok:
            logger.warning(f"请求 {url} 失败，状态码 {resp.status_code}: {resp.text}")
            return None
        return resp
    except requests.exceptions.RequestException as e:
        logger.error(f"请求 {url} 时网络错误: {e}")
        return None


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
def checkin_and_process(cookie: str, exchange_plan: str) -> Dict[str, str]:
    result = {
        'email': '',
        'status': '签到请求失败',
        'points': '0',
        'days': '获取失败',
        'points_total': '获取失败',
        'exchange': '兑换跳过',
    }

    # ---- 1. Checkin ----
    checkin_resp = make_request(CHECKIN_URL, 'POST', HEADERS_TEMPLATE, CHECKIN_DATA, cookies=cookie)
    if not checkin_resp:
        return result
    try:
        cdata = checkin_resp.json()
        msg = cdata.get('message', '')
        result['points'] = str(cdata.get('points', 0))
        if "Checkin! Got" in msg:
            result['status'] = f"签到成功，获得 {result['points']} 积分"
        elif "Checkin Repeats!" in msg:
            result['status'] = "重复签到，明天再来"
            result['points'] = "0"
        else:
            result['status'] = f"签到失败: {msg}"
            result['points'] = "0"
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"解析签到响应失败: {e}")
        return result

    # ---- 2. Account status (remaining days + email) ----
    status_resp = make_request(STATUS_URL, 'GET', HEADERS_TEMPLATE, cookies=cookie)
    if status_resp:
        try:
            sdata = status_resp.json()
            left = sdata.get('data', {}).get('leftDays')
            result['days'] = f"{int(float(left))} 天" if left is not None else "获取失败"
            result['email'] = sdata.get('data', {}).get('email', '')
        except Exception as e:
            logger.error(f"解析状态响应失败: {e}")

    # ---- 3. Current points ----
    current_points = 0
    points_resp = make_request(POINTS_URL, 'GET', HEADERS_TEMPLATE, cookies=cookie)
    if points_resp:
        try:
            pdata = points_resp.json()
            pts = pdata.get('points')
            if pts is not None:
                current_points = int(float(pts))
                result['points_total'] = f"{current_points} 积分"
        except Exception as e:
            logger.error(f"解析积分响应失败: {e}")

    # ---- 4. Auto exchange / redeem ----
    required = EXCHANGE_POINTS.get(exchange_plan, 500)
    if current_points >= required:
        logger.info(f"积分 {current_points} >= {required}，开始兑换 {exchange_plan}")
        ex_resp = make_request(EXCHANGE_URL, 'POST', HEADERS_TEMPLATE,
                               {"planType": exchange_plan}, cookies=cookie)
        if ex_resp:
            try:
                edata = ex_resp.json()
                if edata.get('code') == 0:
                    result['exchange'] = f"兑换成功: {exchange_plan}"
                else:
                    detail = edata.get('message', '未知错误')
                    result['exchange'] = f"兑换失败: {detail}"
            except Exception as e:
                logger.error(f"解析兑换响应失败: {e}")
                result['exchange'] = "兑换响应解析失败"
        else:
            result['exchange'] = "兑换请求失败"
    else:
        logger.info(f"积分不足 ({current_points}/{required})，跳过兑换 {exchange_plan}")
        result['exchange'] = f"积分不足({current_points}/{required})，未兑换"

    return result


def format_push_content(results: List[Dict[str, str]]) -> Tuple[str, str]:
    success = sum(1 for r in results if "成功" in r['status'])
    fail = sum(1 for r in results if "失败" in r['status'])
    repeats = sum(1 for r in results if "重复" in r['status'])

    title = f'GLaDOS 签到, 成功{success}, 失败{fail}, 重复{repeats}'

    lines = []
    for i, r in enumerate(results, 1):
        label = r['email'] or f"账号{i}"
        lines.append(
            f"{label}: P:{r['points']} 剩余:{r['days']} "
            f"总积分:{r['points_total']} | {r['status']}; {r['exchange']}"
        )
    return title, "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    try:
        push_key, cookies_list, exchange_plan = load_config()

        if not cookies_list:
            logger.error("未找到有效的 Cookie，退出。")
            title, content = "# 未找到 cookies!", ""
        else:
            results = []
            for idx, cookie in enumerate(cookies_list, 1):
                logger.info(f"--- 处理第 {idx} 个账户 ---")
                res = checkin_and_process(cookie, exchange_plan)
                results.append(res)

            title, content = format_push_content(results)
            logger.info(f"推送标题: {title}")
            logger.info(f"推送内容:\n{content}")
    except Exception as e:
        logger.error(f"主程序异常: {e}")
        title, content = "# 脚本执行出错", str(e)

    # Push notification
    if not push_key:
        logger.info(f"未设置 '{ENV_PUSH_KEY}'，跳过推送。")
    else:
        try:
            pushdeer = PushDeer(pushkey=push_key)
            pushdeer.send_text(title, desp=content)
            logger.info("推送通知发送成功。")
        except Exception as e:
            logger.error(f"推送通知失败: {e}")


if __name__ == '__main__':
    main()
