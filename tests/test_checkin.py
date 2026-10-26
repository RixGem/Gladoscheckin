import os
import unittest
from unittest import mock

import checkin
from checkin import API, Checker, CheckinStatus, Config, normalize_domain, parse_domains

GLD_COOKIE = "gld:sess=a; gld:sess.sig=b"


def make_config(**env):
    base = {"GLADOS_COOKIES": GLD_COOKIE}
    base.update(env)
    with mock.patch.dict(os.environ, base, clear=True):
        return Config()


class FakeResponse:
    def __init__(self, payload, ok=True, status_code=200, text=None):
        self._payload = payload
        self.ok = ok
        self.status_code = status_code
        self.text = text if text is not None else str(payload)

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class DomainParsingTest(unittest.TestCase):
    def test_normalize_strips_scheme_path_port_and_case(self):
        self.assertEqual(normalize_domain(" https://GLaDOS.cloud:443/console/checkin?x=1 "), "glados.cloud")
        self.assertEqual(normalize_domain("railgun.info/"), "railgun.info")

    def test_parse_supports_separators_dedupes_and_reports_invalid(self):
        domains, invalid = parse_domains("glados.cloud, railgun.info；glados.cloud & glados.one\nnot_a_domain")
        self.assertEqual(domains, ["glados.cloud", "railgun.info", "glados.one"])
        self.assertEqual(invalid, ["not_a_domain"])


class ConfigDomainsTest(unittest.TestCase):
    def test_default_domains(self):
        self.assertEqual(make_config().domains, ["glados.cloud", "railgun.info"])

    def test_env_overrides_domains(self):
        self.assertEqual(make_config(GLADOS_DOMAINS="https://glados.cloud").domains, ["glados.cloud"])

    def test_invalid_env_falls_back_to_default(self):
        self.assertEqual(make_config(GLADOS_DOMAINS="  ,;  ").domains, ["glados.cloud", "railgun.info"])
        self.assertEqual(make_config(GLADOS_DOMAINS="bad_domain").domains, ["glados.cloud", "railgun.info"])

    def test_site_cookie_keys_follow_configured_domains(self):
        config = make_config(GLADOS_DOMAINS="railgun.info,glados.one")
        self.assertEqual(list(config.site_cookie_keys), ["railgun.info"])


class CheckerFlowTest(unittest.TestCase):
    def run_checker(self, config, responses):
        """responses: {(domain, path): payload}; records the order of requests."""
        calls = []

        def fake_request(api, url, method, data=None, cookies=""):
            path = url.split(api.domain, 1)[1]
            calls.append((api.domain, path))
            payload = responses.get((api.domain, path))
            return None if payload is None else FakeResponse(payload)

        with mock.patch.object(API, "_make_request", fake_request):
            checker = Checker(config)
            checker.checkin_all()
        return checker, calls

    def test_only_configured_domain_is_requested(self):
        config = make_config(GLADOS_DOMAINS="glados.cloud")
        checker, calls = self.run_checker(config, {
            ("glados.cloud", "/api/user/status"): {"code": 0, "data": {"leftDays": "10.5"}},
            ("glados.cloud", "/api/user/checkin"): {"code": 0, "points": 2, "message": "ok"},
            ("glados.cloud", "/api/user/points"): {"code": 0, "points": "50"},
        })
        self.assertEqual({domain for domain, _ in calls}, {"glados.cloud"})
        self.assertEqual(checker.failed_cookie_indexes(), [])
        result = checker.results[0]
        self.assertEqual(result.code, CheckinStatus.SUCCESS)
        self.assertEqual(result.points, "2")
        self.assertEqual(result.days, "10 天")

    def test_exchange_skipped_when_points_insufficient(self):
        config = make_config(GLADOS_DOMAINS="glados.cloud", GLADOS_EXCHANGE_PLAN="plan100")
        checker, calls = self.run_checker(config, {
            ("glados.cloud", "/api/user/checkin"): {"code": 1, "message": "repeat"},
            ("glados.cloud", "/api/user/points"): {"code": 0, "points": 99},
        })
        self.assertNotIn(("glados.cloud", "/api/user/exchange"), calls)
        self.assertIn("99/100", checker.results[0].exchange)
        self.assertEqual(checker.failed_cookie_indexes(), [])

    def test_exchange_runs_when_points_sufficient(self):
        config = make_config(GLADOS_DOMAINS="glados.cloud", GLADOS_EXCHANGE_PLAN="plan100")
        checker, calls = self.run_checker(config, {
            ("glados.cloud", "/api/user/checkin"): {"code": 0, "points": 1},
            ("glados.cloud", "/api/user/points"): {"code": 0, "points": 100},
            ("glados.cloud", "/api/user/exchange"): {"code": 0, "message": "ok"},
        })
        self.assertIn(("glados.cloud", "/api/user/exchange"), calls)
        self.assertEqual(checker.results[0].exchange, "兑换成功: plan100")

    def test_auth_failure_skips_points_and_exchange_but_other_domain_counts(self):
        denied = {"code": -2, "message": "没有权限"}
        config = make_config()
        checker, calls = self.run_checker(config, {
            ("glados.cloud", "/api/user/checkin"): {"code": 0, "points": 1},
            ("glados.cloud", "/api/user/points"): {"code": 0, "points": 10},
            ("railgun.info", "/api/user/status"): denied,
            ("railgun.info", "/api/user/checkin"): denied,
        })
        self.assertEqual(
            [path for domain, path in calls if domain == "railgun.info"],
            ["/api/user/status", "/api/user/checkin"],
        )
        self.assertEqual(checker.failed_cookie_indexes(), [])

    def test_all_domains_failing_marks_cookie_failed(self):
        config = make_config(GLADOS_DOMAINS="glados.cloud")
        checker, _ = self.run_checker(config, {})
        self.assertEqual(checker.failed_cookie_indexes(), [1])


class ResponseHandlingTest(unittest.TestCase):
    def test_non_json_checkin_response_is_failure_not_crash(self):
        api = API("glados.cloud")
        html = FakeResponse(ValueError("no json"), text="<html>blocked</html>")
        with mock.patch.object(API, "_make_request", return_value=html):
            result = api.checkin(GLD_COOKIE)
        self.assertEqual(result["code"], CheckinStatus.FAILURE)
        api.close()

    def test_post_is_not_retried_on_status(self):
        self.assertNotIn("POST", API.RETRY.allowed_methods)


class MainExitCodeTest(unittest.TestCase):
    def test_missing_cookies_returns_config_error(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(checkin.main(), checkin.EXIT_CONFIG_ERROR)

    def test_failed_checkin_returns_nonzero(self):
        with mock.patch.dict(os.environ, {"GLADOS_COOKIES": GLD_COOKIE, "GLADOS_DOMAINS": "glados.cloud"}, clear=True), \
                mock.patch.object(API, "_make_request", return_value=None):
            self.assertEqual(checkin.main(), checkin.EXIT_CHECKIN_FAILED)


if __name__ == "__main__":
    unittest.main()
