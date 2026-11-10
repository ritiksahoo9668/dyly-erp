from django.test import TestCase


class HealthEndpointTests(TestCase):
    def test_health_reports_service_status(self):
        response = self.client.get("/api/v1/health/")
        payload = response.json()

        self.assertIn(response.status_code, (200, 503))
        self.assertIn(payload["status"], ("ok", "degraded"))
        self.assertIn(payload["database"], ("ok", "unavailable"))
        self.assertIn(payload["redis"], ("ok", "unavailable"))
